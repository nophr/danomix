"""Classify position changes between two holdings snapshots.

Types:
  open  — symbol appears where it wasn't
  close — symbol disappears
  add   — existing symbol grows by >= threshold percentage points
  trim  — existing symbol shrinks by >= threshold percentage points
  (drift below threshold is ignored)
"""

from __future__ import annotations

THRESHOLD_PP = 0.5


def classify_moves(today: list[dict], prior: list[dict], *, as_of: str,
                   threshold_pp: float = THRESHOLD_PP) -> list[dict]:
    prior_by_sym = {h["symbol"]: h for h in prior}
    today_by_sym = {h["symbol"]: h for h in today}
    all_symbols = set(prior_by_sym) | set(today_by_sym)

    moves: list[dict] = []
    for sym in all_symbols:
        p = prior_by_sym.get(sym, {"percent": 0.0, "display": sym})
        t = today_by_sym.get(sym, {"percent": 0.0, "display": p.get("display", sym)})
        delta = round(t["percent"] - p["percent"], 2)

        if p["percent"] == 0 and t["percent"] > 0:
            move_type = "open"
        elif p["percent"] > 0 and t["percent"] == 0:
            move_type = "close"
        elif delta >= threshold_pp:
            move_type = "add"
        elif delta <= -threshold_pp:
            move_type = "trim"
        else:
            continue  # micro-drift

        moves.append({
            "date":     as_of,
            "type":     move_type,
            "symbol":   sym,
            "display":  t.get("display") or p.get("display") or sym,
            "delta_pp": delta,
            "from_pct": p["percent"],
            "to_pct":   t["percent"],
        })

    moves.sort(key=lambda m: (m["date"], m["symbol"]), reverse=True)
    return moves
