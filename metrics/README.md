# Enki metrics tracker

Weekly Project Enki 2 (WS) bonus table, pipeline, ownership history and lead alerts, computed live from RL Studio.
The site is deployed by Vercel from this folder (GitHub-connected). No contractor data is ever committed:
the page pulls it from Studio when someone opens it or presses **Refresh from Studio**.

## How it works

1. A signed-in lead opens the site (`middleware.js` asks for a username and password first).
2. The page calls `POST /api/refresh` (`api/refresh.py`, Vercel Python function).
3. That function runs `engine/enki_ledger_api.sql` against Studio's querier
   (`POST https://api.studio.mercor.com/querier/unstructured`) with the key from Vercel's settings,
   then runs `engine/bonus_engine.py` and `engine/build_site.py` on the result and returns fresh tables.
4. The page draws them. A refresh within 60 s of the last one reuses that result to spare Studio.

The key never reaches the browser, and the SQL is fixed on the server.

## Files

| File | What it is |
| --- | --- |
| `public/index.html` | The dashboard: Bonuses, Pipeline, Ownership, Alerts, and the Refresh button |
| `middleware.js` | Login in front of every page and the API |
| `api/refresh.py` | Live pull from Studio + recompute |
| `vercel.json`, `requirements.txt` | Vercel setup: serve `public/`; the Python function bundles only `engine/` plus pandas (Vercel's limit is 225 MB) |
| `engine/bonus_config.json` | The week's bonus rules: window, rates, tiers, gates, mid-week rate changes. Edit when a new structure is posted |
| `engine/bonus_engine.py` | Bonus and alert logic |
| `engine/build_site.py` | Turns the engine's output into the page's data |
| `engine/enki_status_map.json` / `.csv`, `engine/enki_flow_transitions.csv` | Every Studio status id (retired ones mapped to current names) and the workflow's actions |
| `engine/enki_ledger_api.sql` | The query the Refresh button runs |
| `sql/enki_ledger.sql` | The same query for pasting into Studio's Query tab by hand |
| `engine/merge_delta.py` | Adds newer Studio changes onto an earlier export (manual fallback) |

## Vercel project settings (one time)

- **Root Directory:** `metrics` (the folder this README is in). Framework preset: Other.
- **Environment Variables (Production):**

| Variable | What |
| --- | --- |
| `DASH_USERS` | Logins: `user:password` pairs separated by commas, e.g. `zayn:LongPassw0rd,manav:Another-0ne`. If missing, nobody gets in. |
| `STUDIO_API_KEY` | The RL Studio key (`rls-sk-...`). |
| `STUDIO_CAMPAIGN_ID`, `STUDIO_COMPANY_ID` | Optional. Default to Project Enki 2 (WS) (`camp_0d3de...`, `comp_2fa41...`). Studio requires both as headers. |
| `STUDIO_USER_AGENT` | Optional. Defaults to `enki-metrics-dashboard/1.0`. Studio's Cloudflare blocks Python's default signature (error 1010). |
| `STUDIO_AUTH` | Optional. `x-api-key` if Studio wants the key in that header instead of `Authorization: Bearer`. |

Changing a variable needs a redeploy (Deployments → ⋯ → Redeploy).

## Weekly upkeep

When a new bonus structure is posted, edit `engine/bonus_config.json` (window, amounts, `writer_rate_changes` for a
mid-week change), commit and push. Vercel redeploys; the next refresh uses the new rules.

## Check after each deploy

- A private window must ask for a login on the site, on `/api/refresh` and on any file.
- Signed in, the page loads live data within about 10–20 s and the line under the button reads
  "Live from Studio: data through …". An error there names the cause, e.g. `Studio answered 401`.

## Run locally (optional)

```
pip install pandas
python engine/bonus_engine.py <ledger export.csv>   # results in engine/out/
python engine/build_site.py <ledger export.csv>     # page data in public/data/
python -m http.server -d public 8000            # preview the snapshot at http://localhost:8000
```
`engine/out/`, any `data/` and `public/data/` are git-ignored.

## Defaults the engine applies where the rules are silent

- Tiers pay the highest level reached, never the sum.
- Streaks are separate pairs of consecutive one-shots.
- Writer tasks are paid at the rates in force when first submitted for review; a streak pays at the rates of the task completing it.
- Superwriter-lane tasks credit whoever submitted to audit; writer-lane tasks credit whoever first submitted for review.
- Re-run loops (In stage 2 review → Running trajectories) and releases back to the pool are not review touches.
- Audit fails are charged to whoever sent the task to audit.
- Staff (`@mercor.com`) accounts are shown but not paid.

## Not yet covered

AHT gates (need hours from the payouts mart) and role eligibility (need the roster). Totals are "before AHT gate".
