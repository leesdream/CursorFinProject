"""
Financial Portfolio Dashboard
Reads the latest Tiger Brokers CSV, enriches with MCP server data, opens report in browser.
"""

import argparse
import asyncio
import io
import json
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows so Unicode chars don't crash
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from csv_parser import parse_latest_statement, Portfolio
from mcp_config import MCP_SERVERS
from philosophy_config import PHILOSOPHY_ANALYSES
from report_generator import build_report

load_dotenv()

CACHE_FILE = Path(__file__).parent / "analysis_cache.json"


async def run_mcp_analysis(portfolio: Portfolio, server: dict) -> str:
    """Connect to a single MCP server, run an agentic analysis loop, return text."""
    server_params = StdioServerParameters(
        command=server["command"],
        args=server["args"],
        env=None,
    )

    print(f"  Connecting to {server['name']} MCP server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tools = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                }
                for t in tools_result.tools
            ]

            print(f"  {server['name']}: {len(tools)} tools available — running analysis...")

            client = anthropic.Anthropic()
            system = (
                "You are a professional financial analyst. "
                "You have access to market data tools — use them to retrieve live data "
                "before forming your analysis. Be specific and cite numbers you retrieve."
            )

            messages = [
                {
                    "role": "user",
                    "content": (
                        f"Here is the client's portfolio as of {portfolio.statement_date}:\n\n"
                        f"{portfolio.to_json()}\n\n"
                        f"{server['analysis_prompt']}"
                    ),
                }
            ]

            # Agentic tool-use loop: keep going until Claude stops calling tools
            while True:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,
                    system=[
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=messages,
                    tools=tools,
                )

                # Collect any tool_use blocks
                tool_uses = [b for b in response.content if b.type == "tool_use"]

                if not tool_uses:
                    # No more tool calls — extract final text
                    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
                    return "\n".join(text_blocks)

                # Append assistant turn, then resolve each tool call against the MCP server
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for tu in tool_uses:
                    print(f"    → calling tool: {tu.name}")
                    try:
                        result = await session.call_tool(tu.name, tu.input)
                        content = str(result.content)
                    except Exception as exc:
                        content = f"Error calling {tu.name}: {exc}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": content,
                        }
                    )

                messages.append({"role": "user", "content": tool_results})


