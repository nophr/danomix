import json

from scripts import benchmark


class _FakeResp:
    def __init__(self, body): self._body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self): return self._body


YAHOO_JSON = json.dumps({
    "chart": {
        "error": None,
        "result": [{
            "timestamp": [1704196800, 1717416000, 1735646400],  # 2024-01-02, 2024-06-03, 2024-12-31 (UTC noon)
            "indicators": {"quote": [{"close": [472.65, 520.44, 589.36]}]},
        }],
    },
}).encode("utf-8")


def test_fetch_spy_daily_closes(monkeypatch):
    monkeypatch.setattr(benchmark, "_urlopen", lambda url, timeout=30: _FakeResp(YAHOO_JSON))
    closes = benchmark.fetch_spy_closes()
    assert closes[0] == {"date": "2024-01-02", "close": 472.65}
    assert closes[-1] == {"date": "2024-12-31", "close": 589.36}


def test_fetch_spy_skips_null_closes(monkeypatch):
    payload = json.dumps({
        "chart": {
            "error": None,
            "result": [{
                "timestamp": [1704196800, 1717416000, 1735646400],
                "indicators": {"quote": [{"close": [472.65, None, 589.36]}]},
            }],
        },
    }).encode("utf-8")
    monkeypatch.setattr(benchmark, "_urlopen", lambda url, timeout=30: _FakeResp(payload))
    closes = benchmark.fetch_spy_closes()
    assert [c["date"] for c in closes] == ["2024-01-02", "2024-12-31"]


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
