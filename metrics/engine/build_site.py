"""Turn the engine's output + the Studio ledger export into the JSON files the lead site reads.

usage: python build_site.py <ledger export .csv>
Run bonus_engine.py on the same export first. Writes ../public/data/*.json (git-ignored: it holds payouts)
for a local preview. On Vercel, api/refresh.py runs this same script on live Studio data
(SITE_DATA points it at a temporary folder), so nothing here needs deploying."""
import glob, json, os, sys
from zoneinfo import ZoneInfo
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("BONUS_OUT", os.path.join(HERE, "out"))
DATA = os.environ.get("SITE_DATA", os.path.join(HERE, "..", "public", "data")); os.makedirs(DATA, exist_ok=True)
CFG = json.load(open(os.environ.get("BONUS_CONFIG") or sorted(glob.glob(os.path.join(HERE, "weeks", "*.json")))[-1]))
if len(sys.argv) < 2: sys.exit("usage: python build_site.py <ledger export .csv>")
RULES = CFG["rules"]
PT = ZoneInfo(RULES.get("day_timezone", "America/Los_Angeles"))
def rd(f):   # an empty week writes header-less files: read them as empty tables
    try: return pd.read_csv(os.path.join(OUT, f))
    except pd.errors.EmptyDataError: return pd.DataFrame()
experts = lambda df: df[df.expert.astype(bool)] if len(df) and "expert" in df else df.iloc[0:0]
def sel(df, cols, sort=None, asc=False):
    if not len(df): return pd.DataFrame(columns=cols)
    df = df[cols]
    return df.sort_values(sort, ascending=asc) if sort else df
RUN = json.load(open(os.path.join(OUT, "run_meta.json")))

# names: "First L" from Studio's users table; the email handle when Studio has no name
short = lambda e: e.split("@")[0] if isinstance(e, str) else None
ppl = rd("people.csv")
NAMES = dict(zip(ppl.email, ppl.name))
name = lambda e: NAMES.get(e) or short(e)

def people(df, col="person"):
    return df.assign(handle=df[col].map(short), **{col: df[col].map(name)})

def dump(df, nm):
    json.dump(json.loads(df.to_json(orient="records")), open(os.path.join(DATA, f"{nm}.json"), "w"))
    print(f"{nm}: {len(df)} rows")

def pt(ts, fmt="%a %b %-d, %-I:%M %p %Z"):
    return pd.Timestamp(ts).tz_convert(PT).strftime(fmt)

usd = lambda v: f"${v:,.0f}"
tiers = lambda t, k, unit: ", ".join(f"{x[k]}{' ' + unit if unit else ''} → {usd(x['usd'])}" for x in sorted(t, key=lambda x: x[k]))

# ---------------- bonus tables ----------------
w = experts(rd("bonus_writers.csv"))
dump(sel(people(w).rename(columns={"total_usd_before_AHT_gate": "total_usd"}) if len(w) else w,
     ["person","handle","submitted_in_window","waiting_review","carried_in","failed_audit","passed","one_shots","streaks","two_shots","three_shots","throughput_tasks",
      "defect_rate_t14","usd_base_rules","usd_new_rules","total_usd"], ["total_usd","submitted_in_window"]), "writers")
r = experts(rd("bonus_reviewers.csv"))
dump(sel(people(r).assign(why_not=r.why_not.fillna("")) if len(r) else r,
     ["person","handle","touches","sent_to_audit","waiting_audit","defect_rate","defect_rate_t14","qualifies","why_not","total_usd"], ["total_usd","touches"]), "reviewers")
s = experts(rd("bonus_superwriters.csv"))
if len(s): s = s[(s.submitted_to_audit > 0) | (s.delivered > 0) | (s.audited_t14 > 0) | (s.waiting > 0)]
dump(sel(people(s).rename(columns={"total_usd_before_AHT_gate": "total_usd"}) if len(s) else s,
     ["person","handle","submitted_to_audit","waiting","delivered","one_shots","defect_rate_t14","defect_ok","total_usd"], ["total_usd","delivered"]), "superwriters")
a = experts(rd("bonus_auditors.csv"))
ACFG = CFG.get("auditor", {"daily_tiers": []})
day_cols = [f"days_{t['min_audits']}_plus" for t in sorted(ACFG["daily_tiers"], key=lambda t: t["min_audits"])]
dump(people(a)[["person","handle","audits","failed","active_days","best_day","by_day","total_usd"] + day_cols].sort_values(["total_usd","audits"], ascending=False)
     if len(a) else pd.DataFrame(), "auditors")

wt = experts(rd("waiting.csv"))
dump(people(wt).assign(submitted_pt=[pt(x, "%b %-d %-I:%M %p") for x in wt.submitted_at])
     [["role","person","handle","task_name","submitted_pt","now","waiting_for","days_waiting"]].sort_values(["role","person","days_waiting"])
     if len(wt) else pd.DataFrame(), "waiting")