def run_philosophy_analysis(portfolio: Portfolio, config: dict) -> str:
    """Call Claude directly (no MCP tools) to analyse the portfolio through a philosophy lens."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": config["system_prompt"],
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here is the client's portfolio as of {portfolio.statement_date}:\n\n"
                    f"{portfolio.to_json()}\n\n"
                    f"{config['analysis_prompt']}"
                ),
            }
        ],
    )
    return "".join(b.text for b in response.content if hasattr(b, "text"))


def run_synthesis_analysis(
    portfolio: Portfolio,
    mcp_sections: dict[str, str],
    philosophy_sections: dict[str, str],
) -> str:
    """Synthesize Yahoo Finance, Howard Marks, and Taleb analyses into a consolidated action plan."""
    all_analyses = "\n\n".join(
        f"## {title}\n{content}"
        for title, content in {**mcp_sections, **philosophy_sections}.items()
    )

    system_prompt = (
        "You are a senior investment advisor who reconciles multiple analytical frameworks "
        "into clear, actionable guidance. You have four independent analyses of the same "
        "portfolio: (1) Yahoo Finance — data-driven, market consensus; "
        "(2) Peter Lynch — GARP, PEG ratio, category classification, ten-bagger hunting; "
        "(3) Howard Marks — risk-first, second-level thinking, cycle awareness; "
        "(4) Nassim Taleb — antifragility, tail risk, Black Swan exposure. "
        "Your job is to reconcile these views, surface conflicts, and deliver one prioritised action plan."
    )

    analysis_prompt = (
        "Synthesize the four analyses below into a consolidated report with exactly these sections:\n\n"
        "1. **Consensus Calls** — positions or themes where Yahoo Finance data, Lynch's GARP view, "
        "Marks' risk view, AND Taleb's fragility view all point the same direction. "
        "These are highest-conviction findings.\n\n"
        "2. **Conflicting Views** — where the frameworks disagree, present a clear comparison:\n"
        "   - State what each framework says\n"
        "   - Explain why they differ (valuation vs. risk? growth vs. fragility?)\n"
        "   - Give your own tiebreaker view\n\n"
        "3. **Priority Action List** — 5-8 specific, concrete next steps ranked by urgency. For each:\n"
        "   - Action (Buy / Sell / Hedge / Rebalance / Monitor)\n"
        "   - Position or asset\n"
        "   - Rationale (cite which framework(s) support it)\n"
        "   - Urgency: Immediate / This month / Watch\n\n"
        "4. **Portfolio Health Score** — rate the portfolio on four dimensions (0–10 each):\n"
        "   - Return Potential (Yahoo Finance view)\n"
        "   - Growth at Reasonable Price (Lynch view)\n"
        "   - Risk Management (Marks view)\n"
        "   - Resilience / Antifragility (Taleb view)\n"
        "   Add one sentence explanation per score.\n\n"
        "Do not repeat analysis already done. Focus on synthesis, comparison, and actionable decisions.\n\n"
        "---\n"
        f"ANALYSES:\n{all_analyses}"
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Portfolio as of {portfolio.statement_date}:\n\n"
                    f"{portfolio.to_json()}\n\n"
                    f"{analysis_prompt}"
                ),
            }
        ],
    )
    return "".join(b.text for b in response.content if hasattr(b, "text"))


async def main():
    parser = argparse.ArgumentParser(description="Financial Portfolio Dashboard")
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Skip MCP server calls (no API usage); report shows parsed CSV data only.",
    )
    args = parser.parse_args()

    print("Financial Portfolio Dashboard")
    print("=" * 40)
    if args.no_mcp:
        print("  [--no-mcp] MCP analysis skipped.")

    # 1. Parse the latest statement
    statement_dir = Path(__file__).parent / "financialstatement"
    print(f"\n[1/3] Loading statement from {statement_dir} ...")
    portfolio = parse_latest_statement(str(statement_dir))
    portfolio.account_holder = "meatball"
    portfolio.account_number = "XXXX"
    portfolio.address = "XXXX"
    print(
        f"  Account: {portfolio.account_holder} ({portfolio.account_number})"
        f" — {portfolio.statement_date}"
    )
    print(
        f"  Holdings: {len(portfolio.stocks)} stocks, "
        f"{len(portfolio.options)} options, {len(portfolio.funds)} funds"
    )
    print(f"  Total value: ${portfolio.overview.ending_total:,.2f}")

    # 2. Run analyses (skipped with --no-mcp)
    mcp_sections: dict[str, str] = {}
    philosophy_sections: dict[str, str] = {}
    synthesis_section: dict[str, str] = {}
    analysis_date: str = ""
    if args.no_mcp:
        print("\n[2/3] Skipping live analysis (--no-mcp) — loading cached results...")
        if CACHE_FILE.exists():
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            mcp_sections = cache.get("mcp_sections", {})
            philosophy_sections = cache.get("philosophy_sections", {})
            synthesis_section = cache.get("synthesis_section", {})
            analysis_date = cache.get("generated_at", "")
            print(f"  Loaded cache from {analysis_date}")
        else:
            print("  No cache found — report will show CSV data only.")
    else:
        print(f"\n[2/3] Running {len(MCP_SERVERS)} MCP server analysis...")
        for server in MCP_SERVERS:
            print(f"\n  [{server['name']}]")
            try:
                result = await run_mcp_analysis(portfolio, server)
                mcp_sections[server["section_title"]] = result
                print(f"  ✓ {server['name']} analysis complete")
            except Exception as exc:
                mcp_sections[server["section_title"]] = (
                    f"Analysis unavailable: {exc}\n\n"
                    "Check that the MCP server package is installed and accessible via npx."
                )
                print(f"  ✗ {server['name']} error: {exc}")

        print(f"\n  Running {len(PHILOSOPHY_ANALYSES)} philosophy analyses...")
        for config in PHILOSOPHY_ANALYSES:
            print(f"  [{config['name']}]")
            try:
                result = run_philosophy_analysis(portfolio, config)
                philosophy_sections[config["section_title"]] = result
                print(f"  ✓ {config['name']} analysis complete")
            except Exception as exc:
                philosophy_sections[config["section_title"]] = f"Analysis unavailable: {exc}"
                print(f"  ✗ {config['name']} error: {exc}")

        # Synthesis: consolidate all three analyses
        if mcp_sections or philosophy_sections:
            print("\n  [synthesis] Consolidating Yahoo Finance + Lynch + Marks + Taleb...")
            try:
                result = run_synthesis_analysis(portfolio, mcp_sections, philosophy_sections)
                synthesis_section["Synthesis — Action Plan"] = result
                print("  ✓ Synthesis complete")
            except Exception as exc:
                synthesis_section["Synthesis — Action Plan"] = f"Synthesis unavailable: {exc}"
                print(f"  ✗ Synthesis error: {exc}")

        # Save fresh results to cache
        if mcp_sections or philosophy_sections or synthesis_section:
            cache = {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "mcp_sections": mcp_sections,
                "philosophy_sections": philosophy_sections,
                "synthesis_section": synthesis_section,
            }
            CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            print("\n  Analysis cached to analysis_cache.json")

    # 3. Build and open the report
    print("\n[3/3] Generating report...")
    output = str(Path(__file__).parent / "report.html")
    build_report(
        portfolio, mcp_sections, philosophy_sections,
        synthesis_section=synthesis_section,
        analysis_date=analysis_date,
        output_path=output,
    )
    print(f"  Report saved: {output}")

    url = f"file:///{Path(output).resolve().as_posix()}"
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if Path(edge).exists():
        import subprocess
        subprocess.Popen([edge, url])
    else:
        webbrowser.open(url)
    print(f"  Opened in browser: {url}")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
