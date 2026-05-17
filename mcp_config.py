MCP_SERVERS = [
    {
        "name": "yahoo_finance",
        "command": "npx",
        "args": ["-y", "@fre4x/yahoo-finance"],
        "section_title": "Yahoo Finance Analysis",
        "analysis_prompt": (
            "You have access to Yahoo Finance tools. For each stock in this portfolio, "
            "fetch the current price, 52-week high/low, and analyst consensus rating. "
            "Then provide 3-5 specific actionable recommendations (buy more / hold / trim / sell) "
            "for each position, citing the data you retrieved. "
            "Format your response in clear sections per stock, then end with an overall portfolio summary."
        ),
    },
    # To add a new MCP server, copy and paste this block:
    # {
    #     "name": "my_server",
    #     "command": "npx",
    #     "args": ["-y", "my-mcp-package"],
    #     "section_title": "My Server Analysis",
    #     "analysis_prompt": "Your prompt here...",
    # },
]
