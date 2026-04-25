"""Append-only NAV ledger persisted as JSON."""

from __future__ import annotations

import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def save(path: Path, ledger: list[dict]) -> None:
    tmp = Path(path).with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_new(existing: list[dict], incoming: list[dict]) -> list[dict]:
    known_dates = {row["date"] for row in existing}
    additions = [row for row in incoming if row["date"] not in known_dates]
    merged = existing + additions
    merged.sort(key=lambda r: r["date"])
    return merged


def to_performance_series(ledger: list[dict]) -> list[dict]:
    if not ledger:
        return []
    base = ledger[0]["total"]
    return [
        {"date": row["date"], "return_pct": round((row["total"] / base - 1) * 100, 2)}
        for row in ledger
    ]
