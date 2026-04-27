"""Daily snapshot orchestrator — run by GitHub Actions.

Pipeline:
  1. Call Flex (SendRequest + GetStatement) for the latest XML.
  2. Parse it into {positions, nav (dollars)}.
  3. Chain-extend the persistent pct series with any new dates (dollars stay in memory).
  4. Refresh SPY benchmark from Stooq (fallback: reuse committed cache).
  5. Build public snapshot.json (percentages only, no identifiers).
  6. Atomically write data/snapshot.json + data/nav_history_pct.json + data/benchmark_history.json.

Public repo safety: dollar NAV values are never persisted to disk — only the
return_pct series is committed. data/nav_history.json (dollars) stays gitignored
and is written purely as a local-only artifact for personal analysis.

Entrypoint: python -m scripts.fetch_snapshot
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from scripts import flex, parse, transform, nav_history, moves, benchmark

DATA = Path("data")
SNAPSHOT_PATH       = DATA / "snapshot.json"
NAV_PCT_PATH        = DATA / "nav_history_pct.json"   # committed (pct only)
NAV_DOLLARS_PATH    = DATA / "nav_history.json"       # gitignored (local only)
BENCHMARK_PATH      = DATA / "benchmark_history.json"

VERSION = 1


def build_snapshot(*, flex_xml: str, pct_series: list[dict], latest_nav: dict,
                   spy_series: list[dict], prior_holdings: Optional[list[dict]], today: str) -> dict:
    parsed = parse.parse_flex_xml(flex_xml)
    holdings = transform.build_holdings(parsed["positions"])

    leverage = transform.compute_leverage(latest_nav)
    inception = pct_series[0]["date"]

    # No baseline (brand-new repo / first run) → suppress the seed-data flood of synthetic "open" moves.
    if prior_holdings is None:
        recent = []
    else:
        recent = moves.classify_moves(holdings, prior_holdings, as_of=today)

    return {
        "version":        VERSION,
        "updated_at":     today,
        "inception_date": inception,
        "nav":            {"leverage": leverage},
        "holdings":       holdings,
        "performance": {
            "portfolio": pct_series,
            "benchmark": {"ticker": "SPY", "series": spy_series},
        },
        "recent_moves": recent,
    }


def _atomic_write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_prior_holdings_30d_ago() -> Optional[list[dict]]:
    """Read data/snapshot.json as it existed ~30 days ago via git history.

    Returns None when no baseline is available (brand-new repo, or the file
    didn't exist at that commit) — so callers can suppress the seed-data
    flood of synthetic "open" moves on the first run.

    Returns a list (possibly empty) when a baseline was actually found.
    """
    import subprocess
    try:
        sha = subprocess.run(
            ["git", "rev-list", "-1", "--before=30 days ago", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if not sha:
            return None
        result = subprocess.run(
            ["git", "show", f"{sha}:data/snapshot.json"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return None  # file didn't exist at that commit
        return json.loads(result.stdout).get("holdings", [])
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return None


def main() -> int:
    token = os.environ["IBKR_FLEX_TOKEN"]
    query_id = os.environ["IBKR_FLEX_QUERY_ID"]

    DATA.mkdir(exist_ok=True)

    # 1+2. Flex → XML → parsed (dollars live in memory only from here)
    ref = flex.request_statement(token=token, query_id=query_id)
    xml_bytes = flex.fetch_statement(token=token, ref_code=ref)
    parsed = parse.parse_flex_xml(xml_bytes.decode("utf-8"))
    if not parsed["nav"]:
        print("error: Flex response had no NAV rows", file=sys.stderr)
        return 1
    latest_nav = parsed["nav"][-1]

    # 3. Chain-extend the public pct series — only new dates get computed
    existing_pct = nav_history.load(NAV_PCT_PATH)
    merged_pct = nav_history.extend_pct(existing_pct, parsed["nav"])
    nav_history.save(NAV_PCT_PATH, merged_pct)

    # Local-only dollar mirror for personal analysis (gitignored)
    existing_dollars = nav_history.load(NAV_DOLLARS_PATH)
    merged_dollars = nav_history.append_new(existing_dollars, parsed["nav"])
    nav_history.save(NAV_DOLLARS_PATH, merged_dollars)

    # 4. Benchmark — resilient to Stooq outage
    inception = merged_pct[0]["date"]
    try:
        closes = benchmark.fetch_spy_closes()
        if BENCHMARK_PATH.exists():
            cached = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
            known = {c["date"] for c in cached}
            cached.extend(c for c in closes if c["date"] not in known)
            cached.sort(key=lambda c: c["date"])
            closes = cached
        _atomic_write_json(BENCHMARK_PATH, closes)
        spy_series = benchmark.to_return_series(closes, inception_date=inception)
    except Exception as e:
        print(f"warning: Stooq fetch failed ({e}); reusing cached benchmark", file=sys.stderr)
        if not BENCHMARK_PATH.exists():
            raise
        closes = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
        spy_series = benchmark.to_return_series(closes, inception_date=inception)

    # 5+6. Build snapshot and write — prior holdings come from ~30 days ago in git
    prior_holdings = _load_prior_holdings_30d_ago()
    today = date.today().isoformat()
    snap = build_snapshot(
        flex_xml=xml_bytes.decode("utf-8"),
        pct_series=merged_pct,
        latest_nav=latest_nav,
        spy_series=spy_series,
        prior_holdings=prior_holdings,
        today=today,
    )
    _atomic_write_json(SNAPSHOT_PATH, snap)
    print(f"wrote {SNAPSHOT_PATH} · holdings={len(snap['holdings'])} · leverage={snap['nav']['leverage']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
