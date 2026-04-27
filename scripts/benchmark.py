"""Fetch SPY daily closes from Yahoo Finance and normalize to an inception-relative return series."""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from typing import Optional

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1=0&period2={now}&interval=1d"


def _urlopen(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_spy_closes() -> list[dict]:
    url = YAHOO_URL.format(now=int(time.time()))
    with _urlopen(url, timeout=30) as resp:
        payload = json.loads(resp.read())
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise RuntimeError(f"Yahoo chart error: {chart['error']}")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise RuntimeError("Yahoo chart response had no result")
    timestamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    rows = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        d = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        rows.append({"date": d, "close": float(close)})
    rows.sort(key=lambda r: r["date"])
    return rows


def to_return_series(closes: list[dict], inception_date: Optional[str] = None) -> list[dict]:
    if not closes:
        return []
    if inception_date is not None:
        closes = [c for c in closes if c["date"] >= inception_date]
        if not closes:
            return []
    base = closes[0]["close"]
    return [
        {"date": c["date"], "return_pct": round((c["close"] / base - 1) * 100, 2)}
        for c in closes
    ]
