# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Python CLI that reads a Tiger Brokers brokerage statement CSV, enriches it with live market data via MCP servers (Yahoo Finance, and future servers), and generates a self-contained HTML report that opens in the browser.

### How to run
```
.venv/Scripts/python.exe main.py
```
This produces `report.html` and opens it automatically.
Use forward slashes — they work in both PowerShell and bash (backslashes break in the bash tool).

### Architecture

```
main.py              # Entry point — orchestrates parse → MCP analysis → report → browser
csv_parser.py        # Parses Tiger Brokers hierarchical CSV into Portfolio dataclass
mcp_config.py        # Registry of MCP analysis servers (add new servers here)
report_generator.py  # Builds self-contained HTML (Bootstrap 5 + Chart.js via CDN)
financialstatement/  # Drop Tiger Brokers Statement_*.csv files here
.env                 # ANTHROPIC_API_KEY (gitignored)
requirements.txt     # anthropic, mcp, python-dotenv
```

### Adding a new MCP server
Copy the commented block in `mcp_config.py` — fill in `name`, `args`, `section_title`, and `analysis_prompt`. A new section appears in the report automatically, no other changes needed.

### Tiger Brokers CSV format
The CSV is hierarchical, not tabular. Each row: `[section, sub_type, sub2, row_type, data...]`
- `row_type` = `DATA` for actual data rows, `TOTAL` for subtotals (skipped), blank for column headers
- Sections: `Account Overview`, `Cash Report`, `Trades`, `Holdings`, `Currency Exchange Rates`
- Holdings sub_types: `Stock`, `Option`, `Fund`
- Encoding: UTF-8 with BOM (`utf-8-sig`)
- Filename pattern: `Statement_<account>_<YYYYMMDD>.csv` — app always loads the most recent

### MCP servers (user scope, global)
- `context7` — up-to-date library docs
- `playwright` — browser automation
- `yahoo-finance` — live stock quotes, analyst ratings, option chains (`@fre4x/yahoo-finance`)
- `filesystem` — file access (via `@modelcontextprotocol/server-filesystem`)

### Python environment
- Python 3.12 installed at `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`
- Virtual environment: `.venv\` (use `.venv\Scripts\python.exe` to run)

## Git & GitHub

Repository: https://github.com/leesdream/CursorFinProject

**Commit convention (Conventional Commits):**
- `feat:` — new feature
- `fix:` — bug fix
- `chore:` — tooling, config, dependencies
- `docs:` — documentation only
- `refactor:` — code restructure, no behavior change
- `test:` — adding or updating tests

Always commit with descriptive messages and push to keep the remote in sync:
```
git add <files>
git commit -m "feat: description of change"
git push
```

## Python Environment

Use a virtual environment in `.venv/` (excluded from git):
```
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements.txt
```

## Documentation

When asked to document or save analysis, always append to the existing relevant file (e.g., nextstep.md, reference/projectexplaination.md) rather than creating a new file unless explicitly told to.

## Financial Analysis

Frame portfolio and options analysis using the barbell/Taleb risk framework with live market data from the yahoo-finance MCP server.

## Tooling Fallbacks

When a browser/screenshot tool is unavailable, fall back to reading the generated HTML directly instead of failing.