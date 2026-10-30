# Enki bonus engine

Computes the weekly Enki bonus tables and lead alerts from Studio's status history.

## Weekly run

1. In Studio → Project Enki Main → Tasks → **Query**, paste `sql/enki_ledger.sql`, click **Run** (expect ~5,800 rows), then **Export CSV**.
2. Edit `bonus_config.json` for the week (window in UTC, tiers, amounts). No code change needed.
3. Run:

   ```bash
   pip install pandas
   python scripts/bonus/bonus_engine.py ~/Downloads/query-results-XXXX.csv
   ```

4. Results land in `scripts/bonus/out/` (git-ignored): `bonus_writers.csv`, `bonus_reviewers.csv`, `bonus_superwriters.csv` and `alert_*.csv`.

## Files

| File | What it is |
| --- | --- |
| `bonus_engine.py` | The engine: ledger + status map + config → bonus tables and alerts |
| `bonus_config.json` | Weekly settings: window, gates, tiers, amounts, stage lists, rule switches |
| `enki_status_map.json` / `.csv` | All 48 status ids seen on Enki → current name and bonus role (retired ids included) |
| `enki_flow_transitions.csv` | The 35 actions of the live workflow (flow revision 38) |
| `build_status_map.py` | Regenerates the status map |
| `sql/enki_ledger.sql` | Read-only Studio query: one row per task per status interval |

## When Studio changes the workflow

The engine prints `unknown statuses: [...]`. Add each new id to `build_status_map.py` with its name and canonical stage, re-run it, and add the stage to the right list in `bonus_config.json`.

## Defaults

See the "Bonus rules as implemented" section of the metrics write-up. Data exports and `out/` contain contractor handles and payouts: never commit them.
