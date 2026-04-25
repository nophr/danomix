import pytest
from scripts.options import parse_option_symbol, format_option_display


def test_parses_lumn_call():
    result = parse_option_symbol("LUMN  270115C00010000")
    assert result == {
        "underlying": "LUMN",
        "expiry": "2027-01-15",
        "type": "call",
        "strike": 10,
    }


def test_parses_unh_high_strike():
    result = parse_option_symbol("UNH   270115C00450000")
    assert result["underlying"] == "UNH"
    assert result["strike"] == 450


def test_parses_put():
    result = parse_option_symbol("AAPL  250117P00100000")
    assert result["type"] == "put"
    assert result["strike"] == 100
    assert result["expiry"] == "2025-01-17"


def test_formats_display():
    parsed = parse_option_symbol("LUMN  270115C00010000")
    assert format_option_display(parsed) == "LUMN Jan'27 $10C"


def test_formats_put_display():
    parsed = parse_option_symbol("AAPL  250117P00100000")
    assert format_option_display(parsed) == "AAPL Jan'25 $100P"


def test_rejects_malformed():
    with pytest.raises(ValueError):
        parse_option_symbol("not an option")
