"""Unit tests for csv_parser — overview layout variations and spread detection."""

from csv_parser import _detect_spreads, _parse_option_contract, _parse_overview, Position


def _pad(rows):
    return [r + [""] * max(0, 5 - len(r)) for r in rows]


# ---------------------------------------------------------------------------
# Helpers that build synthetic row sets
# ---------------------------------------------------------------------------

def _overview_rows_with_options():
    """8-column layout: Cash, Stock, Option, Fund, Transit, Interest, Dividend, Total."""
    return _pad([
        ["Account Overview", "", "", "", "", "Cash", "Stock", "Option", "Fund",
         "Funds in Transit", "Interest Accruals", "Dividend Accruals", "Total"],
        ["Account Overview", "", "", "DATA", "Beginning Of The Period",
         "10,000.00", "50,000.00", "1,500.00", "200.00", "0.00", "0.00", "0.00", "61,700.00"],
        ["Account Overview", "", "", "DATA", "End Of The Period",
         "12,000.00", "55,000.00", "2,000.00", "210.00", "0.00", "0.00", "50.00", "69,260.00"],
    ])


def _overview_rows_without_options():
    """7-column layout: Cash, Stock, Fund, Transit, Interest, Dividend, Total (no Option)."""
    return _pad([
        ["Account Overview", "", "", "", "", "Cash", "Stock", "Fund",
         "Funds in Transit", "Interest Accruals", "Dividend Accruals", "Total"],
        ["Account Overview", "", "", "DATA", "Beginning Of The Period",
         "41,219.21", "164,317.46", "34.23", "0.00", "-1.32", "238.39", "205,807.97"],
        ["Account Overview", "", "", "DATA", "End Of The Period",
         "51,492.43", "152,829.54", "34.54", "0.00", "-1.32", "238.39", "204,593.57"],
    ])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_with_options_totals():
    o = _parse_overview(_overview_rows_with_options())
    assert o.beginning_total == 61_700.00
    assert o.ending_total == 69_260.00


def test_with_options_breakdown():
    o = _parse_overview(_overview_rows_with_options())
    assert o.beginning_cash == 10_000.00
    assert o.beginning_stock == 50_000.00
    assert o.beginning_options == 1_500.00
    assert o.beginning_funds == 200.00
    assert o.ending_cash == 12_000.00
    assert o.ending_stock == 55_000.00
    assert o.ending_options == 2_000.00
    assert o.ending_funds == 210.00


def test_without_options_totals():
    o = _parse_overview(_overview_rows_without_options())
    assert o.beginning_total == 205_807.97
    assert o.ending_total == 204_593.57


def test_without_options_breakdown():
    o = _parse_overview(_overview_rows_without_options())
    assert o.beginning_cash == 41_219.21
    assert o.beginning_stock == 164_317.46
    assert o.beginning_options == 0.0  # column absent → zero
    assert o.beginning_funds == 34.23
    assert o.ending_cash == 51_492.43
    assert o.ending_stock == 152_829.54
    assert o.ending_options == 0.0
    assert o.ending_funds == 34.54


def test_without_options_no_zeros_for_present_fields():
    """Regression: the old len(values)<8 guard zeroed everything when Option was absent."""
    o = _parse_overview(_overview_rows_without_options())
    assert o.ending_total != 0
    assert o.ending_cash != 0
    assert o.ending_stock != 0


def test_empty_rows_returns_zeros():
    o = _parse_overview([])
    assert o.beginning_total == 0
    assert o.ending_total == 0


# ---------------------------------------------------------------------------
# Spread detection tests
# ---------------------------------------------------------------------------

def _make_option(symbol, quantity):
    return Position(symbol=symbol, name="", quantity=quantity, cost_price=0,
                    close_price=0, market_value=0, unrealized_pnl=0,
                    currency="USD", asset_type="option")


def test_parse_option_contract():
    assert _parse_option_contract("SPY 20261120 PUT 700.0") == ("SPY", "20261120", "PUT", 700.0)
    assert _parse_option_contract("AAPL 20261220 CALL 200.0") == ("AAPL", "20261220", "CALL", 200.0)
    assert _parse_option_contract("not an option") is None


def test_bear_put_spread_detection():
    """Long higher-strike put + short lower-strike put = bear put spread."""
    long_750 = _make_option("SPY 20261120 PUT 750.0", +2)
    short_700 = _make_option("SPY 20261120 PUT 700.0", -2)
    _detect_spreads([long_750, short_700])
    assert "bear put spread" in long_750.spread_label
    assert "long 750" in long_750.spread_label
    assert "bear put spread" in short_700.spread_label
    assert "short 700" in short_700.spread_label
    assert "750/700" in long_750.spread_label
    assert "750/700" in short_700.spread_label


def test_bull_put_spread_detection():
    """Long lower-strike put + short higher-strike put = bull put spread."""
    long_700 = _make_option("SPY 20261120 PUT 700.0", +2)
    short_750 = _make_option("SPY 20261120 PUT 750.0", -2)
    _detect_spreads([long_700, short_750])
    assert "bull put spread" in long_700.spread_label
    assert "bull put spread" in short_750.spread_label


def test_bull_call_spread_detection():
    """Long lower-strike call + short higher-strike call = bull call spread."""
    long_200 = _make_option("AAPL 20261220 CALL 200.0", +1)
    short_220 = _make_option("AAPL 20261220 CALL 220.0", -1)
    _detect_spreads([long_200, short_220])
    assert "bull call spread" in long_200.spread_label
    assert "bull call spread" in short_220.spread_label


def test_bear_call_spread_detection():
    """Long higher-strike call + short lower-strike call = bear call spread."""
    long_220 = _make_option("AAPL 20261220 CALL 220.0", +1)
    short_200 = _make_option("AAPL 20261220 CALL 200.0", -1)
    _detect_spreads([long_220, short_200])
    assert "bear call spread" in long_220.spread_label
    assert "bear call spread" in short_200.spread_label


def test_mismatched_quantity_not_paired():
    """Legs with different abs quantities are not treated as a spread."""
    long_750 = _make_option("SPY 20261120 PUT 750.0", +3)
    short_700 = _make_option("SPY 20261120 PUT 700.0", -2)
    _detect_spreads([long_750, short_700])
    assert long_750.spread_label == ""
    assert short_700.spread_label == ""


def test_different_expiry_not_paired():
    """Same strikes but different expiry dates are not a spread."""
    long_750 = _make_option("SPY 20261120 PUT 750.0", +2)
    short_700 = _make_option("SPY 20261220 PUT 700.0", -2)
    _detect_spreads([long_750, short_700])
    assert long_750.spread_label == ""
    assert short_700.spread_label == ""


def test_stocks_unaffected():
    """Stock positions are left untouched."""
    stock = Position(symbol="AAPL", name="Apple", quantity=10, cost_price=150,
                     close_price=200, market_value=2000, unrealized_pnl=500,
                     currency="USD", asset_type="stock")
    _detect_spreads([stock])
    assert stock.spread_label == ""


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
