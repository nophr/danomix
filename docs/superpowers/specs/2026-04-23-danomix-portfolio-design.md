# Danomix Portfolio — Design Spec

**Date:** 2026-04-23
**Domain:** danomix.com
**Status:** Design approved, ready for implementation planning

## 1. Goals and non-goals

### Goals
- A public, read-only web page at `danomix.com` that shows the owner's Interactive Brokers portfolio:
  - **Current holdings** as percentages of gross long value
  - **All-time performance** since account inception, with S&P 500 benchmark overlay
  - **Recent activity** — position changes over the last 30 days
- Minimal operational burden: no always-on gateway, no 24/7 server to babysit.
- Strong privacy posture: no dollar values, share counts, trades, cost basis, or account identifiers ever reach the public page.
- Mobile-responsive; dark theme by default with a light-mode toggle.

### Non-goals
- Real-time or intraday data. End-of-day is sufficient.
- Authentication, user accounts, or any dynamic behavior beyond theme toggle and range selection.
- Trade-level execution history (timestamps, prices, venues).
- Broker integration beyond IBKR.
- Server-side rendering or SPA routing.

## 2. Architecture

```
┌──────────────────┐      daily cron      ┌────────────────────────┐
│   IBKR Flex      │ ◄─── HTTPS + token ──│  GitHub Actions runner │
│   Web Service    │ ────── XML ────────► │   (fetch + transform)  │
└──────────────────┘                      └────────────┬───────────┘
                                                       │ commits
                                                       ▼ snapshot.json
                                          ┌────────────────────────┐
                                          │   GitHub repo (public) │
                                          └────────────┬───────────┘
                                                       │ auto-deploy
                                                       ▼
                                          ┌────────────────────────┐
                                          │   GitHub Pages         │
                                          │   danomix.com          │◄── visitors
                                          │   (static HTML + JS)   │
                                          └────────────────────────┘
```

**Trust boundaries:**
- `IBKR_FLEX_TOKEN` and `IBKR_FLEX_QUERY_ID` live only in GitHub Actions encrypted secrets. They are never committed, never in frontend code, never on the web tier.
- Raw IBKR XML lives only in memory inside the Actions runner. It is never written to disk and never committed.
- The committed `data/snapshot.json` is the only file the public page reads. Its contents are deliberately constrained (percentages only, no identifiers — see §5).

**Host:** GitHub Pages. Chosen to consolidate code, cron, and hosting under one vendor and minimize moving parts.
**DNS:** Route 53 `CNAME danomix.com → <user>.github.io` plus an `A` apex record per GitHub Pages' documented IPs. A `CNAME` file in the repo (`public/CNAME` containing `danomix.com`) completes the Pages binding.

## 3. IBKR Flex Query configuration

### 3.1 Query setup (one-time, in IBKR Client Portal)

Path: **Settings → Reporting → Flex Queries → Activity Flex Query → Configure**.

- **Name:** `PublicPortfolio`
- **Sections enabled:**
  - **Positions** (summary mode, not lot) — fields: `Symbol`, `Asset Class`, `Quantity`, `Position Value`, `Currency`. Ensure **all asset classes** are included (Stocks, Options, Futures, etc.) so shorts and derivatives do appear.
  - **Net Asset Value in Base** — fields: `Report Date`, `Total`. (In XML output this section appears as `<EquitySummaryInBase>`.)
