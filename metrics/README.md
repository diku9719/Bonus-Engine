# Enki metrics tracker

Computes the weekly Project Enki 2 (WS) bonus table and lead alerts from Studio's status history.

## Files

| File | What it is |
| --- | --- |
| `sql/enki_ledger.sql` | Read-only query for Studio's Query tab: one row per task per status (owner, who moved it, hours, last edit). Keep the `LIMIT 10000`: Studio caps results at 100 rows without it. |
| `enki_status_map.json` / `.csv` | All 48 status ids seen on Enki, retired ids mapped to current names, each tagged with its bonus role. |
| `enki_flow_transitions.csv` | The live workflow's 35 actions (from, to, who). Used to flag off-flow moves. |
| `bonus_config.json` | The week's rules: window, gates, tiers, amounts, stage sets, rule switches. Edit this when a new bonus structure is posted. |
| `bonus_engine.py` | Reads the export + map + config; writes bonus tables and alert lists to `out/`. |
| `build_site.py` | Turns `out/` + the export into `site/data/*.json` for the lead site. |
| `site/` | The lead site: `index.html` (Bonuses, Pipeline, Ownership, Alerts). |

## Weekly run

1. In Studio (Project Enki Main → Tasks → Query), paste `sql/enki_ledger.sql`, Run, check the row count, Export CSV.
2. Update `bonus_config.json` (window, amounts) from the week's announcement.
3. `pip install pandas` then `python bonus_engine.py path/to/export.csv`
4. Results land in `out/`: `bonus_writers.csv`, `bonus_reviewers.csv`, `bonus_superwriters.csv`, and `alert_*.csv`.

`BONUS_CONFIG` and `BONUS_OUT` environment variables override the config path and output folder.

## Lead site on Vercel

The site's data holds draft payouts, so it is never committed (`site/data/` is git-ignored). The Vercel CLI also skips git-ignored files, so deploy from a folder outside the repo that `build_site.py` assembles. The site currently has **no login**: anyone with the URL can see the draft payouts, so share the link only with leads.

Every refresh (after the weekly run above):

```
python build_site.py path/to/export.csv --deploy-dir ~/enki-site
cd ~/enki-site
vercel deploy --prod
```

First time only, inside `~/enki-site` before deploying: `vercel link` (pick the existing project, e.g. enki-metrics).

Open the URL in a private window: it should show the tables.

## Defaults the engine applies where the rules are silent

- Tiers pay the highest level reached, never the sum.
- Streaks are separate pairs of consecutive one-shots.
- Superwriter-lane tasks credit whoever submitted to audit; writer-lane tasks credit whoever first submitted for review.
- Re-run loops (In stage 2 review → Running trajectories) and releases back to the pool are not review touches.
- Audit fails are charged to whoever sent the task to audit.
- Staff (`@mercor.com`) accounts are shown but not paid.

## Not yet covered

AHT gates (needs hours from the payouts mart) and role eligibility (needs the roster). Until then, totals are "before AHT gate".
