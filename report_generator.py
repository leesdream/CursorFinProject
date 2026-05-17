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
        rows += f"""
        <tr>
          <td><strong>{p.symbol}</strong>{ccy_badge}<br><small class="text-muted">{p.name[:30]}</small></td>
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


def _render_sections(sections: dict[str, str], header_class: str, analysis_date: str = "") -> str:
    if not sections:
        return ""
    html = ""
    date_badge = (
        f'<span class="badge rounded-pill bg-light text-dark fw-normal ms-2" style="font-size:.7rem">'
        f'cached {analysis_date}</span>'
    ) if analysis_date else ""
    for i, (title, content) in enumerate(sections.items()):
        section_id = "sec-" + "".join(c if c.isalnum() else "-" for c in title).lower()
        paragraphs = "".join(
            f"<p>{line}</p>" if line.strip() else ""
            for line in content.split("\n")
        )
        html += f"""
    <div class="card shadow-sm mb-4">
      <button type="button"
              class="card-header {header_class} border-0 d-flex justify-content-between align-items-center section-toggle"
              data-bs-toggle="collapse" data-bs-target="#{section_id}" aria-expanded="true">
        <h5 class="mb-0">{title}{date_badge}</h5>
        <span class="chevron">&#9660;</span>
      </button>
      <div id="{section_id}" class="collapse show">
        <div class="card-body">
          <div class="analysis-content">{paragraphs}</div>
        </div>
      </div>
    </div>"""
    return html


def _chart_data(portfolio: Portfolio) -> str:
    stocks = portfolio.stocks
    if not stocks:
        return "null"
    labels = [p.symbol for p in stocks]
    values = [round(p.market_value, 2) for p in stocks]
    return json.dumps({"labels": labels, "values": values})


def build_report(
    portfolio: Portfolio,
    mcp_sections: dict[str, str],
    philosophy_sections: dict[str, str],
    analysis_date: str = "",
    output_path: str = "report.html",
) -> str:
    o = portfolio.overview
    total_change = o.ending_total - o.beginning_total
    total_change_cls = _pnl_class(total_change)
    pnl_total = portfolio.total_unrealized_pnl
    chart_data = _chart_data(portfolio)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
  <style>
    body {{ background: #f8f9fa; }}
    .stat-card {{ border-left: 4px solid #0d6efd; }}
    .analysis-content p {{ margin-bottom: .4rem; line-height: 1.6; }}
    .hero {{ background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%); color: #fff; padding: 2rem; border-radius: .5rem; margin-bottom: 1.5rem; }}
    button.card-header {{ width: 100%; text-align: left; cursor: pointer; }}
    button.card-header:focus {{ outline: none; box-shadow: none; }}
    .section-toggle .chevron {{ transition: transform 0.25s ease; display: inline-block; opacity: .85; }}
    .section-toggle.collapsed .chevron {{ transform: rotate(-90deg); }}
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

  <!-- MCP analysis sections (one per server) -->
  {_render_sections(mcp_sections, "bg-primary text-white", analysis_date)}

  <!-- Philosophy analysis sections -->
  {_render_sections(philosophy_sections, "bg-dark text-white", analysis_date)}

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
</script>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
