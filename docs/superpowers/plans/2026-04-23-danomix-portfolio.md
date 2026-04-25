# Danomix Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public, read-only portfolio site at danomix.com that displays IBKR holdings as percentages, an all-time performance chart vs. S&P 500, and recent position activity — powered by a daily GitHub Actions cron that pulls from IBKR Flex Web Service.

**Architecture:** Python 3.12 stdlib-only pipeline in GitHub Actions → commits a percentage-only `data/snapshot.json` → served as static assets from GitHub Pages. Durable state (`nav_history.json`, `benchmark_history.json`) lives in the repo and grows monotonically.

**Tech Stack:** Python 3.12 (stdlib), pytest, vanilla HTML/CSS/JS, uPlot (single frontend dependency, vendored), GitHub Actions, GitHub Pages.

**Reference spec:** `docs/superpowers/specs/2026-04-23-danomix-portfolio-design.md`

---

## File structure (created across all tasks)

```
danomix/
├── .github/workflows/daily-snapshot.yml     (Task 15)
├── scripts/
│   ├── __init__.py                          (Task 1)
│   ├── options.py                           (Task 2) — OCC option symbol parser
│   ├── parse.py                             (Task 3) — Flex XML → dict
│   ├── transform.py                         (Task 4) — dict → snapshot shape
│   ├── nav_history.py                       (Task 5) — append-only NAV ledger
│   ├── moves.py                             (Task 6) — 30-day diff classifier
│   ├── flex.py                              (Task 7) — Flex Web Service client
│   ├── benchmark.py                         (Task 8) — Stooq SPY fetcher
│   ├── seed_nav.py                          (Task 9) — CSV → nav_history (one-time)
│   └── fetch_snapshot.py                    (Task 10) — daily orchestrator
├── data/
│   ├── snapshot.json                        (generated)
│   ├── nav_history.json                     (generated)
│   └── benchmark_history.json               (generated)
├── public/
│   ├── index.html                           (Task 11)
│   ├── style.css                            (Task 11)
│   ├── app.js                               (Task 12–14)
│   ├── vendor/uPlot.iife.min.js             (Task 1, vendored)
│   ├── vendor/uPlot.min.css                 (Task 1, vendored)
│   ├── assets/favicon.svg                   (Task 15)
│   └── CNAME                                (Task 15)
├── tests/
│   ├── conftest.py                          (Task 1)
│   ├── fixtures/sample_flex.xml             (Task 1)
│   └── test_*.py                            (per task)
├── .gitignore                               (exists)
├── README.md                                (Task 15)
└── pyproject.toml                           (Task 1)
```

---

## Task 1: Project scaffolding and fixtures

**Files:**
- Create: `scripts/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/fixtures/sample_flex.xml`
- Create: `pyproject.toml`
- Create: `public/vendor/` (directory — populated by download)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "danomix-portfolio"
version = "0.1.0"
description = "Public IBKR portfolio dashboard for danomix.com"
requires-python = ">=3.12"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `scripts/__init__.py` (empty file)**

Just an empty file to mark `scripts/` as a package.

- [ ] **Step 3: Create `tests/conftest.py`**

```python
"""Pytest fixtures shared across all test modules."""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
```

- [ ] **Step 4: Create `tests/fixtures/sample_flex.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryName="Test" type="AF">
<FlexStatements count="1">
<FlexStatement accountId="U0000000" fromDate="2024-01-02" toDate="2024-12-31" period="Last365CalendarDays" whenGenerated="2024-12-31;000000 UTC">
<EquitySummaryInBase>
<EquitySummaryByReportDateInBase reportDate="2024-01-02" total="100000" totalLong="100000" totalShort="0" />
<EquitySummaryByReportDateInBase reportDate="2024-06-03" total="110000" totalLong="130000" totalShort="-20000" />
<EquitySummaryByReportDateInBase reportDate="2024-12-31" total="120000" totalLong="150000" totalShort="-30000" />
</EquitySummaryInBase>
<OpenPositions>
<OpenPosition symbol="AAPL" assetCategory="STK" position="100" positionValue="30000" currency="USD" />
<OpenPosition symbol="MSFT" assetCategory="STK" position="50" positionValue="20000" currency="USD" />
<OpenPosition symbol="LUMN  270115C00010000" assetCategory="OPT" position="25" positionValue="5000" currency="USD" />
</OpenPositions>
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>
```

Expected math against this fixture:
- Sum of positionValue = 55000 → AAPL 54.55%, MSFT 36.36%, LUMN call 9.09%
- Leverage = totalLong (150000) / total (120000) = **1.25**

- [ ] **Step 5: Download uPlot into `public/vendor/`**

```bash
mkdir -p public/vendor
curl -fsSL -o public/vendor/uPlot.iife.min.js   https://cdn.jsdelivr.net/npm/uplot@1.6.31/dist/uPlot.iife.min.js
curl -fsSL -o public/vendor/uPlot.min.css       https://cdn.jsdelivr.net/npm/uplot@1.6.31/dist/uPlot.min.css
```

- [ ] **Step 6: Verify pytest runs (no tests yet)**

```bash
python -m venv .venv
.venv/Scripts/pip install pytest   # Windows; use .venv/bin/pip on Unix
.venv/Scripts/pytest --collect-only
```

Expected: `collected 0 items` (no error — confirms discovery works).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml scripts/__init__.py tests/conftest.py tests/fixtures/sample_flex.xml public/vendor/
git commit -m "chore: scaffold Python package, pytest config, sample fixture, vendor uPlot"
```

---

## Task 2: OCC option symbol parser

**Files:**
- Create: `scripts/options.py`
- Test: `tests/test_options.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_options.py
import pytest
from scripts.options import parse_option_symbol, format_option_display


def test_parses_lumn_call():
    result = parse_option_symbol("LUMN  270115C00010000")
    assert result == {
        "underlying": "LUMN",
        "expiry": "2027-01-15",
        "type": "call",
        "strike": 10,
    }


def test_parses_unh_high_strike():
    result = parse_option_symbol("UNH   270115C00450000")
    assert result["underlying"] == "UNH"
    assert result["strike"] == 450


def test_parses_put():
    result = parse_option_symbol("AAPL  250117P00100000")
    assert result["type"] == "put"
    assert result["strike"] == 100
    assert result["expiry"] == "2025-01-17"


def test_formats_display():
    parsed = parse_option_symbol("LUMN  270115C00010000")
    assert format_option_display(parsed) == "LUMN Jan'27 $10C"


def test_formats_put_display():
    parsed = parse_option_symbol("AAPL  250117P00100000")
    assert format_option_display(parsed) == "AAPL Jan'25 $100P"


def test_rejects_malformed():
    with pytest.raises(ValueError):
        parse_option_symbol("not an option")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_options.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.options'`.

- [ ] **Step 3: Implement `scripts/options.py`**

```python
"""OCC-style option symbol parser.

Format: 21 characters — 6-char left-padded root, YYMMDD, C/P, 8-digit strike×1000.
Example: "LUMN  270115C00010000" → LUMN Jan 15 2027 $10 call.
"""

from __future__ import annotations

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_option_symbol(symbol: str) -> dict:
    if len(symbol) != 21 or symbol[12] not in ("C", "P"):
        raise ValueError(f"Not an OCC option symbol: {symbol!r}")

    root = symbol[0:6].strip()
    yy, mm, dd = symbol[6:8], symbol[8:10], symbol[10:12]
    kind = "call" if symbol[12] == "C" else "put"
    strike_raw = int(symbol[13:21])
    strike = strike_raw // 1000 if strike_raw % 1000 == 0 else strike_raw / 1000

    return {
        "underlying": root,
        "expiry": f"20{yy}-{mm}-{dd}",
        "type": kind,
        "strike": strike,
    }


def format_option_display(parsed: dict) -> str:
    yy, mm, _dd = parsed["expiry"][2:4], parsed["expiry"][5:7], parsed["expiry"][8:10]
    month = _MONTHS[int(mm) - 1]
    letter = "C" if parsed["type"] == "call" else "P"
    strike = parsed["strike"]
    strike_str = f"{strike:g}"  # drop trailing zeros: 10.0 → "10"
    return f"{parsed['underlying']} {month}'{yy} ${strike_str}{letter}"
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/test_options.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/options.py tests/test_options.py
git commit -m "feat(options): parse OCC symbol into structured dict + display string"
```

---

## Task 3: Flex XML parser

