"""One-time seed: convert an IBKR Client Portal Activity Statement CSV to nav_history.json.

Usage:
    python -m scripts.seed_nav path/to/statement.csv data/nav_history.json

Run locally; never in CI.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

from scripts import nav_history


def parse_statement_csv(csv_text: str) -> list[dict]:
    reader = csv.reader(io.StringIO(csv_text))
    out = []
    for row in reader:
        if len(row) < 6:
            continue
        if row[0] != "Data" or row[1] != "Net Asset Value":
            continue
        try:
            out.append({
                "date":        row[2],
                "total":       float(row[3]),
                "total_long":  float(row[4]),
                "total_short": float(row[5]),
            })
        except (IndexError, ValueError):
            continue
    out.sort(key=lambda r: r["date"])
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m scripts.seed_nav <statement.csv> <out.json>", file=sys.stderr)
        return 2
    csv_path, out_path = Path(argv[0]), Path(argv[1])
    ledger = parse_statement_csv(csv_path.read_text(encoding="utf-8"))
    nav_history.save(out_path, ledger)
    print(f"Wrote {len(ledger)} NAV rows to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