ci = experts(rd("carried_in.csv"))

# ---------------- pipeline + alerts ----------------
order = ["Ready for writing","Drafting","Ready for writing (Superwriter)","Drafting (Superwriter)","Needs Edits","Needs Edits (stage 2)",
         "Needs Edits (Superwriter)","Ready for reviewing","In review","In review (Superreviewer)","Running trajectories",
         "Running trajectories (Superreviewer)","In stage 2 review","Review check","Ready for auditing","In audit","Failed audit",
         "Ready for RFD audit","In RFD audit"]
st = rd("alert_stuck.csv")
p = st.groupby("st").days_in_status.agg(open_tasks="size", median_days="median").reset_index().rename(columns={"st": "stage"})
p["order"] = p.stage.map({k: i for i, k in enumerate(order)}).fillna(99); p["median_days"] = p.median_days.round(1)
dump(p.sort_values("order")[["stage","open_tasks","median_days"]], "pipeline")

rows = []
for _, x in rd("alert_3plus_needs_edits.csv").iterrows():
    rows.append(dict(kind="3+ Needs Edits rounds", task=x.task_name, person=name(x.credited), detail=f"{x.rounds} rounds, now {x.current}"))
for _, x in rd("alert_claimed_idle.csv").iterrows():
    rows.append(dict(kind="Claimed and idle", task=x.task_name, person=name(x.owner), detail=f"{x.idle_days} days in {x.st}"))
for _, x in rd("alert_new_work_with_open_edits.csv").iterrows():
    rows.append(dict(kind="New work with edits open", task=x.claimed_task, person=name(x.person), detail=f"{x.open_needs_edits} task(s) waiting in Needs Edits"))
for _, x in rd("alert_self_routed_to_sw.csv").iterrows():
    rows.append(dict(kind="Self-routed past review", task=x.task_name, person=name(x.person), detail=f"reclaimed as superwriter after {x.minutes} min"))
for _, x in ci.iterrows():
    rows.append(dict(kind="Passed this week, submitted earlier", task=x.task_name, person=name(x.credited),
                     detail=f"submitted {pt(x.first_submit, '%b %-d')}, passed review {pt(x.passed_review_at, '%b %-d')}: "
                            + ("included in this week's bonus" if bool(x.get("paid", False)) else "counted in the week it was submitted")))
dump(pd.DataFrame(rows, columns=["kind","task","person","detail"]), "alerts")

# ---------------- ownership ledger ----------------
smap = {x["status_id"]: x["canonical"] for x in json.load(open(os.path.join(HERE, "enki_status_map.json")))}
L = pd.read_csv(sys.argv[1]); L["status"] = L.status_id.map(smap); L = L[L.status != "EXCLUDE"]
L["owner_s"] = [name(o) if isinstance(o, str) else (None if pd.isna(i) else i) for o, i in zip(L.owner, L.owner_id)]
L["moved_by"] = [name(o) if isinstance(o, str) else i for o, i in zip(L.entered_by, L.entered_by_id)]
dump(L[["task_id","task_name","seq","status","entered_at","exited_at","owner_s","moved_by","hours_in_status"]]
     .rename(columns={"owner_s": "owner", "hours_in_status": "hours"}), "ledger")

# ---------------- meta: week, snapshot, and the rule text shown above each table ----------------
WC, SC, RC = CFG["writer"], CFG.get("superwriter", {}), CFG["reviewer"]
SW_ON = SC.get("enabled", True)
ch = sorted(CFG.get("writer_rate_changes", []), key=lambda c: c["effective_from_utc"])
def wrates(r):
    parts = []
    if r.get("per_task_usd"): parts.append(f"{usd(r['per_task_usd'])} per task")
    if r.get("one_shot_usd"): parts.append(f"+{usd(r['one_shot_usd'])} one-shot boost" if r.get("per_task_usd") else f"one-shot {usd(r['one_shot_usd'])}")
    if r.get("streak_usd"): parts.append(f"streak +{usd(r['streak_usd'])}")
    if r.get("two_shot_usd"): parts.append(f"two-shot {usd(r['two_shot_usd'])}")
    if r.get("three_shot_usd"): parts.append(f"three-shot {usd(r['three_shot_usd'])}")
    return ", ".join(parts)
w_note = wrates(WC) + "."
for c in ch:
    w_note = f"Submitted before {pt(c['effective_from_utc'])}: {wrates(WC)}. From then ({c['structure_name']}): {wrates({**WC, **c})}."
w_note += f" Throughput: {tiers(WC['throughput_tiers'], 'min_tasks', 'tasks')} (highest tier only)."
by = RUN["count_tasks_by"]
resolve = "passes audit (it is held under Waiting while in review or audit)" if WC.get("pay_after") == "audit" else "passes review"
count_note = (f"A task counts for the week it was first submitted in and is paid once it {resolve}, even if that happens after the window."
              if by == "first_submit" else "A task counts for the week it passed review in.")
