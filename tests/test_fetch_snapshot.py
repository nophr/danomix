import json
from pathlib import Path

from scripts import fetch_snapshot
from tests.conftest import read_fixture


def test_build_snapshot_privacy_properties():
    """Integration test: the final snapshot dict must be free of identifiers."""
    xml = read_fixture("sample_flex.xml")
    nav_ledger = [
        {"date": "2024-01-02", "total": 100000.0, "total_long": 100000.0, "total_short": 0.0},
        {"date": "2024-06-03", "total": 110000.0, "total_long": 130000.0, "total_short": -20000.0},
        {"date": "2024-12-31", "total": 120000.0, "total_long": 150000.0, "total_short": -30000.0},
    ]
    spy_series = [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-12-31", "return_pct": 15.0},
    ]
    prior_holdings = []  # all positions "opened" today

    snap = fetch_snapshot.build_snapshot(
        flex_xml=xml,
        nav_ledger=nav_ledger,
        spy_series=spy_series,
        prior_holdings=prior_holdings,
        today="2024-12-31",
    )

    serialized = json.dumps(snap)
    assert "U0000000" not in serialized          # account id stripped
    assert "positionValue" not in serialized     # dollar field stripped
    assert "accountId" not in serialized.lower() # nothing that looks like an id

    assert snap["nav"]["leverage"] == 1.25
    assert abs(sum(h["percent"] for h in snap["holdings"]) - 100.0) < 0.01
    assert snap["performance"]["benchmark"]["ticker"] == "SPY"


def test_build_snapshot_recent_moves_classifies_opens():
    xml = read_fixture("sample_flex.xml")
    nav_ledger = [{"date": "2024-12-31", "total": 120000.0, "total_long": 150000.0, "total_short": -30000.0}]
    snap = fetch_snapshot.build_snapshot(
        flex_xml=xml,
        nav_ledger=nav_ledger,
        spy_series=[{"date": "2024-12-31", "return_pct": 0.0}],
        prior_holdings=[],
        today="2024-12-31",
    )
    move_types = {m["type"] for m in snap["recent_moves"]}
    assert move_types == {"open"}  # all 3 positions are new
