"""Rebuild the ownership ledger = old export's status events + new events pulled from Studio (packed rows)."""
import sys, pandas as pd, numpy as np
old = pd.read_csv(sys.argv[1]); out = sys.argv[2]; parts = sys.argv[3:]
cols = ["task_id","entered_at","status_id","entered_by_id","entered_by","owner_id","owner","creator_id","creator","task_name"]
rows = []
for p in parts:
    for ev in open(p, encoding="utf-8").read().strip().split("~"):
        f = ev.split("|")
        if len(f) != 10: sys.exit(f"bad event ({len(f)} fields): {ev[:120]}")
        rows.append(f)
new = pd.DataFrame(rows, columns=cols).replace({"": np.nan})
ev_old = old[cols].copy()
cut = pd.to_datetime(old.entered_at, utc=True, format="ISO8601").max()
new_t = pd.to_datetime(new.entered_at, utc=True, format="ISO8601")
assert (new_t > cut).all(), "new events must be after the old export"
E = pd.concat([ev_old, new], ignore_index=True)
E["_t"] = pd.to_datetime(E.entered_at, utc=True, format="ISO8601")
E = E.drop_duplicates(["task_id", "entered_at"]).sort_values(["task_id", "_t"]).reset_index(drop=True)
# latest name / creator per task
last = E.groupby("task_id").tail(1).set_index("task_id")
E["task_name"] = E.task_id.map(last.task_name.fillna(""))
for c in ("creator", "creator_id"):
    E[c] = E.task_id.map(E.dropna(subset=[c]).groupby("task_id")[c].first())
g = E.groupby("task_id")
E["seq"] = g.cumcount() + 1
E["prev_status_id"] = g.status_id.shift(1); E["next_status_id"] = g.status_id.shift(-1)
E["exited_at"] = g.entered_at.shift(-1); E["exited_by"] = g.entered_by.shift(-1); E["exited_by_id"] = g.entered_by_id.shift(-1)
now = pd.Timestamp.now(tz="UTC")
ex = pd.to_datetime(E.exited_at, utc=True, format="ISO8601").fillna(now)
E["hours_in_status"] = ((ex - E._t).dt.total_seconds() / 3600).round(3)
order = ["task_id","task_name","creator","seq","prev_status_id","status_id","next_status_id","entered_at","exited_at","entered_by","exited_by","owner","hours_in_status","creator_id","entered_by_id","exited_by_id","owner_id"]
E[order].to_csv(out, index=False)
print(f"old events {len(ev_old)} + new {len(new)} = {len(E)} rows, {E.task_id.nunique()} tasks; new tasks {len(set(new.task_id) - set(ev_old.task_id))}; data through {E._t.max()}")
