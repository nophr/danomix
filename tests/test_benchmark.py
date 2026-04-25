from scripts import benchmark


class _FakeResp:
    def __init__(self, body): self._body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self): return self._body


STOOQ_CSV = (
    b"Date,Open,High,Low,Close,Volume\n"
    b"2024-01-02,472.16,473.78,470.50,472.65,70000000\n"
    b"2024-06-03,520.10,522.30,518.00,520.44,65000000\n"
    b"2024-12-31,586.08,590.10,585.00,589.36,72000000\n"
)


def test_fetch_spy_daily_closes(monkeypatch):
    monkeypatch.setattr(benchmark, "_urlopen", lambda url, timeout=30: _FakeResp(STOOQ_CSV))
    closes = benchmark.fetch_spy_closes()
    assert closes[0] == {"date": "2024-01-02", "close": 472.65}
    assert closes[-1]["close"] == 589.36


def test_benchmark_series_normalized_to_start():
    closes = [
        {"date": "2024-01-02", "close": 100.0},
        {"date": "2024-06-03", "close": 110.0},
        {"date": "2024-12-31", "close": 125.0},
    ]
    series = benchmark.to_return_series(closes)
    assert series[0]["return_pct"] == 0.0
    assert series[1]["return_pct"] == 10.0
    assert series[2]["return_pct"] == 25.0


def test_aligns_to_inception_date():
    closes = [
        {"date": "2023-01-01", "close": 50.0},   # before inception — discarded
        {"date": "2024-01-02", "close": 100.0},  # inception
        {"date": "2024-06-03", "close": 110.0},
    ]
    series = benchmark.to_return_series(closes, inception_date="2024-01-02")
    assert series[0]["date"] == "2024-01-02"
    assert series[0]["return_pct"] == 0.0
    assert series[-1]["return_pct"] == 10.0
