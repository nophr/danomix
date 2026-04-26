# danomix.com

Public IBKR portfolio dashboard. End-of-day data, updated automatically by GitHub Actions.

## How it works

1. A GitHub Actions cron runs Mon–Fri at 21:30 UTC.
2. It calls the IBKR Flex Web Service with a read-only token. The query enables "Net Asset Value (NAV) in Base" + "Open Positions" with period **Last 365 Calendar Days**.
3. It chain-extends `data/nav_history_pct.json` with new dates — dollars never touch disk in the public repo.
4. It writes `data/snapshot.json` (percentages + holdings, no identifiers, no dollars).
5. GitHub Pages serves `public/` at `danomix.com`.

## Public-repo safety

- `data/snapshot.json` and `data/nav_history_pct.json` contain only percentages.
- `data/nav_history.json` (raw dollar NAV) is **gitignored** — written locally as a personal-analysis artifact only.
- All dollar values from Flex stay in workflow memory; nothing dollar-denominated is ever serialized to a committed file.

## Flex query setup (one-time)

In IBKR Client Portal → Reports → Flex Queries → Activity Flex Query, create a query with:

- **Sections:** Net Asset Value (NAV) in Base, Open Positions
- **Period:** Last 365 Calendar Days
- **Format:** XML

Save and copy the numeric Query ID.

## Secrets

Configure in repo **Settings → Secrets and variables → Actions**:

- `IBKR_FLEX_TOKEN` — Flex Web Service token
- `IBKR_FLEX_QUERY_ID` — numeric query ID

## Initial setup

```bash
# 1. Trigger the workflow once in GitHub UI (Actions → Daily Portfolio Snapshot → Run workflow).
#    First run bootstraps data/nav_history_pct.json from the full 365-day Flex pull
#    and commits it back to the repo.

# 2. Verify data/snapshot.json — no accountId, no dollar fields (only date + return_pct + percent).

# 3. Enable GitHub Pages: Settings → Pages → Source: master, /public directory.

# 4. Point DNS: CNAME danomix.com → <user>.github.io
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
