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


def extend_pct(existing_pct: list[dict], new_dollar_nav: list[dict]) -> list[dict]:
    """Append new dates from a fresh dollar NAV pull onto an existing pct series.

    Math: pick the most recent date present in both series as the chain anchor;
    new pct = (1 + pct_anchor/100) * (dollars_new / dollars_anchor) - 1, in %.
    Existing pct values are never recomputed — committed history stays stable.
    """
    if not existing_pct:
        return to_performance_series([{"date": r["date"], "total": r["total"]} for r in new_dollar_nav])

    existing_dates = {r["date"] for r in existing_pct}
    inception = existing_pct[0]["date"]
    new_after_inception = [r for r in new_dollar_nav if r["date"] >= inception]
    new_dates = [r for r in new_after_inception if r["date"] not in existing_dates]
    if not new_dates:
        return list(existing_pct)

    dollars_by_date = {r["date"]: r["total"] for r in new_after_inception}
    overlap = [r for r in existing_pct if r["date"] in dollars_by_date]
    if not overlap:
        raise ValueError(
            "extend_pct: no overlap between existing pct series and new dollar NAV — "
            "cannot chain new dates without a shared anchor date"
        )
    anchor = overlap[-1]
    pct_anchor = anchor["return_pct"]
    dollars_anchor = dollars_by_date[anchor["date"]]

    appended = list(existing_pct)
    for row in new_dates:
        ratio = (1 + pct_anchor / 100) * (row["total"] / dollars_anchor)
        appended.append({"date": row["date"], "return_pct": round((ratio - 1) * 100, 2)})
    appended.sort(key=lambda r: r["date"])
    return appended
