# Financial Portfolio Dashboard

Reads your latest Tiger Brokers brokerage statement CSV, enriches it with live market data, and generates a self-contained HTML report that opens in the browser.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file with your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Drop your Tiger Brokers `Statement_*.csv` file into the `financialstatement/` folder.

## Running

### With MCP analysis (full report)

Calls the Yahoo Finance MCP server via the Anthropic API to enrich the report with live market data and analyst commentary. Requires `ANTHROPIC_API_KEY`.

```
.venv\Scripts\python.exe main.py
```

### Without live analysis (cached results)

Skips all API calls. Loads the Yahoo Finance, Howard Marks, and Taleb analysis from the last full run and includes them in the report with a "cached [date]" badge so you always know how fresh the data is. Falls back to CSV data only if no cache exists yet.

```
.venv\Scripts\python.exe main.py --no-mcp
```

Both commands produce `report.html` and open it in the browser automatically. The first full run also writes `analysis_cache.json` (gitignored) for subsequent `--no-mcp` runs.

## What's in the report

Running without `--no-mcp` produces three categories of analysis, each as a collapsible card in the HTML (click the header arrow to expand or collapse):

**Yahoo Finance (blue header)** — live prices, 52-week range, analyst consensus, and per-position buy/hold/sell recommendations.

**Howard Marks — Risk Control (dark header)** — applies Marks' framework from *The Most Important Thing* and his Oaktree memos:
- Hidden risk inventory — positions whose calm recent behavior may mask fragility
- Downside audit — realistic worst-case loss per significant holding
- Cycle positioning — late-cycle risk exposure vs. genuine margin of safety
- Asymmetry scorecard — positions with favorable vs. unfavorable risk/reward
- Marks verdict — overall risk posture in one paragraph

**Taleb — Antifragile Analysis (dark header)** — applies Taleb's framework from *Antifragile* and *The Black Swan*:
- Triad classification — each position labeled fragile / robust / antifragile
- Barbell assessment — safe core + speculative tail vs. dangerously in the fragile middle
- Ruin scenarios — any position large enough to cause permanent capital impairment
- Convexity inventory — convex payoffs (options, asymmetric upside) vs. concave payoffs
- Black Swan exposure — holdings most vulnerable to a low-probability, high-impact event
- Taleb verdict — one paragraph plus the single most important structural change recommended
