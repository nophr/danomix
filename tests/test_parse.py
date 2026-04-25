from scripts.parse import parse_flex_xml
from tests.conftest import read_fixture


def test_parses_positions():
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    positions = result["positions"]
    assert len(positions) == 3
    aapl = next(p for p in positions if p["symbol"] == "AAPL")
    assert aapl["asset_category"] == "STK"
    assert aapl["position_value"] == 30000.0
    assert aapl["currency"] == "USD"


def test_parses_nav_rows():
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    nav = result["nav"]
    assert len(nav) == 3
    assert nav[0] == {"date": "2024-01-02", "total": 100000.0, "total_long": 100000.0, "total_short": 0.0}
    assert nav[-1]["total_long"] == 150000.0


def test_drops_account_id():
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    # account_id should NOT be present — the parser strips it deliberately
    assert "account_id" not in result
    assert "U0000000" not in str(result)


def test_preserves_option_symbol_verbatim():
    # We don't parse OCC here — scripts.options does that. Parser passes symbol through.
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    opts = [p for p in result["positions"] if p["asset_category"] == "OPT"]
    assert len(opts) == 1
    assert opts[0]["symbol"] == "LUMN  270115C00010000"
