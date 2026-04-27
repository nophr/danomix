"""One-shot backfill of NAV history from a directory of IBKR Flex XMLs.

Reads every *.xml in the directory, parses out EquitySummaryByReportDateInBase
rows, dedupes by date (later files win on conflict), sorts ascending, then:
  - writes the merged dollar NAV to data/nav_history.json (gitignored)
  - regenerates data/nav_history_pct.json from scratch via
    nav_history.to_performance_series — re-anchored at row[0]

Usage:  python -m scripts.backfill_nav [DIR]      # default DIR is backfill/
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts import nav_history, parse


def merge_xml_dir(directory: Path) -> list[dict]:
    """Read every *.xml in directory, return a deduped, ascending-sorted dollar NAV list.

    Leading rows with total <= 0 are dropped — these represent days before the
    account was funded and would otherwise anchor the pct series at zero,
    causing a divide-by-zero in to_performance_series.
    """
    files = sorted(directory.glob("*.xml"))
    if not files:
        raise FileNotFoundError(f"no *.xml files found in {directory}")
    by_date: dict[str, dict] = {}
    for path in files:
        parsed = parse.parse_flex_xml(path.read_text(encoding="utf-8"))
        for row in parsed["nav"]:
            by_date[row["date"]] = row  # later files win on conflict
    rows = sorted(by_date.values(), key=lambda r: r["date"])
    while rows and rows[0]["total"] <= 0:
        rows.pop(0)
    return rows


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    directory = Path(argv[0]) if argv else Path("backfill")
    if not directory.is_dir():
        print(f"error: {directory} is not a directory", file=sys.stderr)
        return 1

    merged = merge_xml_dir(directory)
    pct = nav_history.to_performance_series(merged)

    data = Path("data")
    data.mkdir(exist_ok=True)
    nav_history.save(data / "nav_history.json", merged)
    nav_history.save(data / "nav_history_pct.json", pct)

    print(f"merged {len(merged)} unique trading days  |  {merged[0]['date']} -> {merged[-1]['date']}")
    print(f"re-anchored pct ledger:  row[0] = 0.0%   row[-1] = {pct[-1]['return_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
