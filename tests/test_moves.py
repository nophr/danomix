from scripts.moves import classify_moves


def test_open_position():
    prior = []
    today = [{"symbol": "NVDA", "display": "NVDA", "percent": 3.5}]
    moves = classify_moves(today, prior, as_of="2026-04-20")
    assert moves[0]["type"] == "open"
    assert moves[0]["symbol"] == "NVDA"
    assert moves[0]["delta_pp"] == 3.5
    assert moves[0]["to_pct"] == 3.5
    assert moves[0]["from_pct"] == 0


def test_close_position():
    prior = [{"symbol": "TSLA", "display": "TSLA", "percent": 6.2}]
    today = []
    moves = classify_moves(today, prior, as_of="2026-04-02")
    assert moves[0]["type"] == "close"
    assert moves[0]["delta_pp"] == -6.2
    assert moves[0]["from_pct"] == 6.2


def test_add_over_threshold():
    prior = [{"symbol": "AAPL", "display": "AAPL", "percent": 29.9}]
    today = [{"symbol": "AAPL", "display": "AAPL", "percent": 32.0}]
    moves = classify_moves(today, prior, as_of="2026-04-16")
    assert moves[0]["type"] == "add"
    assert moves[0]["delta_pp"] == 2.1


def test_trim_over_threshold():
    prior = [{"symbol": "GOOGL", "display": "GOOGL", "percent": 14.4}]
    today = [{"symbol": "GOOGL", "display": "GOOGL", "percent": 13.0}]
    moves = classify_moves(today, prior, as_of="2026-04-09")
    assert moves[0]["type"] == "trim"
    assert round(moves[0]["delta_pp"], 1) == -1.4


def test_micro_drift_filtered():
    prior = [{"symbol": "MSFT", "display": "MSFT", "percent": 22.0}]
    today = [{"symbol": "MSFT", "display": "MSFT", "percent": 22.3}]
    moves = classify_moves(today, prior, as_of="2026-04-10")
    assert moves == []  # 0.3pp < 0.5pp threshold


def test_sorts_newest_first_when_same_date():
    # All moves share the `as_of` date; sort is stable on symbol then.
    prior = [{"symbol": "A", "display": "A", "percent": 0}]
    today = [
        {"symbol": "B", "display": "B", "percent": 10.0},
        {"symbol": "A", "display": "A", "percent": 0.0},
    ]
    moves = classify_moves(today, prior, as_of="2026-04-20")
    assert len(moves) == 1
    assert moves[0]["symbol"] == "B"
