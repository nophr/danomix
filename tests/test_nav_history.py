import json
from scripts.nav_history import load, append_new, to_performance_series


def test_load_missing_returns_empty(tmp_path):
    assert load(tmp_path / "nav.json") == []


def test_load_existing(tmp_path):
    path = tmp_path / "nav.json"
    path.write_text(json.dumps([{"date": "2024-01-02", "total": 100.0}]))
    assert load(path)[0]["date"] == "2024-01-02"


def test_append_new_only_new_dates(tmp_path):
    existing = [
        {"date": "2024-01-02", "total": 100.0, "total_long": 100.0, "total_short": 0.0},
        {"date": "2024-01-03", "total": 102.0, "total_long": 102.0, "total_short": 0.0},
    ]
    incoming = [
        {"date": "2024-01-03", "total": 999.9, "total_long": 999.9, "total_short": 0.0},  # dupe — must NOT override
        {"date": "2024-01-04", "total": 105.0, "total_long": 105.0, "total_short": 0.0},
    ]
    merged = append_new(existing, incoming)
    assert len(merged) == 3
    assert merged[1]["total"] == 102.0  # not overridden
    assert merged[2]["date"] == "2024-01-04"


def test_to_performance_series_normalizes_to_inception():
    ledger = [
        {"date": "2024-01-02", "total": 100.0, "total_long": 100.0, "total_short": 0.0},
        {"date": "2024-06-03", "total": 110.0, "total_long": 110.0, "total_short": 0.0},
        {"date": "2024-12-31", "total": 120.0, "total_long": 120.0, "total_short": 0.0},
    ]
    series = to_performance_series(ledger)
    assert series[0] == {"date": "2024-01-02", "return_pct": 0.0}
    assert series[1]["return_pct"] == 10.0
    assert series[2]["return_pct"] == 20.0
