import json
from pathlib import Path

from scripts import fetch_snapshot
from tests.conftest import read_fixture


def test_build_snapshot_privacy_properties():
    """Integration test: the final snapshot dict must be free of identifiers AND dollars."""
    xml = read_fixture("sample_flex.xml")
    pct_series = [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-06-03", "return_pct": 10.0},
        {"date": "2024-12-31", "return_pct": 20.0},
    ]
    latest_nav = {"date": "2024-12-31", "total": 120000.0, "total_long": 150000.0, "total_short": -30000.0}
    spy_series = [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-12-31", "return_pct": 15.0},
    ]
    prior_holdings = []  # all positions "opened" today

    snap = fetch_snapshot.build_snapshot(
        flex_xml=xml,
        pct_series=pct_series,
        latest_nav=latest_nav,
        spy_series=spy_series,
        prior_holdings=prior_holdings,
        today="2024-12-31",
    )

    serialized = json.dumps(snap)
    assert "U0000000" not in serialized          # account id stripped
    assert "positionValue" not in serialized     # dollar field stripped
    assert "accountId" not in serialized.lower() # nothing that looks like an id
    assert "150000" not in serialized            # latest dollar NAV stays in memory only
    assert "120000" not in serialized            # latest dollar NAV stays in memory only

    assert snap["nav"]["leverage"] == 1.25
    assert abs(sum(h["percent"] for h in snap["holdings"]) - 100.0) < 0.01
    assert snap["performance"]["benchmark"]["ticker"] == "SPY"
    assert snap["performance"]["portfolio"] == pct_series


def test_build_snapshot_recent_moves_classifies_opens():
    xml = read_fixture("sample_flex.xml")
    snap = fetch_snapshot.build_snapshot(
        flex_xml=xml,
        pct_series=[{"date": "2024-12-31", "return_pct": 0.0}],
        latest_nav={"date": "2024-12-31", "total": 120000.0, "total_long": 150000.0, "total_short": -30000.0},
        spy_series=[{"date": "2024-12-31", "return_pct": 0.0}],
        prior_holdings=[],
        today="2024-12-31",
    )
    move_types = {m["type"] for m in snap["recent_moves"]}
    assert move_types == {"open"}  # all 3 positions are new
