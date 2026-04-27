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


def compute_twr_series(nav: list[dict], cashflows: list[dict]) -> list[dict]:
    """Daily time-weighted return series from a dollar NAV ledger + external cashflows.

    For each consecutive trading day pair (V_{i-1}, V_i) on dates (d_{i-1}, d_i):
        c_i = sum of external cashflows with d_{i-1} < date <= d_i
        r_i = (V_i - c_i) / V_{i-1} - 1
    Cumulative TWR_t = ∏_{i=1..t} (1 + r_i) - 1, expressed as %.

    Anchored at row[0] = 0%. External cashflows are deposits and withdrawals
    (positive = deposit, negative = withdrawal). Internal P&L (mark-to-market,
    dividends, interest, commissions) is NOT a cashflow — it stays in NAV.
    """
    if not nav:
        return []

    # Aggregate cashflows by date for quick lookup.
    cf_by_date: dict[str, float] = {}
    for c in cashflows:
        cf_by_date[c["date"]] = cf_by_date.get(c["date"], 0.0) + c["amount"]

    series = [{"date": nav[0]["date"], "return_pct": 0.0}]
    cumulative = 1.0
    for prev, curr in zip(nav, nav[1:]):
        v_prev, v_curr = prev["total"], curr["total"]
        if v_prev <= 0:
            # Account had zero balance going into this day — can't compute a return.
            # Reset the chain by anchoring at this day with 0%.
            cumulative = 1.0
            series.append({"date": curr["date"], "return_pct": 0.0})
            continue
        # Sum cashflows occurring between prev_date (exclusive) and curr_date (inclusive).
        c = sum(amt for d, amt in cf_by_date.items() if prev["date"] < d <= curr["date"])
        daily_return = (v_curr - c) / v_prev - 1
        cumulative *= (1 + daily_return)
        series.append({"date": curr["date"], "return_pct": round((cumulative - 1) * 100, 2)})
    return series


def extend_twr(existing_pct: list[dict], new_nav: list[dict],
               new_cashflows: list[dict]) -> list[dict]:
    """Append new dates onto an existing TWR pct series using daily TWR math.

    The chain anchor is the most recent date present in both existing_pct and
    new_nav. Existing pct values are never recomputed — committed history stays
    stable. Only days strictly after the anchor are added.
    """
    if not existing_pct:
        return compute_twr_series(new_nav, new_cashflows)

    existing_dates = {r["date"] for r in existing_pct}
    nav_by_date = {r["date"]: r for r in new_nav}
    overlap_dates = [d for d in existing_dates if d in nav_by_date]
    if not overlap_dates:
        raise ValueError(
            "extend_twr: no overlap between existing pct series and new NAV — "
            "cannot chain new dates without a shared anchor date"
        )
    anchor_date = max(overlap_dates)
    anchor_pct = next(r["return_pct"] for r in existing_pct if r["date"] == anchor_date)
    anchor_factor = 1 + anchor_pct / 100
    v_anchor = nav_by_date[anchor_date]["total"]

    new_after_anchor = sorted(
        (r for r in new_nav if r["date"] > anchor_date),
        key=lambda r: r["date"],
    )
    if not new_after_anchor:
        return list(existing_pct)

    cf_by_date: dict[str, float] = {}
    for c in new_cashflows:
        cf_by_date[c["date"]] = cf_by_date.get(c["date"], 0.0) + c["amount"]

    appended = list(existing_pct)
    cumulative = 1.0
    v_prev, prev_date = v_anchor, anchor_date
    for row in new_after_anchor:
        v_curr = row["total"]
        if v_prev <= 0:
            cumulative = 1.0
            appended.append({"date": row["date"], "return_pct": anchor_pct})
            v_prev, prev_date = v_curr, row["date"]
            continue
        c = sum(amt for d, amt in cf_by_date.items() if prev_date < d <= row["date"])
        daily_return = (v_curr - c) / v_prev - 1
        cumulative *= (1 + daily_return)
        new_pct = (anchor_factor * cumulative - 1) * 100
        appended.append({"date": row["date"], "return_pct": round(new_pct, 2)})
        v_prev, prev_date = v_curr, row["date"]

    appended.sort(key=lambda r: r["date"])
    return appended