if WC.get("no_audit_fail"): count_note += " A task that fails an audit is not paid."
if RULES.get("include_carried_in"):
    count_note += f" Included: {len(ci[ci.paid]) if len(ci) and 'paid' in ci else 0} tasks that passed review this week but were submitted before {pt(RULES['carry_in_submitted_before_utc'], '%b %-d')} (column Carried in)."
aht_h = (WC.get("gate") or {}).get("all_time_aht_max_hours")
aht_note = f"AHT gate (under {aht_h} h) not applied: Studio has no hours data." if aht_h else ""
sg = SC.get("gate", {})
s_note = ((f"One-shot {usd(SC['one_shot_usd'])}, +{usd(SC['streak_usd'])} per streak pair, throughput {tiers(SC['throughput_tiers'], 'min_tasks', 'submitted')}. "
          f"Pays only if the 14-day audit defect rate at the snapshot is under {sg['defect_rate_below']:.0%}. AHT gate (under {sg['all_time_aht_max_hours']} h) not applied: no hours data.")
          if SW_ON else "No superwriter bonus this week. Activity is shown for reference only.")
rg = dict(RC["gate"]); rg.setdefault("defect_rate_max", rg.get("all_time_defect_rate_max", 0.3))
rwin = "14-day" if RC.get("defect_rate_window") == "t14" else "all-time"
r_note = (f"Gate: {rg['min_sent_to_audit_in_window']}+ reviewed task(s) sent to audit this week and {rwin} defect rate {rg['defect_rate_max']:.0%} or less (as of the snapshot). "
          f"Touches {tiers(RC['touch_tiers'], 'min_touches', 'touches')}; {rwin} defect " + ", ".join(f"{t['max_rate']:.0%} or less → {usd(t['usd'])}" for t in sorted(RC['defect_rate_tiers'], key=lambda t: -t['max_rate'])) + ".")
a_tiers = sorted(ACFG["daily_tiers"], key=lambda t: t["min_audits"])
a_note = f"Audits finished per Pacific-time day ({', '.join(ACFG.get('audit_stages', []))}). "
if not a_tiers: a_note += "No auditor bonus this week; counts shown for reference."
elif any(t["usd"] for t in a_tiers): a_note += "Daily: " + ", ".join(f"{t['min_audits']}+ audits → {usd(t['usd'])}" for t in a_tiers) + " (highest tier per day)."
else: a_note += "Thresholds " + " and ".join(str(t["min_audits"]) for t in a_tiers) + " audits a day (highest tier per day); dollar amounts not announced yet."
snap = RUN["snapshot_utc"]
json.dump({
    "week": CFG["week_label"],
    "window_pt": f"{pt(CFG['window']['start_utc'])} – {pt(CFG['window']['end_utc'])}",
    "snapshot_pt": pt(snap), "snapshot_passed": pd.Timestamp(RUN["snapshot_effective_utc"]) >= pd.Timestamp(snap),
    "t14_from_pt": pt(RUN["t14_start_utc"]), "count_tasks_by": by,
    "data_through": str(pd.Timestamp(RUN["data_through"]))[:16] + " UTC", "data_through_pt": pt(RUN["data_through"]),
    "base_label": WC.get("structure_name", "Base rates") if ch else "Earned", "new_label": ch[-1]["structure_name"] if ch else None,
    "writer_change": (ch[-1]["structure_name"] + " from " + pt(ch[-1]["effective_from_utc"])) if ch else None,
    "carried_in": int(len(ci)), "auditor_tiers": a_tiers,
    "writer_cols": (["submitted_in_window", "waiting_review"] + (["carried_in"] if RULES.get("include_carried_in") else [])
                    + (["failed_audit"] if WC.get("no_audit_fail") else []) + ["passed", "one_shots"]
                    + (["streaks"] if WC.get("streak_usd") or any(c.get("streak_usd") for c in ch) else [])
                    + (["two_shots"] if WC.get("two_shot_usd") or any(c.get("two_shot_usd") for c in ch) else [])
                    + (["three_shots"] if WC.get("three_shot_usd") or any(c.get("three_shot_usd") for c in ch) else [])
                    + ["throughput_tasks", "defect_rate_t14"] + (["usd_base_rules", "usd_new_rules"] if ch else []) + ["total_usd"]),
    "week_id": CFG.get("week_id"), "superwriter_bonus": SW_ON, "reviewer_window": rwin,
    "notes": {"writers": f"{count_note} {w_note} {aht_note}".strip(), "superwriters": s_note, "reviewers": r_note, "auditors": a_note},
}, open(os.path.join(DATA, "meta.json"), "w"))
print("site data written to", DATA)