**Files:**
- Create: `scripts/parse.py`
- Test: `tests/test_parse.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parse.py
from scripts.parse import parse_flex_xml
from tests.conftest import read_fixture


def test_parses_positions():
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    positions = result["positions"]
    assert len(positions) == 3
    aapl = next(p for p in positions if p["symbol"] == "AAPL")
    assert aapl["asset_category"] == "STK"
    assert aapl["position_value"] == 30000.0
    assert aapl["currency"] == "USD"


def test_parses_nav_rows():
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    nav = result["nav"]
    assert len(nav) == 3
    assert nav[0] == {"date": "2024-01-02", "total": 100000.0, "total_long": 100000.0, "total_short": 0.0}
    assert nav[-1]["total_long"] == 150000.0


def test_drops_account_id():
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    # account_id should NOT be present — the parser strips it deliberately
    assert "account_id" not in result
    assert "U0000000" not in str(result)


def test_preserves_option_symbol_verbatim():
    # We don't parse OCC here — scripts.options does that. Parser passes symbol through.
    result = parse_flex_xml(read_fixture("sample_flex.xml"))
    opts = [p for p in result["positions"] if p["asset_category"] == "OPT"]
    assert len(opts) == 1
    assert opts[0]["symbol"] == "LUMN  270115C00010000"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_parse.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `scripts/parse.py`**

```python
"""Flex XML → structured dict. Deliberately drops the accountId attribute."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def parse_flex_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)

    positions = []
    for p in root.iter("OpenPosition"):
        positions.append({
            "symbol":         p.attrib["symbol"],
            "asset_category": p.attrib["assetCategory"],
            "position_value": float(p.attrib["positionValue"]),
            "currency":       p.attrib.get("currency", "USD"),
        })

    nav = []
    for row in root.iter("EquitySummaryByReportDateInBase"):
        nav.append({
            "date":        row.attrib["reportDate"],
            "total":       float(row.attrib["total"]),
            "total_long":  float(row.attrib["totalLong"]),
            "total_short": float(row.attrib["totalShort"]),
        })
    nav.sort(key=lambda r: r["date"])

    return {"positions": positions, "nav": nav}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_parse.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/parse.py tests/test_parse.py
git commit -m "feat(parse): Flex XML → dict; strips accountId"
```

---

## Task 4: Transform — holdings, leverage, option formatting

**Files:**
- Create: `scripts/transform.py`
- Test: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transform.py
from scripts.parse import parse_flex_xml
from scripts.transform import build_holdings, compute_leverage
from tests.conftest import read_fixture


def test_holdings_sum_to_100():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    total = sum(h["percent"] for h in holdings)
    assert abs(total - 100.0) < 0.01


def test_holdings_sorted_descending():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    pcts = [h["percent"] for h in holdings]
    assert pcts == sorted(pcts, reverse=True)


def test_option_formatted_in_display():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    lumn = next(h for h in holdings if h["asset_class"] == "OPT")
    assert lumn["display"] == "LUMN Jan'27 $10C"
    assert lumn["option"]["underlying"] == "LUMN"
    assert lumn["option"]["strike"] == 10


def test_stock_display_equals_symbol():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    aapl = next(h for h in holdings if h["symbol"] == "AAPL")
    assert aapl["display"] == "AAPL"
    assert "option" not in aapl


def test_no_dollar_values_in_output():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    holdings = build_holdings(parsed["positions"])
    for h in holdings:
        assert "position_value" not in h
        assert "position" not in h  # (share count)


def test_compute_leverage():
    parsed = parse_flex_xml(read_fixture("sample_flex.xml"))
    latest = parsed["nav"][-1]
    assert compute_leverage(latest) == 1.25
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_transform.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/transform.py`**

```python
"""Build public holdings list and leverage from parsed Flex data.

