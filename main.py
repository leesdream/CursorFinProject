"""
Financial Portfolio Dashboard
Reads the latest Tiger Brokers CSV, enriches with MCP server data, opens report in browser.
"""

import asyncio
import io
import os
import sys
import webbrowser
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
from report_generator import build_report

load_dotenv()


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
                    max_tokens=4096,
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


async def main():
    print("Financial Portfolio Dashboard")
    print("=" * 40)

    # 1. Parse the latest statement
    statement_dir = Path(__file__).parent / "financialstatement"
    print(f"\n[1/3] Loading statement from {statement_dir} ...")
    portfolio = parse_latest_statement(str(statement_dir))
    print(
        f"  Account: {portfolio.account_holder} ({portfolio.account_number})"
        f" — {portfolio.statement_date}"
    )
    print(
        f"  Holdings: {len(portfolio.stocks)} stocks, "
        f"{len(portfolio.options)} options, {len(portfolio.funds)} funds"
    )
    print(f"  Total value: ${portfolio.overview.ending_total:,.2f}")

    # 2. Run each MCP server analysis independently
    print(f"\n[2/3] Running {len(MCP_SERVERS)} MCP server analysis...")
    sections: dict[str, str] = {}
    for server in MCP_SERVERS:
        print(f"\n  [{server['name']}]")
        try:
            result = await run_mcp_analysis(portfolio, server)
            sections[server["section_title"]] = result
            print(f"  ✓ {server['name']} analysis complete")
        except Exception as exc:
            sections[server["section_title"]] = (
                f"Analysis unavailable: {exc}\n\n"
                "Check that the MCP server package is installed and accessible via npx."
            )
            print(f"  ✗ {server['name']} error: {exc}")

    # 3. Build and open the report
    print("\n[3/3] Generating report...")
    output = str(Path(__file__).parent / "report.html")
    build_report(portfolio, sections, output_path=output)
    print(f"  Report saved: {output}")

    url = f"file:///{Path(output).resolve().as_posix()}"
    webbrowser.open(url)
    print(f"  Opened in browser: {url}")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
