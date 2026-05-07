"""Compute holdings whose mark price moved >= threshold day over day.

Compares per-share prices between today's holdings and a prior holdings list
(typically yesterday's snapshot via git history). Newly opened positions and
closed positions are skipped — there's no prior or current price to diff.
"""

from __future__ import annotations

THRESHOLD_PCT = 5.0


def compute(today: list[dict], prior: list[dict],
            *, threshold_pct: float = THRESHOLD_PCT) -> list[dict]:
    prior_price_by_sym = {
        h["symbol"]: h["price"]
        for h in prior
        if h.get("price") and h["price"] > 0
    }

    movers: list[dict] = []
    for h in today:
        today_price = h.get("price")
        if not today_price or today_price <= 0:
            continue
        prior_price = prior_price_by_sym.get(h["symbol"])
        if not prior_price:
            continue
        change_pct = round((today_price - prior_price) / prior_price * 100, 2)
        if abs(change_pct) < threshold_pct:
            continue
        movers.append({
            "symbol":      h["symbol"],
            "display":     h["display"],
            "asset_class": h["asset_class"],
            "percent":     h["percent"],
            "change_pct":  change_pct,
        })

    movers.sort(key=lambda m: (-abs(m["change_pct"]), m["symbol"]))
    return movers
