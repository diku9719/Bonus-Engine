"""Turn the engine's output + the Studio ledger export into the JSON files the lead site reads.

usage: python build_site.py <ledger export .csv>
Run bonus_engine.py on the same export first. Writes site/data/*.json (git-ignored: it holds payouts)."""
import json, os, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("BONUS_OUT", os.path.join(HERE, "out"))
DATA = os.path.join(HERE, "site", "data"); os.makedirs(DATA, exist_ok=True)
CFG = json.load(open(os.environ.get("BONUS_CONFIG", os.path.join(HERE, "bonus_config.json"))))
if len(sys.argv) < 2: sys.exit("usage: python build_site.py <ledger export .csv>")
short = lambda e: e.split("@")[0] if isinstance(e, str) else None
rd = lambda f: pd.read_csv(os.path.join(OUT, f))

def dump(df, name):
    json.dump(json.loads(df.to_json(orient="records")), open(os.path.join(DATA, f"{name}.json"), "w"))
    print(f"{name}: {len(df)} rows")

w = rd("bonus_writers.csv"); w = w[w.expert]
dump(w.assign(person=w.person.map(short)).rename(columns={"total_usd_before_AHT_gate": "total_usd"})
     [["person","passed","one_shots","streaks","two_shots","throughput_tasks","total_usd"]].sort_values("total_usd", ascending=False), "writers")
r = rd("bonus_reviewers.csv"); r = r[r.expert]
dump(r.assign(person=r.person.map(short), why_not=r.why_not.fillna(""))
     [["person","touches","sent_to_audit","defect_rate","qualifies","why_not","total_usd"]].sort_values(["total_usd","touches"], ascending=False), "reviewers")
s = rd("bonus_superwriters.csv"); s = s[s.expert & ((s.submitted_to_audit > 0) | (s.delivered > 0) | (s.audited_t14 > 0))]
dump(s.assign(person=s.person.map(short)).rename(columns={"total_usd_before_AHT_gate": "total_usd"})
     [["person","submitted_to_audit","delivered","one_shots","defect_rate_t14","defect_ok","total_usd"]].sort_values(["total_usd","delivered"], ascending=False), "superwriters")

order = ["Ready for writing","Drafting","Ready for writing (Superwriter)","Drafting (Superwriter)","Needs Edits","Needs Edits (stage 2)",
         "Needs Edits (Superwriter)","Ready for reviewing","In review","In review (Superreviewer)","Running trajectories",
         "Running trajectories (Superreviewer)","In stage 2 review","Review check","Ready for auditing","In audit","Failed audit",
         "Ready for RFD audit","In RFD audit"]
st = rd("alert_stuck.csv")
p = st.groupby("st").days_in_status.agg(open_tasks="size", median_days="median").reset_index().rename(columns={"st": "stage"})
p["order"] = p.stage.map({k: i for i, k in enumerate(order)}).fillna(99); p["median_days"] = p.median_days.round(1)
dump(p.sort_values("order")[["stage","open_tasks","median_days"]], "pipeline")

rows = []
for _, a in rd("alert_3plus_needs_edits.csv").iterrows():
    rows.append(dict(kind="3+ Needs Edits rounds", task=a.task_name, person=short(a.credited), detail=f"{a.rounds} rounds, now {a.current}"))
for _, a in rd("alert_claimed_idle.csv").iterrows():
    rows.append(dict(kind="Claimed and idle", task=a.task_name, person=short(a.owner), detail=f"{a.idle_days} days in {a.st}"))
for _, a in rd("alert_new_work_with_open_edits.csv").iterrows():
    rows.append(dict(kind="New work with edits open", task=a.claimed_task, person=short(a.person), detail=f"{a.open_needs_edits} task(s) waiting in Needs Edits"))
for _, a in rd("alert_self_routed_to_sw.csv").iterrows():
    rows.append(dict(kind="Self-routed past review", task=a.task_name, person=short(a.person), detail=f"reclaimed as superwriter after {a.minutes} min"))
dump(pd.DataFrame(rows, columns=["kind","task","person","detail"]), "alerts")

smap = {x["status_id"]: x["canonical"] for x in json.load(open(os.path.join(HERE, "enki_status_map.json")))}
L = pd.read_csv(sys.argv[1]); L["status"] = L.status_id.map(smap); L = L[L.status != "EXCLUDE"]
L["owner_s"] = [short(o) if isinstance(o, str) else (None if pd.isna(i) else i) for o, i in zip(L.owner, L.owner_id)]
L["moved_by"] = [short(o) if isinstance(o, str) else i for o, i in zip(L.entered_by, L.entered_by_id)]
dump(L[["task_id","task_name","seq","status","entered_at","exited_at","owner_s","moved_by","hours_in_status"]]
     .rename(columns={"owner_s": "owner", "hours_in_status": "hours"}), "ledger")

json.dump({"week": CFG["week_label"], "data_through": str(pd.to_datetime(L.entered_at, utc=True, format="ISO8601").max())[:16] + " UTC"},
          open(os.path.join(DATA, "meta.json"), "w"))
print("site data written to", DATA)
