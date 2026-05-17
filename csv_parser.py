"""
Parser for Tiger Brokers hierarchical activity statement CSVs.
Format: Statement_<account>_<YYYYMMDD>.csv

Row structure: [section, sub_type, sub2, row_type, col0, col1, ...]
  row_type: DATA = data row | TOTAL = subtotal (skip) | HEADER_DATA = labelled data | "" = column header
"""

import csv
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Position:
    symbol: str
    name: str
    quantity: float
    cost_price: float
    close_price: float
    market_value: float
    unrealized_pnl: float
    currency: str
    asset_type: str  # stock | option | fund


@dataclass
class Trade:
    date: str
    symbol: str
    name: str
    quantity: float
    price: float
    amount: float
    fees: float
    action: str  # buy | sell


@dataclass
class Overview:
    beginning_total: float
    ending_total: float
    beginning_cash: float
    ending_cash: float
    beginning_stock: float
    ending_stock: float
    beginning_options: float
    ending_options: float
    beginning_funds: float
    ending_funds: float


@dataclass
class Portfolio:
    account_number: str
    account_holder: str
    statement_date: str
    broker: str
    base_currency: str
    overview: Overview = field(default_factory=lambda: Overview(0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    positions: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    fx_rates: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @property
    def stocks(self):
        return [p for p in self.positions if p.asset_type == "stock"]

    @property
    def options(self):
        return [p for p in self.positions if p.asset_type == "option"]

    @property
    def funds(self):
        return [p for p in self.positions if p.asset_type == "fund"]

    @property
    def total_unrealized_pnl(self):
        return sum(p.unrealized_pnl for p in self.positions)


def _n(val: str) -> float:
    """Parse a number string: strips $, commas, parentheses (negative)."""
    if not val:
        return 0.0
    v = val.strip().replace(",", "").replace("$", "").replace("HK$", "").replace("S$", "")
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]
    try:
        return float(v)
    except ValueError:
        return 0.0


def _read_rows(path: Path) -> list[list[str]]:
    """Read CSV with BOM handling and multiple encoding fallbacks."""
    for enc in ("utf-8-sig", "utf-16", "gbk", "latin-1"):
        try:
            with open(path, encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            # Strip any lingering BOM from first cell
            if rows and rows[0] and rows[0][0].startswith("﻿"):
                rows[0][0] = rows[0][0].lstrip("﻿")
            return rows
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Final fallback
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.reader(f))


def _section_rows(rows, section: str, sub_type: str = None, row_type: str = "DATA"):
    """
    Yield rows matching section (col0) and optionally sub_type (col1) and row_type (col3).
    Tiger CSV: col0=section, col1=sub_type, col2=sub2, col3=row_type, col4...=data
    """
    for row in rows:
        if len(row) < 4:
            continue
        if row[0].strip() != section:
            continue
        if row_type is not None and row[3].strip() != row_type:
            continue
        if sub_type is not None and row[1].strip().lower() != sub_type.lower():
            continue
        yield row


def _parse_meta(rows) -> dict:
    meta = {"account_holder": "", "account_number": "", "broker": "Tiger Brokers", "base_currency": "USD", "statement_date": ""}
    for row in rows:
        if len(row) < 2:
            continue
        key = row[0].strip().lower()
        val = row[4].strip() if len(row) > 4 else (row[1].strip() if len(row) > 1 else "")
        if key == "name" and not meta["account_holder"]:
            meta["account_holder"] = val
        elif key == "account information" and len(row) > 4 and row[3].strip() == "DATA":
            if not meta["account_number"]:
                meta["account_number"] = row[4].strip()
            if len(row) > 7:
                meta["base_currency"] = row[7].strip() or "USD"
        elif "activity statement" in key and len(row) > 4:
            meta["statement_date"] = row[4].strip()
    return meta


def _parse_overview(rows) -> Overview:
    # Row: Account Overview,,,DATA,<period>,cash,stock,option,fund,transit,interest,dividend,total
    beg = {}
    end = {}
    for row in _section_rows(rows, "Account Overview", row_type="DATA"):
        period = row[4].strip().lower() if len(row) > 4 else ""
        values = row[5:] if len(row) > 5 else []
        target = beg if "beginning" in period else (end if "end" in period else None)
        if target is None or len(values) < 8:
            continue
        target["cash"] = _n(values[0])
        target["stock"] = _n(values[1])
        target["option"] = _n(values[2])
        target["fund"] = _n(values[3])
        target["total"] = _n(values[7])
    return Overview(
        beginning_total=beg.get("total", 0),
        ending_total=end.get("total", 0),
        beginning_cash=beg.get("cash", 0),
        ending_cash=end.get("cash", 0),
        beginning_stock=beg.get("stock", 0),
        ending_stock=end.get("stock", 0),
        beginning_options=beg.get("option", 0),
        ending_options=end.get("option", 0),
        beginning_funds=beg.get("fund", 0),
        ending_funds=end.get("fund", 0),
    )


def _parse_trades(rows) -> list[Trade]:
    # Header: Trades,,,,Symbol,Market,Exchange,Activity Type,Quantity,Trade Price,Amount,...
    # Data:   Trades,Stock,,DATA,<name> (<symbol>),<market>,...,<qty>,<price>,<amount>,...
    trades = []
    # Find header row (col3 empty, col4="Symbol")
    header = None
    for row in rows:
        if row[0].strip() != "Trades":
            continue
        if row[3].strip() == "" and len(row) > 4 and row[4].strip().lower() == "symbol":
            header = [c.strip().lower().replace(" ", "_").replace("/", "_") for c in row[4:]]
            break

    if not header:
        return trades

    for row in _section_rows(rows, "Trades", row_type="DATA"):
        data = row[4:]
        if len(data) < len(header):
            data += [""] * (len(header) - len(data))
        d = dict(zip(header, data))

        # Symbol is "Name (TICKER)" — extract ticker from parentheses
        raw_sym = d.get("symbol", "").strip()
        m = re.search(r"\(([^)]+)\)\s*$", raw_sym)
        ticker = m.group(1) if m else raw_sym
        name = re.sub(r"\s*\([^)]+\)\s*$", "", raw_sym).strip()

        qty = _n(d.get("quantity", "0"))
        activity = d.get("activity_type", "").lower()
        action = "sell" if qty < 0 or "close" in activity else "buy"

        # Fees: sum of all fee/commission columns
        fee_cols = [k for k in header if any(x in k for x in ("commission", "fee", "gst", "tax", "settlement"))]
        fees = sum(abs(_n(d.get(c, "0"))) for c in fee_cols)

        # Date: look for a column named "trade_date_time" or "date_time"
        date_col = next((k for k in header if "date" in k), "")
        date_val = d.get(date_col, "").strip()

        trades.append(Trade(
            date=date_val,
            symbol=ticker,
            name=name,
            quantity=abs(qty),
            price=_n(d.get("trade_price", "0")),
            amount=abs(_n(d.get("amount", "0"))),
            fees=fees,
            action=action,
        ))
    return trades


def _parse_holdings(rows, fx_rates: dict) -> list[Position]:
    positions = []

    # Holdings has three header rows (one per asset type) and DATA rows interleaved.
    # We process each sub_type separately using its own header.
    for sub_type, asset_type in [("Option", "option"), ("Fund", "fund"), ("Stock", "stock")]:
        # Find the column header row for this sub_type:
        # It's the last row before DATA rows where col0=Holdings, col1 empty or sub_type, col3=""
        header = None
        for row in rows:
            if row[0].strip() != "Holdings":
                continue
            col1 = row[1].strip()
            col3 = row[3].strip()
            col4 = row[4].strip() if len(row) > 4 else ""
            # Column header rows: col3 is empty and col4 looks like "Symbol"
            if col3 == "" and col4.lower() == "symbol":
                header = [c.strip().lower().replace(" ", "_").replace("/", "_") for c in row[4:]]
            # When we hit a DATA row for this sub_type, stop updating header
            if col1 == sub_type and col3 == "DATA":
                break

        if not header:
            continue

        for row in _section_rows(rows, "Holdings", sub_type=sub_type, row_type="DATA"):
            data = row[4:]
            if len(data) < len(header):
                data += [""] * (len(header) - len(data))
            d = dict(zip(header, data))

            raw_sym = d.get("symbol", "").strip()
            if not raw_sym or raw_sym.lower().startswith("total"):
                continue

            # For options/stocks, extract ticker from parentheses
            m = re.search(r"\(([^)]+)\)\s*$", raw_sym)
            if m:
                ticker = m.group(1)
                name = re.sub(r"\s*\([^)]+\)\s*$", "", raw_sym).strip()
            else:
                ticker = raw_sym
                name = raw_sym

            qty = _n(d.get("quantity", "0"))
            cost = _n(d.get("cost_price", "0"))
            close = _n(d.get("close_price", "0"))
            value = _n(d.get("value", "0"))
            pnl = _n(d.get("unrealized_p_l", d.get("unrealized_pl", "0")))
            currency = d.get("currency", "USD").strip() or "USD"

            # Convert non-USD market values to USD using fx rates
            rate = fx_rates.get(currency, 1.0)
            value_usd = value * rate if currency != "USD" else value
            pnl_usd = pnl * rate if currency != "USD" else pnl

            positions.append(Position(
                symbol=ticker,
                name=name,
                quantity=qty,
                cost_price=cost,
                close_price=close,
                market_value=value_usd,
                unrealized_pnl=pnl_usd,
                currency=currency,
                asset_type=asset_type,
            ))

    return positions


def _parse_fx_rates(rows) -> dict:
    # Section is "Base Currency Exchange Rate", row_type HEADER_DATA, col4=currency, col5=rate-to-USD
    rates = {}
    for row in rows:
        if row[0].strip() != "Base Currency Exchange Rate":
            continue
        if row[3].strip() != "HEADER_DATA":
            continue
        if len(row) < 6:
            continue
        currency = row[4].strip()
        try:
            rates[currency] = float(row[5].strip())
        except (ValueError, IndexError):
            pass
    return rates


def parse_latest_statement(folder: str) -> Portfolio:
    """Find the most recent Statement_*.csv and parse it."""
    csv_files = sorted(Path(folder).glob("Statement_*.csv"), reverse=True)
    if not csv_files:
        raise FileNotFoundError(f"No Statement_*.csv files found in {folder!r}")

    path = csv_files[0]
    rows = _read_rows(path)

    # Pad all rows to at least 5 columns to avoid index errors
    rows = [r + [""] * max(0, 5 - len(r)) for r in rows]

    meta = _parse_meta(rows)

    # Statement date from filename if not found in file
    if not meta["statement_date"]:
        m = re.search(r"(\d{8})", path.stem)
        if m:
            d = m.group(1)
            meta["statement_date"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"

    fx_rates = _parse_fx_rates(rows)
    overview = _parse_overview(rows)
    trades = _parse_trades(rows)
    positions = _parse_holdings(rows, fx_rates)

    return Portfolio(
        account_number=meta["account_number"],
        account_holder=meta["account_holder"],
        statement_date=meta["statement_date"],
        broker=meta["broker"],
        base_currency=meta["base_currency"],
        overview=overview,
        positions=positions,
        trades=trades,
        fx_rates=fx_rates,
    )
