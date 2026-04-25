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
