"""Generates a self-contained HTML portfolio report."""

import json
from datetime import datetime
from pathlib import Path

from csv_parser import Portfolio


def _pnl_class(value: float) -> str:
    if value > 0:
        return "text-success"
    if value < 0:
        return "text-danger"
    return "text-muted"


def _fmt_usd(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}"


def _fmt_plain(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


def _holdings_table(positions, title: str) -> str:
    if not positions:
        return ""
    rows = ""
    for p in positions:
        pnl_cls = _pnl_class(p.unrealized_pnl)
        cost_total = p.cost_price * abs(p.quantity)
        pnl_pct = (p.unrealized_pnl / cost_total * 100) if cost_total else 0
        # Show original-currency price with badge if non-USD, USD value always in market value column
        ccy_badge = f'<span class="badge bg-secondary ms-1">{p.currency}</span>' if p.currency != "USD" else ""
        spread_line = f'<br><small class="text-info">{p.spread_label}</small>' if getattr(p, "spread_label", "") else ""
        rows += f"""
        <tr>
          <td><strong>{p.symbol}</strong>{ccy_badge}<br><small class="text-muted">{p.name[:30]}</small>{spread_line}</td>
          <td class="text-end">{_fmt_plain(p.quantity)}</td>
          <td class="text-end">{p.currency} {_fmt_plain(p.cost_price)}</td>
          <td class="text-end">{p.currency} {_fmt_plain(p.close_price)}</td>
          <td class="text-end">${_fmt_plain(p.market_value)}<br><small class="text-muted">USD</small></td>
          <td class="text-end {pnl_cls}">{_fmt_usd(p.unrealized_pnl)}<br>
            <small>({'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%)</small>
          </td>
        </tr>"""
    return f"""
    <h5 class="mt-4 mb-2">{title}</h5>
    <div class="table-responsive">
      <table class="table table-sm table-hover">
        <thead class="table-light">
          <tr>
            <th>Symbol</th>
            <th class="text-end">Qty</th>
            <th class="text-end">Avg Cost</th>
            <th class="text-end">Last Price</th>
            <th class="text-end">Market Value</th>
            <th class="text-end">Unrealized P&amp;L</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


def _trades_table(trades) -> str:
    if not trades:
        return "<p class='text-muted'>No trades in this period.</p>"
    rows = ""
    for t in trades:
        badge = "success" if t.action == "buy" else "danger"
        rows += f"""
        <tr>
          <td>{t.date}</td>
          <td><span class="badge bg-{badge}">{t.action.upper()}</span></td>
          <td><strong>{t.symbol}</strong></td>
          <td class="text-end">{_fmt_plain(t.quantity)}</td>
          <td class="text-end">${_fmt_plain(t.price)}</td>
          <td class="text-end">${_fmt_plain(t.amount)}</td>
          <td class="text-end text-danger">{_fmt_usd(-t.fees)}</td>
        </tr>"""
    return f"""
    <div class="table-responsive">
      <table class="table table-sm">
        <thead class="table-light">
          <tr>
            <th>Date</th><th>Action</th><th>Symbol</th>
            <th class="text-end">Qty</th><th class="text-end">Price</th>
            <th class="text-end">Amount</th><th class="text-end">Fees</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


def _md_to_html(text: str) -> str:
    import markdown as md_lib
    html = md_lib.markdown(text, extensions=["tables", "nl2br"])
    html = (
        html
        .replace(
            "<table>",
            '<div class="table-responsive"><table class="table table-sm table-striped table-bordered align-middle">',
        )
        .replace("</table>", "</table></div>")
        .replace(
            "<blockquote>",
            '<blockquote class="border-start border-3 border-secondary ps-3 text-muted my-3">',
        )
    )
    return html


def _analysis_tabs(
    mcp_sections: dict[str, str],
    philosophy_sections: dict[str, str],
    synthesis_section: dict[str, str],
    analysis_date: str,
) -> str:
    # Synthesis first, then MCP, then philosophy
    all_sections: dict[str, str] = {**synthesis_section, **mcp_sections, **philosophy_sections}
    date_badge = (
        f'<span class="badge bg-secondary fw-normal ms-3" style="font-size:.72rem">'
        f'cached {analysis_date}</span>'
    ) if analysis_date else ""

    synthesis_titles = set(synthesis_section.keys())

    tab_nav = ""
    tab_panes = ""
    for i, (title, content) in enumerate(all_sections.items()):
        tab_id = "tab-" + "".join(c if c.isalnum() else "-" for c in title).lower()
        short = title.split("—")[0].split(" Analysis")[0].strip()
        active = "active" if i == 0 else ""
        show_active = "show active" if i == 0 else ""

        if title in synthesis_titles:
            # Synthesis tab gets amber accent
            tab_nav += f"""
        <li class="nav-item" role="presentation">
          <button class="nav-link synthesis-tab {active} px-3 py-2" data-bs-toggle="tab"
                  data-bs-target="#{tab_id}" type="button" role="tab">&#9733; {short}</button>
        </li>"""
        else:
            tab_nav += f"""
        <li class="nav-item" role="presentation">
          <button class="nav-link {active} px-3 py-2" data-bs-toggle="tab"
                  data-bs-target="#{tab_id}" type="button" role="tab">{short}</button>
        </li>"""

        tab_panes += f"""
        <div class="tab-pane fade {show_active}" id="{tab_id}" role="tabpanel">
          <div class="analysis-content">{_md_to_html(content)}</div>
        </div>"""

    # Trade Planner — always the last tab; interactive, powered by trade_advisor.py
    tab_nav += """
        <li class="nav-item" role="presentation">
          <button class="nav-link px-3 py-2" data-bs-toggle="tab"
                  data-bs-target="#tab-trade-planner" type="button" role="tab">
            &#9998; Trade Planner</button>
        </li>"""
    tab_panes += """
        <div class="tab-pane fade" id="tab-trade-planner" role="tabpanel">
          <p class="text-muted small mb-3">
            Enter your planned trades for the next session. Analysis applies Lynch &middot; Marks &middot; Taleb
            &mdash; no live market data calls.
            <span class="text-warning">&#9888; Requires <code>main.py</code> to be running.</span>
          </p>
          <textarea id="tp-input" class="form-control mb-3" rows="6"
            placeholder="e.g.&#10;Buy 50 NVDA at ~$130&#10;Sell 2 SPY 750P Nov 2026&#10;Buy 1 AAPL 200C Jan 2027 at ~$5.50"></textarea>
          <div class="d-flex align-items-center gap-3 mb-3">
            <button id="tp-btn" class="btn btn-primary btn-sm" onclick="tpAnalyze()">Analyze Trades</button>
            <div id="tp-spinner" class="spinner-border spinner-border-sm text-primary d-none" role="status"></div>
            <span id="tp-status" class="text-muted small"></span>
          </div>
          <div id="tp-result" class="analysis-content border-top pt-3 d-none"></div>
        </div>"""

    return f"""
  <div class="card shadow-sm mb-4">
    <div class="card-header d-flex align-items-center">
      <ul class="nav nav-tabs card-header-tabs flex-grow-1 mb-0" role="tablist">
        {tab_nav}
      </ul>
      {date_badge}
    </div>
    <div class="card-body p-4">
      <div class="tab-content">
        {tab_panes}
      </div>
    </div>
  </div>"""


def _portfolio_text_summary(portfolio: Portfolio) -> str:
    lines = [
        f"Statement: {portfolio.statement_date}",
        f"Total value: ${portfolio.overview.ending_total:,.2f}",
        f"Cash: ${portfolio.overview.ending_cash:,.2f}",
        f"Stocks: ${portfolio.overview.ending_stock:,.2f}",
        f"Options: ${portfolio.overview.ending_options:,.2f}",
        "",
        "Holdings:",
    ]
    for p in portfolio.stocks:
        lines.append(
            f"  {p.symbol} {p.quantity:+.0f}sh | cost {p.currency}{p.cost_price:.2f}"
            f" | last {p.currency}{p.close_price:.2f} | value ${p.market_value:,.0f}"
            f" | P&L {'+'if p.unrealized_pnl>=0 else ''}{p.unrealized_pnl:,.0f}"
        )
    for p in portfolio.options:
        label = getattr(p, "spread_label", "") or ""
        note = f" [{label}]" if label else ""
        lines.append(
            f"  {p.symbol}{note} {p.quantity:+.0f}ct | cost {p.currency}{p.cost_price:.2f}"
            f" | last {p.currency}{p.close_price:.2f}"
            f" | P&L {'+'if p.unrealized_pnl>=0 else ''}{p.unrealized_pnl:,.0f}"
        )
    for p in portfolio.funds:
        lines.append(
            f"  {p.symbol} (fund) {p.quantity:+.0f}sh | value ${p.market_value:,.0f}"
        )
    return "\n".join(lines)


def _chart_data(portfolio: Portfolio) -> str:
    stocks = portfolio.stocks
    if not stocks:
        return "null"
    labels = [p.symbol for p in stocks]
    values = [round(p.market_value, 2) for p in stocks]
    return json.dumps({"labels": labels, "values": values})


_TP_SCRIPT = """\
const TP_PORTFOLIO = TP_SUMMARY_PLACEHOLDER;
async function tpAnalyze() {
  const trades = document.getElementById('tp-input').value.trim();
  if (!trades) {
    document.getElementById('tp-status').textContent = 'Enter at least one trade.';
    return;
  }
  const btn = document.getElementById('tp-btn');
  const spinner = document.getElementById('tp-spinner');
  const status = document.getElementById('tp-status');
  const result = document.getElementById('tp-result');
  btn.disabled = true;
  spinner.classList.remove('d-none');
  status.textContent = 'Analyzing — 1 Claude call, ~10 sec…';
  result.classList.add('d-none');
  try {
    const resp = await fetch('http://localhost:7823/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trades: trades, portfolio: TP_PORTFOLIO }),
    });
    if (!resp.ok) throw new Error('Server returned ' + resp.status);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    result.innerHTML = marked.parse(data.analysis);
    result.classList.remove('d-none');
    status.textContent = '';
  } catch (err) {
    status.textContent = 'Error: ' + err.message + ' — is main.py still running?';
    status.className = 'text-danger small';
  } finally {
    btn.disabled = false;
    spinner.classList.add('d-none');
  }
}
"""


def build_report(
    portfolio: Portfolio,
    mcp_sections: dict[str, str],
    philosophy_sections: dict[str, str],
    synthesis_section: dict[str, str] | None = None,
    analysis_date: str = "",
    output_path: str = "report.html",
) -> str:
    if synthesis_section is None:
        synthesis_section = {}
    o = portfolio.overview
    total_change = o.ending_total - o.beginning_total
    total_change_cls = _pnl_class(total_change)
    pnl_total = portfolio.total_unrealized_pnl
    chart_data = _chart_data(portfolio)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tp_script = _TP_SCRIPT.replace(
        "TP_SUMMARY_PLACEHOLDER", json.dumps(_portfolio_text_summary(portfolio))
    )

    holdings_html = (
        _holdings_table(portfolio.stocks, "Stocks")
        + _holdings_table(portfolio.options, "Options")
        + _holdings_table(portfolio.funds, "Funds")
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Portfolio Report — {portfolio.statement_date}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked@9.1.6/marked.min.js"></script>
  <style>
    body {{ background: #f8f9fa; }}
    .stat-card {{ border-left: 4px solid #0d6efd; }}
    .hero {{ background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%); color: #fff; padding: 2rem; border-radius: .5rem; margin-bottom: 1.5rem; }}
    /* Markdown content styles */
    .analysis-content h1 {{ font-size: 1.35rem; margin-top: 1.5rem; margin-bottom: .5rem; }}
    .analysis-content h2 {{ font-size: 1.15rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: .4rem; padding-bottom: .3rem; border-bottom: 1px solid #dee2e6; }}
    .analysis-content h3 {{ font-size: 1.0rem; font-weight: 600; margin-top: 1.1rem; margin-bottom: .25rem; color: #495057; }}
    .analysis-content p {{ margin-bottom: .5rem; line-height: 1.7; }}
    .analysis-content ul, .analysis-content ol {{ padding-left: 1.5rem; margin-bottom: .75rem; }}
    .analysis-content li {{ margin-bottom: .2rem; line-height: 1.65; }}
    .analysis-content hr {{ margin: 1.5rem 0; border-color: #dee2e6; }}
    .analysis-content strong {{ color: #212529; }}
    .analysis-content blockquote p {{ margin-bottom: 0; font-style: italic; }}
    .analysis-content .table {{ font-size: .875rem; }}
    .nav-tabs .nav-link {{ color: #495057; }}
    .nav-tabs .nav-link.active {{ font-weight: 600; }}
    .nav-tabs .synthesis-tab {{ color: #b45309; font-weight: 600; }}
    .nav-tabs .synthesis-tab.active {{ color: #92400e; background: #fffbeb; border-bottom-color: #fffbeb; }}
  </style>
</head>
<body>
<div class="container py-4">

  <!-- Header -->
  <div class="hero">
    <div class="row align-items-center">
      <div class="col">
        <h2 class="mb-0">Portfolio Report</h2>
        <p class="mb-0 opacity-75">{portfolio.account_holder} &middot; Account {portfolio.account_number} &middot; {portfolio.broker}</p>
      </div>
      <div class="col-auto text-end">
        <h3 class="mb-0">${o.ending_total:,.2f}</h3>
        <p class="mb-0 opacity-75">Total Value as of {portfolio.statement_date}</p>
      </div>
    </div>
  </div>

  <!-- Summary cards -->
  <div class="row g-3 mb-4">
    <div class="col-sm-6 col-lg-3">
      <div class="card shadow-sm stat-card h-100">
        <div class="card-body">
          <div class="text-muted small">Period Change</div>
          <div class="h4 {total_change_cls}">{_fmt_usd(total_change)}</div>
        </div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="card shadow-sm stat-card h-100">
        <div class="card-body">
          <div class="text-muted small">Unrealized P&amp;L</div>
          <div class="h4 {_pnl_class(pnl_total)}">{_fmt_usd(pnl_total)}</div>
        </div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="card shadow-sm stat-card h-100">
        <div class="card-body">
          <div class="text-muted small">Cash (Base)</div>
          <div class="h4">${o.ending_cash:,.2f}</div>
        </div>
      </div>
    </div>
    <div class="col-sm-6 col-lg-3">
      <div class="card shadow-sm stat-card h-100">
        <div class="card-body">
          <div class="text-muted small">Equity + Options</div>
          <div class="h4">${o.ending_stock + o.ending_options:,.2f}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Holdings + Chart -->
  <div class="row g-4 mb-4">
    <div class="col-lg-8">
      <div class="card shadow-sm">
        <div class="card-header"><h5 class="mb-0">Holdings</h5></div>
        <div class="card-body">
          {holdings_html}
        </div>
      </div>
    </div>
    <div class="col-lg-4">
      <div class="card shadow-sm">
        <div class="card-header"><h5 class="mb-0">Stock Allocation</h5></div>
        <div class="card-body d-flex align-items-center justify-content-center" style="min-height:320px">
          <canvas id="allocationChart"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- Trades -->
  <div class="card shadow-sm mb-4">
    <div class="card-header"><h5 class="mb-0">Trades This Period</h5></div>
    <div class="card-body">
      {_trades_table(portfolio.trades)}
    </div>
  </div>

  <!-- Analysis tabs: Synthesis · Yahoo Finance · Howard Marks · Taleb -->
  {_analysis_tabs(mcp_sections, philosophy_sections, synthesis_section, analysis_date)}

  <footer class="text-center text-muted small mt-4 pb-3">
    Generated {generated_at} &middot; Data source: {portfolio.broker} statement {portfolio.statement_date}
  </footer>
</div>

<script>
const chartData = {chart_data};
if (chartData) {{
  const COLORS = [
    '#0d6efd','#198754','#dc3545','#ffc107','#0dcaf0',
    '#6610f2','#fd7e14','#20c997','#6f42c1','#d63384','#0dcaf0','#adb5bd'
  ];
  new Chart(document.getElementById('allocationChart'), {{
    type: 'doughnut',
    data: {{
      labels: chartData.labels,
      datasets: [{{ data: chartData.values, backgroundColor: COLORS }}]
    }},
    options: {{
      plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 11 }} }} }} }},
      cutout: '60%'
    }}
  }});
}}
{tp_script}
</script>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
