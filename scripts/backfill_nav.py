"""One-shot backfill of NAV history from a directory of IBKR Flex XMLs.

Reads every *.xml in the directory, parses out EquitySummaryByReportDateInBase
rows AND CashTransaction rows of type Deposits / Withdrawals / Internal
Transfers, dedupes by date for NAV (later files win on conflict), unions
cashflows, then:
  - writes the merged dollar NAV to data/nav_history.json (gitignored)
  - regenerates data/nav_history_pct.json from scratch using time-weighted
    return math (daily cashflows subtracted before computing daily return)

Usage:  python -m scripts.backfill_nav [DIR]      # default DIR is backfill/
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts import nav_history, parse


def merge_xml_dir(directory: Path) -> tuple[list[dict], list[dict]]:
    """Read every *.xml in directory, return (dollar NAV, cashflows) sorted ascending.

    Leading rows with total <= 0 are dropped — these represent days before the
    account was funded and would otherwise anchor the pct series at zero,
    causing a divide-by-zero in compute_twr_series.

    Cashflows are unioned across files and deduped by (date, amount, type)
    so an event covered by overlapping queries is not double-counted.
    """
    files = sorted(directory.glob("*.xml"))
    if not files:
        raise FileNotFoundError(f"no *.xml files found in {directory}")

    nav_by_date: dict[str, dict] = {}
    seen_cashflows: set[tuple[str, float, str]] = set()
    cashflows: list[dict] = []
    for path in files:
        parsed = parse.parse_flex_xml(path.read_text(encoding="utf-8"))
        for row in parsed["nav"]:
            nav_by_date[row["date"]] = row  # later files win on NAV conflict
        for cf in parsed.get("cashflows", []):
            key = (cf["date"], cf["amount"], cf["type"])
            if key in seen_cashflows:
                continue
            seen_cashflows.add(key)
            cashflows.append(cf)

    nav = sorted(nav_by_date.values(), key=lambda r: r["date"])
    while nav and nav[0]["total"] <= 0:
        nav.pop(0)
    cashflows.sort(key=lambda r: r["date"])
    return nav, cashflows


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    directory = Path(argv[0]) if argv else Path("backfill")
    if not directory.is_dir():
        print(f"error: {directory} is not a directory", file=sys.stderr)
        return 1

    nav, cashflows = merge_xml_dir(directory)
    pct = nav_history.compute_twr_series(nav, cashflows)

    data = Path("data")
    data.mkdir(exist_ok=True)
    nav_history.save(data / "nav_history.json", nav)
    nav_history.save(data / "nav_history_pct.json", pct)

    total_in  = sum(c["amount"] for c in cashflows if c["amount"] > 0)
    total_out = sum(c["amount"] for c in cashflows if c["amount"] < 0)
    print(f"merged {len(nav)} unique trading days  |  {nav[0]['date']} -> {nav[-1]['date']}")
    print(f"cashflows: {len(cashflows)} events  |  deposits ${total_in:,.0f}  withdrawals ${total_out:,.0f}")
    print(f"re-anchored TWR pct ledger:  row[0] = 0.0%   row[-1] = {pct[-1]['return_pct']}%")
    if not cashflows:
        print("WARNING: zero cashflow events parsed. The XMLs likely don't include the")
        print("         CashTransaction section yet, so TWR == raw NAV ratio. Re-pull")
        print("         after enabling Cash Transactions (Deposits/Withdrawals) in IBKR.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
