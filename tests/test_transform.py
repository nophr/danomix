from scripts.parse import parse_flex_xml
from scripts.transform import build_holdings, compute_leverage
from tests.conftest import read_fixture


def test_holdings_sum_to_100():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    total = sum(h["percent"] for h in holdings)
    assert abs(total - 100.0) < 0.01


def test_holdings_sorted_descending():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    pcts = [h["percent"] for h in holdings]
    assert pcts == sorted(pcts, reverse=True)


def test_option_formatted_in_display():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    lumn = next(h for h in holdings if h["asset_class"] == "OPT")
    assert lumn["display"] == "LUMN Jan'27 $10C"
    assert lumn["option"]["underlying"] == "LUMN"
    assert lumn["option"]["strike"] == 10


def test_stock_display_equals_symbol():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    aapl = next(h for h in holdings if h["symbol"] == "AAPL")
    assert aapl["display"] == "AAPL"
    assert "option" not in aapl


def test_no_dollar_values_in_output():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    for h in holdings:
        assert "position_value" not in h
        assert "position" not in h  # (share count)


def test_compute_leverage_gross():
    """Gross leverage = (total_long + |total_short|) / total.
    Fixture: total_long=150000, total_short=-30000, total=120000
    → (150000 - (-30000)) / 120000 = 1.5"""
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    latest = parsed["nav"][-1]
    assert compute_leverage(latest) == 1.5


def test_compute_leverage_no_shorts():
    """With zero short exposure, gross leverage equals long-only leverage."""
    nav = {"total": 100000.0, "total_long": 120000.0, "total_short": 0.0}
    assert compute_leverage(nav) == 1.2
