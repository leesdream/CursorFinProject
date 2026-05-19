MCP_SERVERS = [
    {
        "name": "yahoo_finance",
        "command": "npx",
        "args": ["-y", "@fre4x/yahoo-finance@1.1.0"],
        "section_title": "Yahoo Finance Analysis",
        "analysis_prompt": (
            "You have access to Yahoo Finance tools. For each stock in this portfolio, "
            "fetch the current price, 52-week high/low, and analyst consensus rating. "
            "Then provide 3-5 specific actionable recommendations (buy more / hold / trim / sell) "
            "for each position, citing the data you retrieved. "
            "Format your response in clear sections per stock, then end with an overall portfolio summary."
        ),
    },
    {
        "name": "peter_lynch",
        "command": "npx",
        "args": ["-y", "@fre4x/yahoo-finance@1.1.0"],
        "section_title": "Peter Lynch — GARP Scorecard",
        "analysis_prompt": (
            "You are applying Peter Lynch's GARP (Growth at a Reasonable Price) framework from "
            "'One Up on Wall Street' and 'Beating the Street'. "
            "Use the Yahoo Finance tools to fetch real data for every stock holding, then score each one.\n\n"
            "For each stock position, use get_stock_info and get_financial_statement to retrieve:\n"
            "  - Trailing P/E and forward P/E\n"
            "  - EPS (trailing twelve months) and EPS growth rate (use earningsGrowth or compare income statements)\n"
            "  - Total debt and total cash (from balance sheet)\n"
            "  - Debt-to-equity ratio\n"
            "  - Revenue growth year-over-year\n"
            "  - Return on equity\n\n"
            "For options and funds, use get_stock_info on the underlying ticker where applicable; "
            "skip or note 'N/A — derivative' otherwise.\n\n"
            "Produce exactly these sections:\n\n"
            "1. **Lynch Category Classification** — classify each stock as one of Lynch's six types:\n"
            "   - Slow Grower (large, mature, earnings growth <5% p.a.)\n"
            "   - Stalwart (large but still growing 5–12% p.a., defensive)\n"
            "   - Fast Grower (small/mid, earnings growth >15% p.a., Lynch's favourite)\n"
            "   - Cyclical (profits tied to economic cycle: auto, commodity, airline)\n"
            "   - Turnaround (distressed, loss-making, recovery play)\n"
            "   - Asset Play (hidden assets — real estate, cash, IP — not reflected in price)\n"
            "   Present as a table: Symbol | Category | One-line rationale\n\n"
            "2. **PEG Ratio Scorecard** — for each stock, calculate PEG = (Trailing P/E) ÷ (annual EPS growth %).\n"
            "   Lynch's rule: PEG < 1 = attractive, PEG 1–2 = fairly valued, PEG > 2 = expensive.\n"
            "   If P/E or growth is negative, flag as 'N/A — unprofitable' or 'N/A — declining earnings'.\n"
            "   Present as a table: Symbol | P/E | EPS Growth % | PEG | Lynch Signal\n\n"
            "3. **Balance Sheet Health** — for each stock:\n"
            "   - Debt-to-equity: Lynch preferred D/E < 0.3 for most companies\n"
            "   - Net cash position (cash − total debt): positive = fortress, negative = leveraged\n"
            "   - Flag any position where debt is a serious concern\n"
            "   Present as a table: Symbol | D/E Ratio | Net Cash ($M) | Assessment\n\n"
            "4. **Ten-Bagger Candidates** — which Fast Growers or Turnarounds in the portfolio have "
            "the highest potential for 5–10x returns based on growth rate, market size, and current valuation? "
            "Rank the top 2–3 with a brief Lynch-style investment thesis for each.\n\n"
            "5. **Stocks to Avoid (Lynch's Warning Signs)** — flag any holdings that show:\n"
            "   - PEG > 2 with slowing growth\n"
            "   - High debt load funding a declining business\n"
            "   - 'Diworsification' — company expanding into unrelated businesses\n"
            "   - Whisper stocks (hyped story, no earnings)\n\n"
            "6. **Lynch Verdict** — one paragraph summary: which 2–3 stocks does Lynch's framework "
            "favour most strongly, and what is the single most important portfolio change Lynch would recommend?\n\n"
            "Ground every number in the data you retrieved. Show fetched values, not estimates."
        ),
    },
    # To add a new MCP server, copy and paste this block:
    # {
    #     "name": "my_server",
    #     "command": "npx",
    #     "args": ["-y", "my-mcp-package@x.y.z"],
    #     "section_title": "My Server Analysis",
    #     "analysis_prompt": "Your prompt here...",
    # },
]