Percentages are relative to gross long value (sum of positionValue). Dollars are never
written to the output — only percentages, display strings, and structured option metadata.
"""

from __future__ import annotations

from scripts.options import parse_option_symbol, format_option_display


def build_holdings(positions: list[dict]) -> list[dict]:
    gross_long = sum(p["position_value"] for p in positions)
    if gross_long == 0:
        return []

    out = []
    for p in positions:
        percent = round(p["position_value"] / gross_long * 100, 2)
        row = {
            "symbol":      p["symbol"],
            "display":     p["symbol"],
            "asset_class": p["asset_category"],
            "percent":     percent,
        }
        if p["asset_category"] == "OPT":
            parsed_opt = parse_option_symbol(p["symbol"])
            row["option"] = parsed_opt
            row["display"] = format_option_display(parsed_opt)
            # stable synthetic key for options across runs (used for moves diffing)
            strike = parsed_opt["strike"]
            letter = "C" if parsed_opt["type"] == "call" else "P"
            yymmdd = parsed_opt["expiry"][2:].replace("-", "")
            row["symbol"] = f"{parsed_opt['underlying']}_{yymmdd}{letter}{strike:g}"
        out.append(row)

    out.sort(key=lambda h: h["percent"], reverse=True)
    return out


def compute_leverage(latest_nav: dict) -> float:
    return round(latest_nav["total_long"] / latest_nav["total"], 2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_transform.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/transform.py tests/test_transform.py
git commit -m "feat(transform): build holdings (% of gross long), leverage, option display"
```

---

## Task 5: NAV history (append-only ledger)

**Files:**
- Create: `scripts/nav_history.py`
- Test: `tests/test_nav_history.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_nav_history.py
import json
from scripts.nav_history import load, append_new, to_performance_series


def test_load_missing_returns_empty(tmp_path):
    assert load(tmp_path / "nav.json") == []


def test_load_existing(tmp_path):
    path = tmp_path / "nav.json"
    path.write_text(json.dumps([{"date": "2024-01-02", "total": 100.0}]))
    assert load(path)[0]["date"] == "2024-01-02"


def test_append_new_only_new_dates(tmp_path):
    existing = [
        {"date": "2024-01-02", "total": 100.0, "total_long": 100.0, "total_short": 0.0},
        {"date": "2024-01-03", "total": 102.0, "total_long": 102.0, "total_short": 0.0},
    ]
    incoming = [
        {"date": "2024-01-03", "total": 999.9, "total_long": 999.9, "total_short": 0.0},  # dupe — must NOT override
        {"date": "2024-01-04", "total": 105.0, "total_long": 105.0, "total_short": 0.0},
    ]
    merged = append_new(existing, incoming)
    assert len(merged) == 3
    assert merged[1]["total"] == 102.0  # not overridden
    assert merged[2]["date"] == "2024-01-04"


def test_to_performance_series_normalizes_to_inception():
    ledger = [
        {"date": "2024-01-02", "total": 100.0, "total_long": 100.0, "total_short": 0.0},
        {"date": "2024-06-03", "total": 110.0, "total_long": 110.0, "total_short": 0.0},
        {"date": "2024-12-31", "total": 120.0, "total_long": 120.0, "total_short": 0.0},
    ]
    series = to_performance_series(ledger)
    assert series[0] == {"date": "2024-01-02", "return_pct": 0.0}
    assert series[1]["return_pct"] == 10.0
    assert series[2]["return_pct"] == 20.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_nav_history.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/nav_history.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_nav_history.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/nav_history.py tests/test_nav_history.py
git commit -m "feat(nav_history): append-only ledger with inception-relative returns"
```

---

## Task 6: Recent moves classifier

**Files:**
- Create: `scripts/moves.py`
- Test: `tests/test_moves.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_moves.py
from scripts.moves import classify_moves


def test_open_position():
    prior = []
    today = [{"symbol": "NVDA", "display": "NVDA", "percent": 3.5}]
    moves = classify_moves(today, prior, as_of="2026-04-20")
    assert moves[0]["type"] == "open"
    assert moves[0]["symbol"] == "NVDA"
    assert moves[0]["delta_pp"] == 3.5
    assert moves[0]["to_pct"] == 3.5
    assert moves[0]["from_pct"] == 0


def test_close_position():
    prior = [{"symbol": "TSLA", "display": "TSLA", "percent": 6.2}]
    today = []
    moves = classify_moves(today, prior, as_of="2026-04-02")
    assert moves[0]["type"] == "close"
    assert moves[0]["delta_pp"] == -6.2
    assert moves[0]["from_pct"] == 6.2


def test_add_over_threshold():
    prior = [{"symbol": "AAPL", "display": "AAPL", "percent": 29.9}]
    today = [{"symbol": "AAPL", "display": "AAPL", "percent": 32.0}]
    moves = classify_moves(today, prior, as_of="2026-04-16")
    assert moves[0]["type"] == "add"
    assert moves[0]["delta_pp"] == 2.1


def test_trim_over_threshold():
    prior = [{"symbol": "GOOGL", "display": "GOOGL", "percent": 14.4}]
    today = [{"symbol": "GOOGL", "display": "GOOGL", "percent": 13.0}]
    moves = classify_moves(today, prior, as_of="2026-04-09")
    assert moves[0]["type"] == "trim"
    assert round(moves[0]["delta_pp"], 1) == -1.4


def test_micro_drift_filtered():
    prior = [{"symbol": "MSFT", "display": "MSFT", "percent": 22.0}]
    today = [{"symbol": "MSFT", "display": "MSFT", "percent": 22.3}]
    moves = classify_moves(today, prior, as_of="2026-04-10")
    assert moves == []  # 0.3pp < 0.5pp threshold


def test_sorts_newest_first_when_same_date():
    # All moves share the `as_of` date; sort is stable on symbol then.
    prior = [{"symbol": "A", "display": "A", "percent": 0}]
    today = [
        {"symbol": "B", "display": "B", "percent": 10.0},
        {"symbol": "A", "display": "A", "percent": 0.0},
    ]
    moves = classify_moves(today, prior, as_of="2026-04-20")
    assert len(moves) == 1
    assert moves[0]["symbol"] == "B"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_moves.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/moves.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_moves.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/moves.py tests/test_moves.py
git commit -m "feat(moves): classify open/add/trim/close from snapshot diff"
```

---

## Task 7: Flex Web Service client

**Files:**
- Create: `scripts/flex.py`
- Test: `tests/test_flex.py`

- [ ] **Step 1: Write the failing test** (no network — uses monkeypatched `urlopen`)

```python
# tests/test_flex.py
import io
import pytest
from scripts import flex


class _FakeResp:
    def __init__(self, body: bytes): self._body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self): return self._body


def test_request_statement_returns_ref_code(monkeypatch):
    body = (b'<FlexStatementResponse timestamp="20261231"><Status>Success</Status>'
            b'<ReferenceCode>123456789</ReferenceCode>'
            b'<Url>https://ndcdyn.interactivebrokers.com/.../GetStatement</Url>'
            b'</FlexStatementResponse>')
    monkeypatch.setattr(flex, "_urlopen", lambda url, timeout=30: _FakeResp(body))
    ref = flex.request_statement(token="TOK", query_id="Q")
    assert ref == "123456789"


def test_request_statement_raises_on_error(monkeypatch):
    body = (b'<FlexStatementResponse><Status>Fail</Status>'
            b'<ErrorCode>1012</ErrorCode><ErrorMessage>Token invalid</ErrorMessage>'
            b'</FlexStatementResponse>')
    monkeypatch.setattr(flex, "_urlopen", lambda url, timeout=30: _FakeResp(body))
    with pytest.raises(flex.FlexError, match="1012"):
        flex.request_statement(token="TOK", query_id="Q")


def test_fetch_statement_returns_final_xml(monkeypatch):
    final = b'<?xml version="1.0"?><FlexQueryResponse><dummy/></FlexQueryResponse>'
    monkeypatch.setattr(flex, "_urlopen", lambda url, timeout=30: _FakeResp(final))
    monkeypatch.setattr(flex.time, "sleep", lambda _s: None)
    xml = flex.fetch_statement(token="TOK", ref_code="123")
    assert b"<FlexQueryResponse>" in xml


def test_fetch_statement_polls_on_in_progress(monkeypatch):
    calls = {"n": 0}
    in_progress = (b'<FlexStatementResponse><Status>Warn</Status>'
                   b'<ErrorCode>1019</ErrorCode>'
                   b'<ErrorMessage>Statement generation in progress</ErrorMessage>'
                   b'</FlexStatementResponse>')
    final = b'<FlexQueryResponse><ok/></FlexQueryResponse>'

    def fake(url, timeout=30):
        calls["n"] += 1
        return _FakeResp(in_progress if calls["n"] < 3 else final)

    monkeypatch.setattr(flex, "_urlopen", fake)
    monkeypatch.setattr(flex.time, "sleep", lambda _s: None)
    xml = flex.fetch_statement(token="TOK", ref_code="123")
    assert calls["n"] == 3
    assert b"<ok/>" in xml
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_flex.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `scripts/flex.py`**

```python
"""Thin client for the IBKR Flex Web Service (two-call protocol)."""

from __future__ import annotations

import time
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
SEND = BASE + "/SendRequest"
GET = BASE + "/GetStatement"
VERSION = "3"

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 60


class FlexError(RuntimeError):
    pass


def _urlopen(url: str, timeout: int = 30):
    return urllib.request.urlopen(url, timeout=timeout)


def request_statement(*, token: str, query_id: str) -> str:
    url = f"{SEND}?t={token}&q={query_id}&v={VERSION}"
    with _urlopen(url, timeout=30) as resp:
        body = resp.read()
    root = ET.fromstring(body)
    status = (root.findtext("Status") or "").strip()
    if status != "Success":
        code = root.findtext("ErrorCode") or "?"
        msg = root.findtext("ErrorMessage") or "(no message)"
        raise FlexError(f"Flex SendRequest failed {code}: {msg}")
    ref = root.findtext("ReferenceCode")
    if not ref:
        raise FlexError("Flex SendRequest success but no ReferenceCode")
    return ref.strip()


def fetch_statement(*, token: str, ref_code: str) -> bytes:
    url = f"{GET}?t={token}&q={ref_code}&v={VERSION}"
    deadline = time.time() + POLL_TIMEOUT_S
    while True:
        with _urlopen(url, timeout=30) as resp:
            body = resp.read()
        if body.lstrip().startswith(b"<FlexQueryResponse"):
            return body
        # otherwise it's an error/in-progress envelope
        try:
            root = ET.fromstring(body)
            code = root.findtext("ErrorCode") or ""
            msg = root.findtext("ErrorMessage") or ""
        except ET.ParseError:
            code, msg = "parse", "could not parse response"
        if code == "1019" or "in progress" in msg.lower():
            if time.time() > deadline:
                raise FlexError(f"Flex statement still generating after {POLL_TIMEOUT_S}s")
            time.sleep(POLL_INTERVAL_S)
            continue
        raise FlexError(f"Flex GetStatement failed {code}: {msg}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_flex.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/flex.py tests/test_flex.py
git commit -m "feat(flex): two-call client (SendRequest + polled GetStatement)"
```

---

## Task 8: Benchmark fetcher (Stooq SPY)

**Files:**
- Create: `scripts/benchmark.py`
- Test: `tests/test_benchmark.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_benchmark.py
from scripts import benchmark


class _FakeResp:
    def __init__(self, body): self._body = body
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def read(self): return self._body


STOOQ_CSV = (
    b"Date,Open,High,Low,Close,Volume\n"
    b"2024-01-02,472.16,473.78,470.50,472.65,70000000\n"
    b"2024-06-03,520.10,522.30,518.00,520.44,65000000\n"
    b"2024-12-31,586.08,590.10,585.00,589.36,72000000\n"
)


def test_fetch_spy_daily_closes(monkeypatch):
    monkeypatch.setattr(benchmark, "_urlopen", lambda url, timeout=30: _FakeResp(STOOQ_CSV))
    closes = benchmark.fetch_spy_closes()
    assert closes[0] == {"date": "2024-01-02", "close": 472.65}
    assert closes[-1]["close"] == 589.36


def test_benchmark_series_normalized_to_start():
    closes = [
        {"date": "2024-01-02", "close": 100.0},
        {"date": "2024-06-03", "close": 110.0},
        {"date": "2024-12-31", "close": 125.0},
    ]
    series = benchmark.to_return_series(closes)
    assert series[0]["return_pct"] == 0.0
    assert series[1]["return_pct"] == 10.0
    assert series[2]["return_pct"] == 25.0


def test_aligns_to_inception_date():
    closes = [
        {"date": "2023-01-01", "close": 50.0},   # before inception — discarded
        {"date": "2024-01-02", "close": 100.0},  # inception
        {"date": "2024-06-03", "close": 110.0},
    ]
    series = benchmark.to_return_series(closes, inception_date="2024-01-02")
    assert series[0]["date"] == "2024-01-02"
    assert series[0]["return_pct"] == 0.0
    assert series[-1]["return_pct"] == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_benchmark.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/benchmark.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_benchmark.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/benchmark.py tests/test_benchmark.py
git commit -m "feat(benchmark): Stooq SPY fetcher + inception-aligned return series"
```

---

## Task 9: Seed script (CSV → initial nav_history.json)

**Files:**
- Create: `scripts/seed_nav.py`
- Test: `tests/test_seed_nav.py`
- Create: `tests/fixtures/sample_statement.csv`

- [ ] **Step 1: Create sample CSV fixture**

`tests/fixtures/sample_statement.csv`:
```csv
"Header","Section","...other noise..."
"Data","Trades","...other noise..."
"Header","Net Asset Value","Date","Total","Long","Short"
"Data","Net Asset Value","2023-04-18","250000.00","250000.00","0.00"
"Data","Net Asset Value","2023-04-19","251200.00","251200.00","0.00"
"Data","Net Asset Value","2023-05-01","255300.00","260000.00","-4700.00"
"Header","Something Else","..."
```

Note: IBKR activity statement CSVs use a multi-section format where each row is prefixed with `"Header"` or `"Data"` and the section name. Our parser looks for rows where field 1 is `"Data"` and field 2 is `"Net Asset Value"`.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_seed_nav.py
import json
from pathlib import Path
from scripts.seed_nav import parse_statement_csv, main


def test_extracts_nav_rows_from_csv():
    csv_text = Path("tests/fixtures/sample_statement.csv").read_text(encoding="utf-8")
    ledger = parse_statement_csv(csv_text)
    assert len(ledger) == 3
    assert ledger[0] == {
        "date": "2023-04-18",
        "total": 250000.00,
        "total_long": 250000.00,
        "total_short": 0.00,
    }
    assert ledger[-1]["total_short"] == -4700.00


def test_main_writes_nav_history(tmp_path, monkeypatch):
    csv_path = tmp_path / "stmt.csv"
    csv_path.write_text(Path("tests/fixtures/sample_statement.csv").read_text(encoding="utf-8"))
    out_path = tmp_path / "nav_history.json"
    main([str(csv_path), str(out_path)])
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written[0]["date"] == "2023-04-18"
    assert len(written) == 3
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_seed_nav.py -v
```
Expected: FAIL.

- [ ] **Step 4: Implement `scripts/seed_nav.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_seed_nav.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/seed_nav.py tests/test_seed_nav.py tests/fixtures/sample_statement.csv
git commit -m "feat(seed_nav): one-time CSV → nav_history.json bootstrap"
```

---

## Task 10: Main orchestrator (`fetch_snapshot.py`)

**Files:**
- Create: `scripts/fetch_snapshot.py`
- Test: `tests/test_fetch_snapshot.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch_snapshot.py
import json
from pathlib import Path

from scripts import fetch_snapshot
from tests.conftest import read_fixture


def test_build_snapshot_privacy_properties():
    """Integration test: the final snapshot dict must be free of identifiers."""
    xml = read_fixture("sample_flex.xml")
    nav_ledger = [
        {"date": "2024-01-02", "total": 100000.0, "total_long": 100000.0, "total_short": 0.0},
        {"date": "2024-06-03", "total": 110000.0, "total_long": 130000.0, "total_short": -20000.0},
        {"date": "2024-12-31", "total": 120000.0, "total_long": 150000.0, "total_short": -30000.0},
    ]
    spy_series = [
        {"date": "2024-01-02", "return_pct": 0.0},
        {"date": "2024-12-31", "return_pct": 15.0},
    ]
    prior_holdings = []  # all positions "opened" today

    snap = fetch_snapshot.build_snapshot(
        flex_xml=xml,
        nav_ledger=nav_ledger,
        spy_series=spy_series,
        prior_holdings=prior_holdings,
        today="2024-12-31",
    )

    serialized = json.dumps(snap)
    assert "U0000000" not in serialized          # account id stripped
    assert "positionValue" not in serialized     # dollar field stripped
    assert "accountId" not in serialized.lower() # nothing that looks like an id

    assert snap["nav"]["leverage"] == 1.25
    assert abs(sum(h["percent"] for h in snap["holdings"]) - 100.0) < 0.01
    assert snap["performance"]["benchmark"]["ticker"] == "SPY"


def test_build_snapshot_recent_moves_classifies_opens():
    xml = read_fixture("sample_flex.xml")
    nav_ledger = [{"date": "2024-12-31", "total": 120000.0, "total_long": 150000.0, "total_short": -30000.0}]
    snap = fetch_snapshot.build_snapshot(
        flex_xml=xml,
        nav_ledger=nav_ledger,
        spy_series=[{"date": "2024-12-31", "return_pct": 0.0}],
        prior_holdings=[],
        today="2024-12-31",
    )
    move_types = {m["type"] for m in snap["recent_moves"]}
    assert move_types == {"open"}  # all 3 positions are new
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_fetch_snapshot.py -v
```
Expected: FAIL.

- [ ] **Step 3: Implement `scripts/fetch_snapshot.py`**

```python
"""Daily snapshot orchestrator — run by GitHub Actions.