- **Sections explicitly disabled:** Trades, Account Information, Cash Report, Tax Lots, and every other section not listed above. Minimizing response content minimizes the sensitive data flowing through the pipeline.
- **Delivery configuration:**
  - Format: **XML**
  - Period: **Last 365 Calendar Days** (IBKR's max for a single Activity Flex Query)
  - Date Format: **yyyy-MM-dd**
  - Time Zone: **UTC**
  - Include Canceled Trades, Currency Rates, Audit Trail: **No**

### 3.2 Flex Web Service token

Path: **Settings → Account Settings → Reporting → Flex Web Service → Configure → Enabled → copy token**.

The token is a long opaque string. It only grants read access to configured Flex Queries on this account; it cannot place trades or transfer funds.

### 3.3 Observed XML structure

The query produces XML of this shape (validated against a live run on 2026-04-23):

```xml
<FlexQueryResponse queryName="PublicPortfolio" type="AF">
  <FlexStatements count="1">
    <FlexStatement accountId="U…" fromDate="…" toDate="…" period="Last365CalendarDays" whenGenerated="…">
      <EquitySummaryInBase>
        <EquitySummaryByReportDateInBase
            reportDate="2026-04-22"
            total="435742.846…"
            totalLong="795067.375…"
            totalShort="-359324.529…" />
        <!-- one row per trading day -->
      </EquitySummaryInBase>
      <OpenPositions>
        <OpenPosition symbol="AAPL"
                      assetCategory="STK"
                      position="100"
                      positionValue="27317"
                      currency="USD" />
        <OpenPosition symbol="LUMN  270115C00010000"
                      assetCategory="OPT"
                      position="25"
                      positionValue="5634.25"
                      currency="USD" />
        <!-- one row per symbol -->
      </OpenPositions>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
```

## 4. Data pipeline

### 4.1 Daily job (`scripts/fetch_snapshot.py`)

Runs in GitHub Actions, Mon–Fri at 21:30 UTC (~5:30pm ET, after US market close).

**Steps:**
1. **Request Flex statement.** `POST https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest?t=<TOKEN>&q=<QUERY_ID>&v=3` → returns a reference code.
2. **Poll for statement.** `GET https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement?t=<TOKEN>&q=<REF_CODE>&v=3`. If IBKR replies with "statement generation in progress," wait 5s and retry. Give up after 60s with a loud failure.
3. **Parse XML.** Using `xml.etree.ElementTree` (stdlib). Extract:
   - `positions[]` from `OpenPosition` elements: `{symbol, assetCategory, position, positionValue, currency}`.
   - `nav_rows[]` from `EquitySummaryByReportDateInBase` elements: `{reportDate, total, totalLong, totalShort}`.
4. **Update NAV ledger.** Load existing `data/nav_history.json` (the persistent durable NAV series, predating the 365-day Flex window). Append any new `{reportDate, total, totalLong, totalShort}` rows that post-date the last entry. Never rewrite older entries.
5. **Fetch benchmark series.** GET SPY daily closes from Stooq (`https://stooq.com/q/d/l/?s=spy.us&i=d`), a free no-key source. Update `data/benchmark_history.json` with any new dates.
6. **Compute derived values:**
   - `allocation.percent[i] = positionValue[i] / sum(positionValue) × 100` (positions sum to 100%).
   - `leverage = totalLong / total` from the latest NAV row.
   - `performance.portfolio[t] = (nav_total[t] / nav_total[0] - 1) × 100`.
   - `performance.benchmark[t] = (spy_close[t] / spy_close[0] - 1) × 100`, aligned to the portfolio's inception date.
   - `recent_moves` — see §4.3.
7. **Parse option symbols.** See §4.4.
8. **Write `data/snapshot.json`** atomically (write to `.tmp`, then rename).
9. **Git commit if changed.** `git diff --cached --quiet || git commit`. No commit means no deploy, which keeps history clean when nothing moved.

### 4.2 One-time historical seed (`scripts/seed_nav.py`)

The account is ~3 years old. Flex only reaches back 365 days, so pre-cron history must be imported once, manually, from the Client Portal's Activity Statement.

**Procedure (one-time):**
1. In IBKR Client Portal: **Reports → Statements → Activity → Custom date range** covering account inception to yesterday.
2. Download as **CSV**.
3. Run `python scripts/seed_nav.py path/to/statement.csv`. The script extracts the daily NAV rows and writes the initial `data/nav_history.json`.
4. Commit.

From that point forward, the daily cron appends new days and the seed script is never needed again.

### 4.3 Recent-moves derivation

Computed purely from `data/nav_history.json` and historical `snapshot.json` state. No separate Flex section needed — the Trades section stays disabled.

**Algorithm:**
1. Load today's holdings (after transform).
2. Walk backward through git history to find `snapshot.json` as of ~30 days ago (nearest commit to `today - 30d`).
3. Build a symbol-keyed delta: `delta[symbol] = today_pct - prior_pct` (0 if absent on either side).
4. Classify each symbol:
   - `prior_pct == 0 && today_pct > 0` → `type: "open"`
   - `prior_pct > 0 && today_pct == 0` → `type: "close"`
   - `delta >= +0.5 pp` → `type: "add"`
   - `delta <= -0.5 pp` → `type: "trim"`
   - otherwise → ignore (micro-drift from price movement, not a real trade)
5. For each classified event, look up the date of the earliest commit that reflects the change (best-effort; fall back to "within last 30 days" label if ambiguous).
6. Emit `recent_moves[]` sorted newest-first.

### 4.4 Option symbol parser

Input (21 chars, OCC-style): e.g. `"LUMN  270115C00010000"`.

- **Root symbol:** chars 0–5, right-trimmed → `"LUMN"`
- **Expiry:** chars 6–11 (`YYMMDD`) → `"2027-01-15"`
- **Type:** char 12 (`C` or `P`) → `"call"` / `"put"`
- **Strike:** chars 13–20 as integer ÷ 1000 → `10`

Output: `{ underlying: "LUMN", expiry: "2027-01-15", type: "call", strike: 10 }`.

Display format: `"<underlying> <Mmm>'<YY> $<strike><C|P>"` → `"LUMN Jan'27 $10C"`.

### 4.5 Tech stack

- **Language:** Python 3.12, stdlib-only. No `requests`, no `pandas`, no `lxml`. `urllib` + `xml.etree.ElementTree` + `json`.
- **Rationale:** minimal supply-chain surface; fast cold start in CI; the transform is pure data munging.

## 5. Public JSON schema (`data/snapshot.json`)

```json
{
  "version": 1,
  "updated_at": "2026-04-23",
  "inception_date": "2023-04-18",
  "nav": { "leverage": 1.83 },

  "holdings": [
    { "symbol": "AAPL", "display": "AAPL", "asset_class": "STK", "percent": 4.78 },
    { "symbol": "GOOGL", "display": "GOOGL", "asset_class": "STK", "percent": 18.41 },
    { "symbol": "LUMN_270115C10",
      "display": "LUMN Jan'27 $10C",
      "asset_class": "OPT",
      "percent": 0.99,
      "option": { "underlying": "LUMN", "expiry": "2027-01-15", "type": "call", "strike": 10 } }
  ],

  "performance": {
    "portfolio": [
      { "date": "2023-04-18", "return_pct": 0.0 },
      { "date": "2026-04-22", "return_pct": 42.3 }
    ],
    "benchmark": {
      "ticker": "SPY",
      "series": [
        { "date": "2023-04-18", "return_pct": 0.0 },
        { "date": "2026-04-22", "return_pct": 31.7 }
      ]
    }
  },

  "recent_moves": [
    { "date": "2026-04-20", "type": "open",  "symbol": "NVDA",  "display": "NVDA",
      "delta_pp": 3.5,  "from_pct": 0.0,  "to_pct": 3.5 },
    { "date": "2026-04-16", "type": "add",   "symbol": "AAPL",  "display": "AAPL",
      "delta_pp": 2.1,  "from_pct": 29.9, "to_pct": 32.0 },
    { "date": "2026-04-09", "type": "trim",  "symbol": "GOOGL", "display": "GOOGL",
      "delta_pp": -1.4, "from_pct": 14.4, "to_pct": 13.0 },
    { "date": "2026-04-02", "type": "close", "symbol": "TSLA",  "display": "TSLA",
      "delta_pp": -6.2, "from_pct": 6.2,  "to_pct": 0.0 }
  ]
}
```

### What is deliberately absent
- Account ID, account holder name, any identifying strings.
- Dollar values, share quantities, position values.
- Cost basis, realized P&L, unrealized P&L.
- Trade execution prices, timestamps, venues, commissions.
- Individual tax lots.

### Field conventions
- `percent`, `return_pct`, `delta_pp`, `leverage` rounded to 2 decimals.
- Dates are ISO 8601 (`YYYY-MM-DD`).
- `holdings` ordered by descending `percent`.
- `recent_moves` ordered newest-first.
- `recent_moves[].type` is one of `"open" | "add" | "trim" | "close"`.

## 6. Frontend

### 6.1 Aesthetic

"Fintech / Gradient" direction. Dark palette:
- Background: radial gradients (purple `#8a5bff` top-left, cyan `#4ad6ff` top-right) fading to near-black (`#04030e`) base.
- Primary text: `#e9e4ff`; secondary: `#a79dc9`.
- Accent gradient: `linear-gradient(90deg, #8a5bff, #4ad6ff)` for charts, active states, and brand.
- Semantic colors: positive `#7affaa` (soft green), negative `#ffb84a` (soft amber).

Typography: system stack (`ui-sans-serif, -apple-system, "Inter", sans-serif`). No web-font load.

Light theme uses the same semantic tokens with inverted lightness values. Toggle persists via `localStorage`; default is dark.

### 6.2 Brand

- Wordmark: **"Danomix"** (capitalized).
- Logo mark: three ascending bars in the accent gradient (Option B from logo exploration). Renders as `public/assets/favicon.svg` for browser favicon; embedded inline in the header for main display.

### 6.3 Layout

Single page, sections top to bottom:

1. **Header** — logo mark + wordmark (left); "Updated <date>" green chip + leverage chip ("Leverage 1.83×") + theme toggle (right).
2. **Hero performance chart** — "All-Time Return · Since Inception" eyebrow; big gradient number (+42.3%); subline showing S&P 500 return and outperformance in percentage points; range tabs (YTD / 1Y / 3Y / All, default All); gradient-stroked portfolio line + dashed cyan SPY line; subtle grid.
3. **Current Holdings** — donut chart (left, stacked on mobile) with center count; ranked rows (right) showing colored dot + symbol + **absolute-scale** percentage bar + percent. Bar width equals the percentage (0–100% track), not relative to the largest holding.
4. **Recent Activity** — 30-day window, ≥0.5pp threshold. Each row: colored icon tile (green plus for opened, cyan up-arrow for added, amber down-arrow for trimmed, pink × for closed) + uppercase action label + descriptive sentence + ISO date. Uses the "Opened Position / Increased Position / Reduced Position / Closed Position" copy pattern.
5. **Footer** — data source attribution, "how it works" link, disclaimer (*For informational purposes only. Not investment advice. Past performance is not indicative of future results.*).

### 6.4 Responsive behavior

Container queries on the page root. Breakpoint at 720px:
- Below 720px: all sections stack vertically; big number shrinks to 34px; chart height reduces to 200px; donut shrinks to 170px; range tabs align left; date labels in Recent Activity truncate (`Apr 20, 2026` → `Apr 20`).
- 720px+: hero number returns to 44px; chart height 260px; holdings lays out as `donut | rows` grid; date labels return to long form.

### 6.5 Charting

- **Performance chart:** `uPlot` (~40KB, no dependencies). Two series. Gradient fill under portfolio line. X-axis: `Date`. Y-axis: percent, formatted `+XX.X%` at gridline tick marks.
- **Donut chart:** hand-rolled SVG with `conic-gradient`. No chart library.
- **Holdings bars:** absolute-scale CSS bars, width equals the percentage.

### 6.6 Client-side logic (`public/app.js`)

- Fetch `/data/snapshot.json` on load.
- Render header, hero, holdings, recent activity.
- Wire up theme toggle and range-tab filtering.
- **Stale-data guard:** if `updated_at` is older than 4 business days, replace the green "Updated" chip with an amber "⚠ Last updated <date>" chip.
- No routing. No SPA. No build step required beyond copying source to `public/`.

## 7. GitHub Actions workflow

`.github/workflows/daily-snapshot.yml`:

```yaml
name: Daily Portfolio Snapshot
on:
  schedule:
    - cron: "30 21 * * 1-5"   # 21:30 UTC Mon–Fri, post-US-close
  workflow_dispatch:           # manual trigger

permissions:
  contents: write

jobs:
  snapshot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Run tests
        run: python -m pytest tests/
      - name: Fetch and transform
        env:
          IBKR_FLEX_TOKEN:    ${{ secrets.IBKR_FLEX_TOKEN }}
          IBKR_FLEX_QUERY_ID: ${{ secrets.IBKR_FLEX_QUERY_ID }}
        run: python scripts/fetch_snapshot.py
      - name: Commit if changed
        run: |
          git config user.name  "danomix-bot"
          git config user.email "bot@users.noreply.github.com"
          git add data/
          git diff --cached --quiet || git commit -m "snapshot $(date -I)"
          git push
```

Secrets (configured once in repo Settings → Secrets and variables → Actions):
- `IBKR_FLEX_TOKEN`
- `IBKR_FLEX_QUERY_ID`

The account ID is never passed in as a secret — the Flex Query itself already scopes to the configured account.

## 8. Error handling

| Failure | Response |
|---|---|
| Flex returns "query in progress" | Poll 5s intervals, up to 60s total, then fail loudly. |
| Flex returns error (bad token, rate limit, maintenance) | Fail the Action; previous `snapshot.json` stays live. No partial write. |
| XML missing `OpenPositions` or `EquitySummaryInBase` | Fail; likely query was reconfigured. |
| Stooq unreachable | Reuse `benchmark_history.json` as of last successful fetch; log warning; still publish the portfolio side. |
| NAV gap (one day missing in series) | Leave the gap; frontend interpolates linearly between known points. |
| No moves above 0.5pp threshold in last 30 days | Publish `recent_moves: []`; frontend renders empty state: *"No significant changes in the last 30 days."* |
| Uncaught exception in script | GitHub Actions email notification; previous snapshot remains live. |

**Observability:** Action run logs in GitHub; email on failure via GitHub's default notifications. No external alerting (Slack, PagerDuty) for a one-user dashboard.

## 9. Testing

### Unit tests (`tests/test_transform.py`, pytest)

Using a redacted fixture XML file in `tests/fixtures/sample_flex.xml`:

- **Privacy assertions:**
  - Account ID is not present in transformed JSON output.
  - No `position` (share quantity) field in output.
  - No `positionValue` (dollar value) field in output.
- **Correctness assertions:**
  - `holdings[*].percent` sums to 100.0 ± 0.01.
  - `leverage = totalLong / total` to 2-decimal precision.
  - Option symbol parser: `"LUMN  270115C00010000"` → `{underlying: "LUMN", expiry: "2027-01-15", type: "call", strike: 10}`, display `"LUMN Jan'27 $10C"`.
  - Moves classifier: opens, adds, trims, closes — each correctly detected from diff.
  - Micro-drift (|delta_pp| < 0.5) is excluded from `recent_moves`.
- **Date handling:**
  - Stale-data guard threshold (4 business days) respects weekends.

### CI integration
`pytest` runs before `fetch_snapshot.py` in the workflow. Test failure aborts the run before any write to `data/`.

### Manual acceptance test (once, before going public)
1. Run the full pipeline locally using real credentials.
2. Inspect `data/snapshot.json` — grep for your account number, grep for any suspicious substrings (e.g., `accountId`, `positionValue`, `markValue`).
3. Open `public/index.html` in a browser; verify dark/light toggle; verify at mobile breakpoint.
4. Push; verify the published site at `<user>.github.io/<repo>/`; flip DNS.

## 10. Repository layout

```
danomix/
├── .github/workflows/
│   └── daily-snapshot.yml
├── scripts/
│   ├── fetch_snapshot.py        # daily cron (run by Actions)
│   └── seed_nav.py              # one-time historical backfill (run locally)
├── data/
│   ├── snapshot.json            # PUBLIC — the file the frontend reads
│   ├── nav_history.json         # durable NAV ledger; grows daily
│   └── benchmark_history.json   # SPY daily closes; grows daily
├── public/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   ├── assets/favicon.svg
│   └── CNAME                    # contains "danomix.com"
├── tests/
│   ├── test_transform.py
│   └── fixtures/
│       └── sample_flex.xml      # redacted fixture
├── docs/superpowers/specs/
│   └── 2026-04-23-danomix-portfolio-design.md
├── .gitignore
└── README.md
```

## 11. Initial setup order

1. `git init` the repo; add `.gitignore` (`.DS_Store`, `*.pyc`, etc.).
2. Create the IBKR Flex Query per §3.1; generate the Flex Web Service token per §3.2.
3. Run `scripts/seed_nav.py` against a Client Portal activity statement CSV to bootstrap `data/nav_history.json`.
4. Create the GitHub repo (public); push initial commit.
5. Add `IBKR_FLEX_TOKEN` and `IBKR_FLEX_QUERY_ID` to repo Actions secrets.
6. Manually trigger the workflow (`workflow_dispatch`) once to verify end-to-end.
7. Inspect the committed `data/snapshot.json` for privacy compliance (§9 acceptance test).
8. Enable GitHub Pages: Settings → Pages → Source: `main` branch, `/public` directory.
9. Add `danomix.com` as custom domain in Pages; update Route 53 records (ALIAS/A to GitHub's Pages IPs, plus `www` CNAME).
10. Verify HTTPS cert provisions (up to a few hours).

## 12. Security posture summary

| Asset | Where it lives | Exposure |
|---|---|---|
| Flex Web Service token | GitHub Actions secret | Encrypted at rest; only materialized in-memory for a ~30-second Action run. |
| Flex Query ID | GitHub Actions secret | Same as above. Useless without the token. |
| Account ID, holder name | IBKR; passes through Actions memory in raw XML | Never written to disk; stripped by transform; never committed. |
| Raw XML (includes dollar values) | Actions runner memory only | Discarded at end of run. |
| Public `snapshot.json` | Repo + served on danomix.com | Contains percentages only — no identifiers, dollar amounts, or quantities. |

Rotation: rotate `IBKR_FLEX_TOKEN` periodically (every 6–12 months, or immediately on suspected compromise) — regenerate in Client Portal and update the GitHub secret.

## 13. Open questions and future work

- **Benchmark choice:** SPY for initial launch. Could add QQQ, VT, or BTC later by extending the transform; no frontend changes needed as long as the JSON shape holds.
- **"How this works" link:** placeholder in the footer. A short explainer page (`public/about.html`) would improve transparency — out of scope for v1.
- **Stale data 4-day threshold:** calibrated for US markets + weekends. May need to relax around long holiday weekends (e.g., Thanksgiving).
- **365-day Flex window rollover:** after 365 days of cron, the oldest day in each Flex response will fall off. The append-only `nav_history.json` already handles this — the Flex window slides while our ledger grows monotonically.
