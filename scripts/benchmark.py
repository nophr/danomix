"""Fetch SPY daily closes from Stooq and normalize to an inception-relative return series."""

from __future__ import annotations

import urllib.request
from typing import Optional

STOOQ_URL = "https://stooq.com/q/d/l/?s=spy.us&i=d"


def _urlopen(url: str, timeout: int = 30):
    return urllib.request.urlopen(url, timeout=timeout)


def fetch_spy_closes() -> list[dict]:
    with _urlopen(STOOQ_URL, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    lines = text.strip().splitlines()
    header = lines[0].split(",")
    idx_date = header.index("Date")
    idx_close = header.index("Close")
    rows = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < max(idx_date, idx_close) + 1:
            continue
        try:
            close = float(parts[idx_close])
        except ValueError:
            continue
        rows.append({"date": parts[idx_date], "close": close})
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