Pipeline:
  1. Call Flex (SendRequest + GetStatement) for the latest XML.
  2. Parse it into {positions, nav}.
  3. Merge new NAV rows into the persistent ledger.
  4. Refresh SPY benchmark from Stooq (fallback: reuse committed cache).
  5. Build public snapshot.json (percentages only, no identifiers).
  6. Atomically write data/snapshot.json + data/nav_history.json + data/benchmark_history.json.

Entrypoint: python -m scripts.fetch_snapshot
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

from scripts import flex, parse, transform, nav_history, moves, benchmark

DATA = Path("data")
SNAPSHOT_PATH   = DATA / "snapshot.json"
NAV_PATH        = DATA / "nav_history.json"
BENCHMARK_PATH  = DATA / "benchmark_history.json"

VERSION = 1


def build_snapshot(*, flex_xml: str, nav_ledger: list[dict], spy_series: list[dict],
                   prior_holdings: list[dict], today: str) -> dict:
    parsed = parse.parse_flex_xml(flex_xml)
    holdings = transform.build_holdings(parsed["positions"])

    latest_nav = nav_ledger[-1]
    leverage = transform.compute_leverage(latest_nav)

    perf_portfolio = nav_history.to_performance_series(nav_ledger)
    inception = nav_ledger[0]["date"]

    recent = moves.classify_moves(holdings, prior_holdings, as_of=today)

    return {
        "version":        VERSION,
        "updated_at":     today,
        "inception_date": inception,
        "nav":            {"leverage": leverage},
        "holdings":       holdings,
        "performance": {
            "portfolio": perf_portfolio,
            "benchmark": {"ticker": "SPY", "series": spy_series},
        },
        "recent_moves": recent,
    }


