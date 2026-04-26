import json
import pytest

from scripts.nav_history import (
    append_new,
    extend_pct,
    load,
    to_performance_series,
)


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


def test_extend_pct_bootstraps_when_existing_empty():
    new_dollars = [
        {"date": "2024-01-02", "total": 100.0},
        {"date": "2024-06-03", "total": 110.0},
        {"date": "2024-12-31", "total": 120.0},
    ]
    out = extend_pct([], new_dollars)
    assert out == [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-06-03", "return_pct": 10.0},
        {"date": "2024-12-31", "return_pct": 20.0},
    ]


def test_extend_pct_chains_new_dates_via_overlap_anchor():
    existing = [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-06-03", "return_pct": 10.0},  # implied $110 if base=$100
    ]
    new_dollars = [
        {"date": "2024-06-03", "total": 220.0},   # anchor (different scale; value irrelevant)
        {"date": "2024-12-31", "total": 242.0},   # +10% from anchor in dollar space
    ]
    out = extend_pct(existing, new_dollars)
    assert len(out) == 3
    assert out[2]["date"] == "2024-12-31"
    # 1.10 (existing pct at anchor) * 242/220 = 1.21 → 21%
    assert out[2]["return_pct"] == 21.0


def test_extend_pct_preserves_existing_pct_unchanged():
    existing = [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-06-03", "return_pct": 10.0},
    ]
    # Even if dollar series implies a different historical pct, existing values must not move.
    new_dollars = [
        {"date": "2024-01-02", "total": 999.0},   # would imply different ratio
        {"date": "2024-06-03", "total": 1100.0},
        {"date": "2024-12-31", "total": 1210.0},
    ]
    out = extend_pct(existing, new_dollars)
    assert out[0] == {"date": "2024-01-02", "return_pct": 0.0}
    assert out[1] == {"date": "2024-06-03", "return_pct": 10.0}


def test_extend_pct_no_new_dates_is_noop():
    existing = [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-06-03", "return_pct": 10.0},
    ]
    new_dollars = [
        {"date": "2024-01-02", "total": 100.0},
        {"date": "2024-06-03", "total": 110.0},
    ]
    out = extend_pct(existing, new_dollars)
    assert out == existing


def test_extend_pct_raises_when_no_overlap_for_chain():
    existing = [{"date": "2024-01-02", "return_pct": 0.0}]
    new_dollars = [{"date": "2025-06-01", "total": 100.0}]  # no shared date
    with pytest.raises(ValueError, match="no overlap"):
        extend_pct(existing, new_dollars)


def test_extend_pct_ignores_dates_before_existing_inception():
    # We never extend backwards; only forward.
    existing = [
        {"date": "2024-06-03", "return_pct": 0.0},
        {"date": "2024-12-31", "return_pct": 10.0},
    ]
    new_dollars = [
        {"date": "2024-01-02", "total": 90.0},    # earlier than existing — must be ignored
        {"date": "2024-06-03", "total": 100.0},
        {"date": "2024-12-31", "total": 110.0},
        {"date": "2025-03-01", "total": 121.0},   # new — should be appended
    ]
    out = extend_pct(existing, new_dollars)
    dates = [r["date"] for r in out]
    assert dates == ["2024-06-03", "2024-12-31", "2025-03-01"]
    # 1.10 * 121/110 = 1.21 → 21%
    assert out[-1]["return_pct"] == 21.0