def _atomic_write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_prior_holdings_30d_ago() -> list[dict]:
    """Read data/snapshot.json as it existed ~30 days ago via git history.

    Returns [] when:
      - the repo has no commit from that far back (brand-new repo)
      - the file didn't exist yet at that commit (first run)
    """
    import subprocess
    try:
        sha = subprocess.run(
            ["git", "rev-list", "-1", "--before=30 days ago", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if not sha:
            return []
        result = subprocess.run(
            ["git", "show", f"{sha}:data/snapshot.json"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return []  # file didn't exist at that commit
        return json.loads(result.stdout).get("holdings", [])
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return []


def main() -> int:
    token = os.environ["IBKR_FLEX_TOKEN"]
    query_id = os.environ["IBKR_FLEX_QUERY_ID"]

    DATA.mkdir(exist_ok=True)

    # 1+2. Flex → XML → parsed
    ref = flex.request_statement(token=token, query_id=query_id)
    xml_bytes = flex.fetch_statement(token=token, ref_code=ref)
    parsed = parse.parse_flex_xml(xml_bytes.decode("utf-8"))

    # 3. Merge NAV into ledger
    existing_nav = nav_history.load(NAV_PATH)
    merged_nav = nav_history.append_new(existing_nav, parsed["nav"])
    nav_history.save(NAV_PATH, merged_nav)

    # 4. Benchmark — resilient to Stooq outage
    inception = merged_nav[0]["date"]
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
        nav_ledger=merged_nav,
        spy_series=spy_series,
        prior_holdings=prior_holdings,
        today=today,
    )
    _atomic_write_json(SNAPSHOT_PATH, snap)
    print(f"wrote {SNAPSHOT_PATH} · holdings={len(snap['holdings'])} · leverage={snap['nav']['leverage']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetch_snapshot.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```
Expected: all tests pass (27+ total across tasks 2–10).

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_snapshot.py tests/test_fetch_snapshot.py
git commit -m "feat(fetch_snapshot): orchestrator — Flex → transform → snapshot.json"
```

---

## Task 11: Frontend — HTML + CSS scaffold (dark theme, responsive)

**Files:**
- Create: `public/index.html`
- Create: `public/style.css`

- [ ] **Step 1: Create `public/style.css`**

```css
:root {
  --accent-from: #8a5bff;
  --accent-to:   #4ad6ff;
  --positive:    #7affaa;
  --negative:    #ffb84a;

  --bg-0: #04030e;
  --bg-1: #0b0720;
  --bg-card: rgba(255, 255, 255, 0.02);
  --border:  rgba(255, 255, 255, 0.05);
  --text-primary:   #e9e4ff;
  --text-secondary: #a79dc9;
  --text-muted:     #6e6792;
}

:root[data-theme="light"] {
  --bg-0: #fbfaff;
  --bg-1: #ffffff;
  --bg-card: rgba(10, 7, 24, 0.03);
  --border: rgba(10, 7, 24, 0.08);
  --text-primary:   #0b0720;
  --text-secondary: #4b446b;
  --text-muted:     #8a84a8;
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  min-height: 100vh;
  background:
    radial-gradient(60% 80% at 0% 0%, rgba(138,91,255,.18), transparent 60%),
    radial-gradient(50% 70% at 100% 0%, rgba(74,214,255,.12), transparent 60%),
    linear-gradient(180deg, var(--bg-1), var(--bg-0) 60%);
  color: var(--text-primary);
  font-family: ui-sans-serif, -apple-system, "Inter", system-ui, sans-serif;
  line-height: 1.5;
}

.container { max-width: 1100px; margin: 0 auto; padding: 22px 22px 60px; container-type: inline-size; }

/* ----- Header ----- */
.pg-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; gap: 8px; }
.pg-brand  { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 17px; letter-spacing: -.01em; }
.pg-header-right { display: flex; align-items: center; gap: 10px; font-size: 11px; color: var(--text-secondary); }
.pg-chip   { font-size: 9px; padding: 4px 9px; border-radius: 999px; letter-spacing: .1em; text-transform: uppercase; white-space: nowrap; border: 1px solid; }
.pg-chip--ok     { background: rgba(122,255,170,.12); color: var(--positive); border-color: rgba(122,255,170,.22); }
.pg-chip--warn   { background: rgba(255,184,74,.12); color: var(--negative); border-color: rgba(255,184,74,.22); }
.pg-chip--muted  { background: var(--bg-card); color: var(--text-secondary); border-color: var(--border); }
.pg-toggle { width: 30px; height: 30px; border-radius: 8px; background: var(--bg-card); border: 1px solid var(--border); display: grid; place-items: center; cursor: pointer; font-size: 13px; color: var(--text-primary); }

/* ----- Hero ----- */
.pg-hero { margin-bottom: 32px; }
.pg-hero-top { display: flex; flex-direction: column; gap: 14px; margin-bottom: 14px; }
.pg-eyebrow { font-size: 10px; letter-spacing: .22em; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 6px; }
.pg-bignum {
  font-size: 34px; font-weight: 700; letter-spacing: -.02em; line-height: 1;
  background: linear-gradient(90deg, var(--text-primary), #b9a5ff 60%, var(--positive));
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.pg-bignum-sub { font-size: 12px; color: var(--text-secondary); margin-top: 6px; }
.pg-delta { color: var(--positive); font-weight: 600; }
.pg-ranges { display: flex; gap: 4px; background: var(--bg-card); padding: 4px; border-radius: 10px; border: 1px solid var(--border); align-self: flex-start; }
.pg-range  { font-size: 10px; padding: 6px 10px; border-radius: 7px; color: var(--text-secondary); cursor: pointer; background: transparent; border: 0; font-family: inherit; }
.pg-range.is-active { background: linear-gradient(135deg, rgba(138,91,255,.35), rgba(74,214,255,.25)); color: #fff; }

.pg-chart { width: 100%; height: 200px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 14px; }
.pg-legend { display: flex; gap: 16px; margin-top: 10px; font-size: 11px; color: var(--text-secondary); flex-wrap: wrap; }
.pg-legend .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }

/* ----- Section heads ----- */
.pg-section-title { display: flex; justify-content: space-between; align-items: baseline; margin: 28px 0 10px; gap: 10px; flex-wrap: wrap; }
.pg-section-title h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--text-primary); }
.pg-section-title .hint { font-size: 10px; color: var(--text-muted); }

/* ----- Holdings ----- */
.pg-holdings { display: grid; grid-template-columns: 1fr; gap: 16px; }
.pg-donut-wrap { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; align-items: center; }
.pg-donut { width: 170px; height: 170px; border-radius: 50%; display: grid; place-items: center; position: relative; box-shadow: 0 0 50px rgba(138,91,255,.35); }
.pg-donut::after { content: ""; width: 110px; height: 110px; border-radius: 50%; background: radial-gradient(circle, var(--bg-0) 60%, var(--bg-1) 100%); position: absolute; }
.pg-donut-center { position: relative; z-index: 1; text-align: center; }
.pg-donut-count  { font-size: 24px; font-weight: 700; }
.pg-donut-label  { font-size: 9px; letter-spacing: .22em; color: var(--text-secondary); text-transform: uppercase; }
.pg-rows { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 4px 0; }
.pg-row  { display: grid; grid-template-columns: 10px 54px 1fr 54px; align-items: center; gap: 10px; padding: 11px 16px; font-size: 12px; border-bottom: 1px solid var(--border); }
.pg-row:last-child { border-bottom: none; }
.pg-row .sym { font-weight: 600; }
.pg-row .bar { height: 5px; background: rgba(255,255,255,.06); border-radius: 999px; overflow: hidden; position: relative; }
.pg-row .bar > span { position: absolute; inset: 0 auto 0 0; background: linear-gradient(90deg, var(--accent-from), var(--accent-to)); border-radius: 999px; }
.pg-row .pct { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; color: var(--text-primary); }
.pg-dot { width: 9px; height: 9px; border-radius: 50%; }

/* ----- Recent Activity ----- */
.pg-moves { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 4px 0; }
.pg-move  { display: grid; grid-template-columns: 30px 1fr; align-items: start; gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.pg-move:last-child { border-bottom: none; }
.pg-move-icon { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; font-size: 12px; font-weight: 700; }
.pg-move-body { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.pg-move-head { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.pg-move-action { font-size: 9px; letter-spacing: .16em; text-transform: uppercase; color: var(--text-secondary); font-weight: 600; }
.pg-move-time   { font-size: 10px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.pg-move-text   { font-size: 12px; color: var(--text-primary); line-height: 1.45; }
.pg-move-text .sym { font-weight: 600; }
.m-open  { background: rgba(122,255,170,.12); color: var(--positive); border: 1px solid rgba(122,255,170,.22); }
.m-add   { background: rgba(74,214,255,.12); color: #4ad6ff; border: 1px solid rgba(74,214,255,.22); }
.m-trim  { background: rgba(255,184,74,.12); color: var(--negative); border: 1px solid rgba(255,184,74,.22); }
.m-close { background: rgba(255,107,214,.12); color: #ff6bd6; border: 1px solid rgba(255,107,214,.22); }
.chg-pos { color: var(--positive); }
.chg-neg { color: var(--negative); }

.pg-empty { padding: 22px; text-align: center; color: var(--text-muted); font-size: 12px; }

.pg-footer { margin-top: 28px; font-size: 10px; color: var(--text-muted); display: flex; flex-direction: column; gap: 6px; }

/* ----- Responsive (≥720px) ----- */
@container (min-width: 720px) {
  .container   { padding: 28px 36px 80px; }
  .pg-header   { margin-bottom: 32px; }
  .pg-header-right { font-size: 12px; }
  .pg-chip     { font-size: 10px; }
  .pg-hero-top { flex-direction: row; justify-content: space-between; align-items: flex-end; }
  .pg-ranges   { align-self: auto; }
  .pg-bignum   { font-size: 44px; }
  .pg-bignum-sub { font-size: 13px; }
  .pg-chart    { height: 260px; padding: 18px; }
  .pg-holdings { grid-template-columns: 280px 1fr; gap: 24px; }
  .pg-donut    { width: 210px; height: 210px; }
  .pg-donut::after { width: 140px; height: 140px; }
  .pg-donut-count  { font-size: 28px; }
  .pg-row      { grid-template-columns: 14px 70px 1fr 60px; padding: 12px 22px; font-size: 13px; }
  .pg-move     { grid-template-columns: 32px 1fr; padding: 14px 22px; }
  .pg-move-icon { width: 30px; height: 30px; }
  .pg-move-text { font-size: 13px; }
  .pg-footer   { flex-direction: row; justify-content: space-between; font-size: 11px; }
}
```

- [ ] **Step 2: Create `public/index.html`**

```html
<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Danomix · Portfolio</title>
  <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg" />
  <link rel="stylesheet" href="/vendor/uPlot.min.css" />
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <div class="container">

    <header class="pg-header">
      <div class="pg-brand">
        <svg width="28" height="28" viewBox="0 0 40 40" aria-hidden="true">
          <defs><linearGradient id="brandG" x1="0" x2="1" y1="1" y2="0">
            <stop offset="0%" stop-color="#8a5bff"/><stop offset="100%" stop-color="#4ad6ff"/>
          </linearGradient></defs>
          <rect x="6"  y="22" width="6" height="12" rx="2" fill="url(#brandG)" opacity="0.55"/>
          <rect x="16" y="14" width="6" height="20" rx="2" fill="url(#brandG)" opacity="0.8"/>
          <rect x="26" y="6"  width="6" height="28" rx="2" fill="url(#brandG)"/>
        </svg>
        <span>Danomix</span>
      </div>
      <div class="pg-header-right">
        <span class="pg-chip pg-chip--ok" id="chipUpdated">● Loading…</span>
        <span class="pg-chip pg-chip--muted" id="chipLeverage">Leverage —</span>
        <button class="pg-toggle" id="themeToggle" type="button" aria-label="Toggle theme">☾</button>
      </div>
    </header>

    <section class="pg-hero">
      <div class="pg-hero-top">
        <div>
          <div class="pg-eyebrow">All-Time Return · Since Inception</div>
          <div class="pg-bignum" id="returnBig">—</div>
          <div class="pg-bignum-sub" id="returnSub">&nbsp;</div>
        </div>
        <div class="pg-ranges" id="ranges" role="tablist">
          <button class="pg-range" data-range="ytd"  role="tab">YTD</button>
          <button class="pg-range" data-range="1y"   role="tab">1Y</button>
          <button class="pg-range" data-range="3y"   role="tab">3Y</button>
          <button class="pg-range is-active" data-range="all" role="tab">All</button>
        </div>
      </div>
      <div class="pg-chart" id="perfChart"></div>
      <div class="pg-legend">
        <span><span class="dot" style="background:linear-gradient(90deg,#8a5bff,#4ad6ff)"></span>Portfolio</span>
        <span><span class="dot" style="background:#4ad6ff;opacity:.6"></span>S&amp;P 500</span>
      </div>
    </section>

    <div class="pg-section-title"><h3>Current Holdings</h3><span class="hint">Percent of portfolio</span></div>
    <section class="pg-holdings">
      <div class="pg-donut-wrap">
        <div class="pg-donut" id="donut" style="background: conic-gradient(#333 0 100%)">
          <div class="pg-donut-center">
            <div class="pg-donut-count" id="holdingCount">—</div>
            <div class="pg-donut-label">Holdings</div>
          </div>
        </div>
      </div>
      <div class="pg-rows" id="holdingRows"></div>
    </section>

    <div class="pg-section-title"><h3>Recent Activity</h3><span class="hint">Last 30 days · Changes of 0.5pp or more</span></div>
    <section class="pg-moves" id="movesList">
      <div class="pg-empty">Loading…</div>
    </section>

    <footer class="pg-footer">
      <span>Data source: Interactive Brokers · End-of-day snapshot</span>
      <span>For informational purposes only. Not investment advice. Past performance is not indicative of future results.</span>
    </footer>

  </div>

  <script src="/vendor/uPlot.iife.min.js"></script>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Visual smoke check**

```bash
cd public && python -m http.server 8000
```
Open `http://localhost:8000/` in a browser. Expected:
- Page loads without JS errors.
- Header shows "Danomix" + placeholder chips.
- Hero shows "—" placeholders.
- Holdings and recent activity sections show empty loading states.
- Toggle button visible but non-functional yet.

- [ ] **Step 4: Commit**

```bash
git add public/index.html public/style.css
git commit -m "feat(frontend): HTML scaffold + dark/light CSS with container-query responsive"
```

---

## Task 12: Frontend — JSON load, holdings donut + rows, leverage chip

**Files:**
- Create: `public/app.js`

- [ ] **Step 1: Create `public/app.js` (initial version — data binding for everything except the chart and moves)**

```javascript
const PALETTE = ["#8a5bff", "#4ad6ff", "#ff6bd6", "#ffb84a", "#7affaa",
                 "#b9a5ff", "#ff9a9a", "#a5e6ff", "#d3c9ff", "#ffd57a"];
const MOVE_ICON = { open: "+", add: "▲", trim: "▼", close: "×" };
const MOVE_LABEL = {
  open:  "Opened Position",
  add:   "Increased Position",
  trim:  "Reduced Position",
  close: "Closed Position",
};

function formatDateLong(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US",
    { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

function businessDaysBetween(isoA, isoB) {
  const a = new Date(isoA + "T00:00:00Z");
  const b = new Date(isoB + "T00:00:00Z");
  let count = 0;
  const step = new Date(a);
  while (step < b) {
    step.setUTCDate(step.getUTCDate() + 1);
    const dow = step.getUTCDay();
    if (dow !== 0 && dow !== 6) count += 1;
  }
  return count;
}

function renderHeaderChips(snap) {
  const chip = document.getElementById("chipUpdated");
  const todayIso = new Date().toISOString().slice(0, 10);
  const businessDaysOld = businessDaysBetween(snap.updated_at, todayIso);
  if (businessDaysOld > 4) {
    chip.className = "pg-chip pg-chip--warn";
    chip.textContent = "⚠ Last updated " + formatDateLong(snap.updated_at);
  } else {
    chip.className = "pg-chip pg-chip--ok";
    chip.textContent = "● Updated " + formatDateLong(snap.updated_at);
  }
  document.getElementById("chipLeverage").textContent =
    "Leverage " + snap.nav.leverage.toFixed(2) + "×";
}

function renderDonut(holdings) {
  const el = document.getElementById("donut");
  let acc = 0;
  const stops = holdings.map((h, i) => {
    const from = acc;
    acc += h.percent;
    const color = PALETTE[i % PALETTE.length];
    return `${color} ${from}% ${acc}%`;
  });
  if (acc < 100) stops.push(`#2b244a ${acc}% 100%`);
  el.style.background = `conic-gradient(${stops.join(",")})`;
  document.getElementById("holdingCount").textContent = holdings.length;
}

function renderHoldingRows(holdings) {
  const host = document.getElementById("holdingRows");
  host.innerHTML = "";
  holdings.forEach((h, i) => {
    const color = PALETTE[i % PALETTE.length];
    const row = document.createElement("div");
    row.className = "pg-row";
    row.innerHTML = `
      <span class="pg-dot" style="background:${color}"></span>
      <span class="sym">${h.display}</span>
      <span class="bar"><span style="width:${Math.min(h.percent, 100)}%"></span></span>
      <span class="pct">${h.percent.toFixed(1)}%</span>
    `;
    host.appendChild(row);
  });
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("themeToggle").textContent = theme === "dark" ? "☾" : "☀";
}

function setupThemeToggle() {
  const stored = localStorage.getItem("theme");
  applyTheme(stored === "light" ? "light" : "dark");
  document.getElementById("themeToggle").addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    localStorage.setItem("theme", next);
    applyTheme(next);
  });
}

async function main() {
  setupThemeToggle();
  const res = await fetch("/data/snapshot.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("snapshot.json not available: " + res.status);
  const snap = await res.json();

  renderHeaderChips(snap);
  renderDonut(snap.holdings);
  renderHoldingRows(snap.holdings);

  window._snap = snap;  // expose for later tasks
}

main().catch(err => {
  console.error(err);
  document.getElementById("chipUpdated").textContent = "⚠ Data unavailable";
  document.getElementById("chipUpdated").className = "pg-chip pg-chip--warn";
});
```

- [ ] **Step 2: Create a temporary `data/snapshot.json` fixture for local testing**

```bash
mkdir -p data
cat > data/snapshot.json <<'JSON'
{
  "version": 1,
  "updated_at": "2026-04-23",
  "inception_date": "2023-04-18",
  "nav": { "leverage": 1.83 },
  "holdings": [
    { "symbol": "AAPL", "display": "AAPL", "asset_class": "STK", "percent": 32.0 },
    { "symbol": "MSFT", "display": "MSFT", "asset_class": "STK", "percent": 22.0 },
    { "symbol": "NVDA", "display": "NVDA", "asset_class": "STK", "percent": 18.0 },
    { "symbol": "GOOGL", "display": "GOOGL", "asset_class": "STK", "percent": 13.0 },
    { "symbol": "META", "display": "META", "asset_class": "STK", "percent": 10.0 },
    { "symbol": "Cash", "display": "Cash", "asset_class": "CASH", "percent": 5.0 }
  ],
  "performance": {
    "portfolio": [{ "date": "2023-04-18", "return_pct": 0 }, { "date": "2026-04-22", "return_pct": 187.4 }],
    "benchmark": { "ticker": "SPY", "series": [{ "date": "2023-04-18", "return_pct": 0 }, { "date": "2026-04-22", "return_pct": 74.9 }] }
  },
  "recent_moves": []
}
JSON
```

- [ ] **Step 3: Visual smoke test**

```bash
python -m http.server 8000
```
From the repo root. Open `http://localhost:8000/public/index.html`. Expected:
- Header chips now populate: "● Updated April 23, 2026" and "Leverage 1.83×"
- Donut chart shows segmented rings in the palette colors
- Holding count ("6") in donut center
- Six rows render with dot + symbol + absolute-scaled bar + percentage
- Theme toggle flips the whole page between dark and light, persists across reload

- [ ] **Step 4: Commit**

```bash
git add public/app.js data/snapshot.json
git commit -m "feat(frontend): fetch snapshot, render donut + holdings rows, theme toggle"
```

---

## Task 13: Frontend — performance chart (uPlot)

**Files:**
- Modify: `public/app.js`

- [ ] **Step 1: Add chart rendering to `public/app.js`**

Add the following functions at the top (after the constants) and update `main()`:

```javascript
function buildChartSeries(snap) {
  const pf = snap.performance.portfolio;
  const bm = snap.performance.benchmark.series;
  const bmByDate = new Map(bm.map(p => [p.date, p.return_pct]));

  const timestamps = pf.map(p => new Date(p.date + "T00:00:00Z").getTime() / 1000);
  const portfolioPct = pf.map(p => p.return_pct);
  const benchmarkPct = pf.map(p => bmByDate.has(p.date) ? bmByDate.get(p.date) : null);
  return [timestamps, portfolioPct, benchmarkPct];
}

function filterByRange(series, range) {
  const [ts, pf, bm] = series;
  if (range === "all") return series;
  const now = ts[ts.length - 1];
  const cutoff =
    range === "ytd" ? new Date(Date.UTC(new Date().getUTCFullYear(), 0, 1)).getTime() / 1000 :
    range === "1y"  ? now - 365 * 24 * 3600 :
    range === "3y"  ? now - 3 * 365 * 24 * 3600 : 0;
  const idx = ts.findIndex(t => t >= cutoff);
  if (idx <= 0) return series;
  return [ts.slice(idx), pf.slice(idx), bm.slice(idx)];
}

let chartInstance = null;

function renderChart(series) {
  const host = document.getElementById("perfChart");
  host.innerHTML = "";

  const { width, height } = host.getBoundingClientRect();
  const opts = {
    width: Math.max(300, width),
    height: Math.max(180, height),
    padding: [8, 4, 4, 4],
    scales: { x: { time: true } },
    axes: [
      { stroke: "#6e6792", grid: { stroke: "rgba(255,255,255,0.04)" } },
      {
        stroke: "#6e6792",
        grid: { stroke: "rgba(255,255,255,0.04)" },
        values: (_, ticks) => ticks.map(v => (v >= 0 ? "+" : "") + v.toFixed(0) + "%"),
      },
    ],
    series: [
      {},
      {
        label: "Portfolio",
        stroke: "#8a5bff",
        width: 2.5,
        fill: "rgba(138,91,255,0.15)",
        points: { show: false },
      },
      {
        label: "S&P 500",
        stroke: "#4ad6ff",
        width: 2,
        dash: [4, 4],
        points: { show: false },
      },
    ],
    legend: { show: false },
  };

  chartInstance = new uPlot(opts, series, host);
}

function renderHero(snap, range) {
  const pf = snap.performance.portfolio;
  const bm = snap.performance.benchmark.series;
  const now = pf[pf.length - 1];
  document.getElementById("returnBig").textContent =
    (now.return_pct >= 0 ? "+" : "") + now.return_pct.toFixed(1) + "%";

  const bmNow = bm[bm.length - 1];
  if (bmNow) {
    const out = (now.return_pct - bmNow.return_pct).toFixed(1);
    document.getElementById("returnSub").innerHTML =
      `S&amp;P 500 <span class="pg-delta">${bmNow.return_pct >= 0 ? "+" : ""}${bmNow.return_pct.toFixed(1)}%</span> · ` +
      `Outperformance <span class="pg-delta">${out >= 0 ? "+" : ""}${out} pp</span>`;
  }
}

function setupRangeTabs(snap) {
  const series = buildChartSeries(snap);
  document.querySelectorAll("#ranges .pg-range").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#ranges .pg-range").forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      const filtered = filterByRange(series, btn.dataset.range);
      renderChart(filtered);
    });
  });
  renderChart(series);
  window.addEventListener("resize", () => {
    if (!chartInstance) return;
    const host = document.getElementById("perfChart");
    const { width } = host.getBoundingClientRect();
    chartInstance.setSize({ width: Math.max(300, width), height: chartInstance.height });
  });
}
```

Then update `main()` to call the new functions:

```javascript
async function main() {
  setupThemeToggle();
  const res = await fetch("/data/snapshot.json", { cache: "no-cache" });
  if (!res.ok) throw new Error("snapshot.json not available: " + res.status);
  const snap = await res.json();

  renderHeaderChips(snap);
  renderHero(snap, "all");
  renderDonut(snap.holdings);
  renderHoldingRows(snap.holdings);
  setupRangeTabs(snap);

  window._snap = snap;
}
```

- [ ] **Step 2: Enrich the test-fixture snapshot with a more realistic series**

Replace the fixture you wrote in Task 12 with one that has more points so the chart has visible shape:

```bash
python -c "
import json, random
random.seed(7)
start = '2023-04-18'
dates = []
from datetime import date, timedelta
d = date.fromisoformat(start)
end = date(2026, 4, 22)
v = 100.0; bv = 100.0
pf, bm = [], []
while d <= end:
    if d.weekday() < 5:
        v  *= 1 + random.gauss(0.0008, 0.012)
        bv *= 1 + random.gauss(0.0004, 0.008)
        pf.append({'date': d.isoformat(), 'return_pct': round(v - 100, 2)})
        bm.append({'date': d.isoformat(), 'return_pct': round(bv - 100, 2)})
    d += timedelta(days=1)

snap = {
  'version': 1, 'updated_at': '2026-04-23', 'inception_date': '2023-04-18',
  'nav': {'leverage': 1.83},
  'holdings': [
    {'symbol':'AAPL','display':'AAPL','asset_class':'STK','percent':32.0},
    {'symbol':'MSFT','display':'MSFT','asset_class':'STK','percent':22.0},
    {'symbol':'NVDA','display':'NVDA','asset_class':'STK','percent':18.0},
    {'symbol':'GOOGL','display':'GOOGL','asset_class':'STK','percent':13.0},
    {'symbol':'META','display':'META','asset_class':'STK','percent':10.0},
    {'symbol':'Cash','display':'Cash','asset_class':'CASH','percent':5.0}
  ],
  'performance': {'portfolio': pf, 'benchmark': {'ticker':'SPY','series': bm}},
  'recent_moves': []
}
open('data/snapshot.json','w').write(json.dumps(snap, indent=2))
print('wrote', len(pf), 'days')
"
```

- [ ] **Step 3: Visual smoke test**

```bash
python -m http.server 8000
```
Open `http://localhost:8000/public/index.html`. Expected:
- Performance chart renders with two lines: solid gradient portfolio, dashed cyan SPY
- Big hero number reflects latest portfolio return
- Range tabs (YTD / 1Y / 3Y / All) re-render the chart when clicked
- Resizing the window re-fits chart width
- Dark/light toggle still works

- [ ] **Step 4: Commit**

```bash
git add public/app.js data/snapshot.json
git commit -m "feat(frontend): uPlot performance chart with SPY overlay and range tabs"
```

---

## Task 14: Frontend — recent activity section

**Files:**
- Modify: `public/app.js`

- [ ] **Step 1: Add recent-moves rendering to `public/app.js`**

Add this function:

```javascript
function renderMoves(moves) {
  const host = document.getElementById("movesList");
  host.innerHTML = "";
  if (!moves.length) {
    host.innerHTML = `<div class="pg-empty">No significant changes in the last 30 days.</div>`;
    return;
  }
  moves.forEach(m => {
    const chgClass = m.delta_pp >= 0 ? "chg-pos" : "chg-neg";
    const sign = m.delta_pp >= 0 ? "+" : "";
    let body = "";
    if (m.type === "open") {
      body = `Initiated a new position in <span class="sym">${m.display}</span> <span class="${chgClass}">(${m.to_pct.toFixed(1)}%)</span>`;
    } else if (m.type === "close") {
      body = `Fully exited <span class="sym">${m.display}</span>, previously held at ${m.from_pct.toFixed(1)}%`;
    } else if (m.type === "add") {
      body = `Added to <span class="sym">${m.display}</span>, allocation moved from ${m.from_pct.toFixed(1)}% to ${m.to_pct.toFixed(1)}% <span class="${chgClass}">(${sign}${m.delta_pp.toFixed(1)}pp)</span>`;
    } else {  // trim
      body = `Trimmed <span class="sym">${m.display}</span>, allocation moved from ${m.from_pct.toFixed(1)}% to ${m.to_pct.toFixed(1)}% <span class="${chgClass}">(${m.delta_pp.toFixed(1)}pp)</span>`;
    }
    const row = document.createElement("div");
    row.className = "pg-move";
    row.innerHTML = `
      <div class="pg-move-icon m-${m.type}">${MOVE_ICON[m.type]}</div>
      <div class="pg-move-body">
        <div class="pg-move-head">
          <span class="pg-move-action">${MOVE_LABEL[m.type]}</span>
          <span class="pg-move-time">${formatDateLong(m.date)}</span>
        </div>
        <div class="pg-move-text">${body}</div>
      </div>
    `;
    host.appendChild(row);
  });
}
```

Add a call to `renderMoves(snap.recent_moves)` inside `main()` after `renderHoldingRows`:

```javascript
renderHoldingRows(snap.holdings);
renderMoves(snap.recent_moves);
setupRangeTabs(snap);
```

- [ ] **Step 2: Update test fixture with sample moves**

Append this to your local `data/snapshot.json` (replacing the `recent_moves: []`):

```bash
python -c "
import json
snap = json.loads(open('data/snapshot.json').read())
snap['recent_moves'] = [
  {'date':'2026-04-20','type':'open','symbol':'NVDA','display':'NVDA','delta_pp':3.5,'from_pct':0,'to_pct':3.5},
  {'date':'2026-04-16','type':'add','symbol':'AAPL','display':'AAPL','delta_pp':2.1,'from_pct':29.9,'to_pct':32.0},
  {'date':'2026-04-09','type':'trim','symbol':'GOOGL','display':'GOOGL','delta_pp':-1.4,'from_pct':14.4,'to_pct':13.0},
  {'date':'2026-04-02','type':'close','symbol':'TSLA','display':'TSLA','delta_pp':-6.2,'from_pct':6.2,'to_pct':0.0}
]
open('data/snapshot.json','w').write(json.dumps(snap, indent=2))
"
```

- [ ] **Step 3: Visual smoke test**

Refresh `http://localhost:8000/public/index.html`. Expected:
- Recent activity shows four rows: green + (opened), cyan ▲ (added), amber ▼ (trimmed), pink × (closed)
- Each row has uppercase action label + right-aligned date + sentence with the allocation delta
- Resize to ~400px wide (mobile view in DevTools): date labels wrap gracefully, icon column stays intact

- [ ] **Step 4: Also test the empty state**

```bash
python -c "
import json
snap = json.loads(open('data/snapshot.json').read()); snap['recent_moves'] = []
open('data/snapshot.json','w').write(json.dumps(snap, indent=2))
"
```
Refresh — should see *"No significant changes in the last 30 days."* Then restore the moves.

- [ ] **Step 5: Commit**

```bash
git add public/app.js data/snapshot.json
git commit -m "feat(frontend): recent activity section with open/add/trim/close rows"
```

---

## Task 15: CI workflow, favicon, CNAME, README

**Files:**
- Create: `.github/workflows/daily-snapshot.yml`
- Create: `public/assets/favicon.svg`
- Create: `public/CNAME`
- Create: `README.md`

- [ ] **Step 1: Create `.github/workflows/daily-snapshot.yml`**

```yaml
name: Daily Portfolio Snapshot

on:
  schedule:
    - cron: "30 21 * * 1-5"   # 21:30 UTC Mon–Fri (post US close)
  workflow_dispatch:           # manual run button

permissions:
  contents: write

jobs:
  snapshot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # full history needed for 30-day-ago snapshot lookup

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install pytest
        run: pip install pytest

      - name: Run tests
        run: pytest -q

      - name: Fetch and transform
        env:
          IBKR_FLEX_TOKEN:    ${{ secrets.IBKR_FLEX_TOKEN }}
          IBKR_FLEX_QUERY_ID: ${{ secrets.IBKR_FLEX_QUERY_ID }}
        run: python -m scripts.fetch_snapshot

      - name: Commit if changed
        run: |
          git config user.name  "danomix-bot"
          git config user.email "bot@users.noreply.github.com"
          git add data/
          if git diff --cached --quiet; then
            echo "no changes"
          else
            git commit -m "snapshot $(date -I)"
            git push
          fi
```

- [ ] **Step 2: Create `public/assets/favicon.svg`**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="40" height="40">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="1" y2="0">
      <stop offset="0%" stop-color="#8a5bff"/>
      <stop offset="100%" stop-color="#4ad6ff"/>
    </linearGradient>
  </defs>
  <rect x="6"  y="22" width="6" height="12" rx="2" fill="url(#g)" opacity="0.55"/>
  <rect x="16" y="14" width="6" height="20" rx="2" fill="url(#g)" opacity="0.8"/>
  <rect x="26" y="6"  width="6" height="28" rx="2" fill="url(#g)"/>
</svg>
```

- [ ] **Step 3: Create `public/CNAME`**

Single line, no trailing newline:
```
danomix.com
```

- [ ] **Step 4: Create `README.md`**

````markdown
# danomix.com

Public IBKR portfolio dashboard. End-of-day data, updated automatically by GitHub Actions.

## How it works

1. A GitHub Actions cron runs Mon–Fri at 21:30 UTC.
2. It calls the IBKR Flex Web Service with a read-only token.
3. It parses the XML, strips account identifiers and dollar values, and writes `data/snapshot.json` — percentages only.
4. GitHub Pages serves `public/` at `danomix.com`.

## Secrets

Configure in repo **Settings → Secrets and variables → Actions**:

- `IBKR_FLEX_TOKEN` — Flex Web Service token
- `IBKR_FLEX_QUERY_ID` — numeric query ID

## Initial setup

```bash
# 1. One-time seed (local — not in CI)
python -m scripts.seed_nav path/to/activity_statement.csv data/nav_history.json
git add data/nav_history.json
git commit -m "chore: seed NAV history from activity statement"
git push

# 2. Manually trigger the workflow once in GitHub UI (Actions → Daily Portfolio Snapshot → Run workflow)

# 3. Verify data/snapshot.json — no accountId, no dollar values.

# 4. Enable GitHub Pages: Settings → Pages → Source: main, /public directory.

# 5. Point Route 53: CNAME danomix.com → <user>.github.io
```

## Local development

```bash
python -m venv .venv
.venv/bin/pip install pytest
pytest
python -m http.server 8000  # view at http://localhost:8000/public/
```

## Spec and plan

- Design: `docs/superpowers/specs/2026-04-23-danomix-portfolio-design.md`
- Plan:   `docs/superpowers/plans/2026-04-23-danomix-portfolio.md`
````

- [ ] **Step 5: Verify full test suite still passes**

```bash
pytest -v
```
Expected: all tests across tasks 2–10 pass.

- [ ] **Step 6: Remove the local fixture snapshot before shipping**

The `data/snapshot.json` we used for frontend testing has fake numbers. Either:
- Leave it in place and let the first Actions run overwrite it, or
- Delete it to force the first render to show the "Data unavailable" error until the cron populates real data.

Recommendation: delete locally, don't commit:
```bash
rm data/snapshot.json
```

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/daily-snapshot.yml public/assets/favicon.svg public/CNAME README.md
git commit -m "chore: workflow, favicon, CNAME, README"
```

---

## Final acceptance checklist

After all tasks are implemented, before flipping DNS:

- [ ] All pytest tests pass locally (`pytest -v`)
- [ ] Repo pushed to GitHub (public)
- [ ] `IBKR_FLEX_TOKEN` and `IBKR_FLEX_QUERY_ID` added to Actions secrets
- [ ] `data/nav_history.json` seeded and committed (run `scripts/seed_nav.py` locally)
- [ ] Workflow manually triggered (`workflow_dispatch`) — succeeds and commits `data/snapshot.json`
- [ ] Inspect committed `snapshot.json`: grep for account number, `positionValue`, share quantities — none present
- [ ] GitHub Pages enabled: Settings → Pages → Source: `main`, directory: `/public`
- [ ] `<user>.github.io/<repo>/` loads and shows the real portfolio
- [ ] DNS configured at Route 53 (CNAME `danomix.com` → `<user>.github.io`)
- [ ] HTTPS certificate provisioned (up to a few hours after DNS propagates)
- [ ] Mobile view and light-theme toggle both work
