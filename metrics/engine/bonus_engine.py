"""Enki bonus engine: ledger (task_history status intervals) + status map -> per-person bonus metrics.
Rules: Sara's 10-26 announcements + Zayn's 10-29 answers; defaults documented inline."""
import json, sys
import pandas as pd

import os
CFG = json.load(open(os.environ.get("BONUS_CONFIG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "bonus_config.json"))))
WIN_START = pd.Timestamp(CFG["window"]["start_utc"])
WIN_END   = pd.Timestamp(CFG["window"]["end_utc"])
WCFG, RCFG, SCFG, STG, RULES = CFG["writer"], CFG["reviewer"], CFG["superwriter"], CFG["stages"], CFG["rules"]

HERE = os.path.dirname(os.path.abspath(__file__))
smap = {r["status_id"]: r for r in json.load(open(os.path.join(HERE, "enki_status_map.json")))}
if len(sys.argv) < 2: sys.exit("usage: python bonus_engine.py <ledger export .csv>")
L = pd.read_csv(sys.argv[1])
for c in ("entered_at", "exited_at"):
    L[c] = pd.to_datetime(L[c], utc=True, format="ISO8601")
canon = lambda s: smap.get(s, {}).get("canonical", "UNKNOWN") if isinstance(s, str) else None
L["st"] = L.status_id.map(canon); L["nx"] = L.next_status_id.map(canon); L["pv"] = L.prev_status_id.map(canon)
unknown = sorted(set(L.loc[L.st == "UNKNOWN", "status_id"]))
L = L[L.st != "EXCLUDE"]
who = lambda email, uid: email if isinstance(email, str) else uid
L["entered_who"] = [who(a, b) for a, b in zip(L.entered_by, L.entered_by_id)]
L["exited_who"] = [who(a, b) for a, b in zip(L.exited_by, L.exited_by_id)]
DATA_THROUGH = L.entered_at.max()

PASSED = set(STG["passed_review_band"])
W_SB = set(STG["writer_sendback"])
SW_LANE = set(STG["superwriter_lane"])
REVIEW = set(STG["review"])
NOT_A_VERDICT = {"Ready for reviewing", None}           # release back to pool, or still open
AUDIT_WORK = {"In audit": {"Passed audit","Failed audit"}, "In RFD audit": {"RFD audit pass","RFD audit fail"}}
FAIL = set(STG["audit_fail"])
inwin = lambda ts: pd.notna(ts) and WIN_START <= ts < WIN_END

tasks = []; touches = []; audits = []
for tid, g in L.sort_values(["task_id","seq"]).groupby("task_id", sort=False):
    g = g.reset_index(drop=True)
    name = g.task_name.iloc[0]
    # --- superwriter lane: submitter of Drafting (Superwriter)/Needs Edits (SW) -> Ready for auditing
    sw_sub = g[(g.st.isin({"Drafting (Superwriter)","Needs Edits (Superwriter)"})) & (g.nx == "Ready for auditing")]
    sw = sw_sub.exited_who.iloc[-1] if len(sw_sub) else None
    # --- regular writer: who submitted Drafting -> Ready for reviewing (first submission)
    w_sub = g[(g.st == "Drafting") & (g.nx == "Ready for reviewing")]
    writer = w_sub.exited_who.iloc[0] if len(w_sub) else None
    first_sub = w_sub.exited_at.iloc[0] if len(w_sub) else pd.NaT
    # --- first entry into the passed-review band
    band = g[g.st.isin(PASSED)]
    pass_at = band.entered_at.iloc[0] if len(band) else pd.NaT
    pre = g[g.entered_at < pass_at] if pd.notna(pass_at) else g
    sendbacks = int(pre.st.isin(W_SB).sum())
    sw_sendbacks = int(g.st.isin(set(STG["superwriter_sendback"])).sum())
    used_sw = bool(g.st.isin(SW_LANE).any())
    outcomes = g[g.st.isin(AUDIT_WORK) & g.nx.notna()]
    outcomes = outcomes[[nx in AUDIT_WORK[st] for st, nx in zip(outcomes.st, outcomes.nx)]]
    last_outcome_fail = bool(len(outcomes)) and outcomes.nx.iloc[-1] in FAIL
    rfd = g[g.st == "Ready for delivery"]
    rfd_at = rfd.entered_at.iloc[0] if len(rfd) else pd.NaT
    sw_first_sub = sw_sub.exited_at.iloc[0] if len(sw_sub) else pd.NaT
    credit = sw if used_sw and sw else writer               # Zayn #12: superwriter gets the credit
    tasks.append(dict(task_id=tid, task_name=name, writer=writer, superwriter=sw, credited=credit,
        lane="superwriter" if (used_sw and sw) else "writer", first_submit=first_sub, sw_first_submit=sw_first_sub,
        passed_review_at=pass_at, rfd_at=rfd_at, writer_sendbacks=sendbacks, sw_sendbacks=sw_sendbacks,
        last_audit_failed=last_outcome_fail, current=g.st.iloc[-1]))
    # --- review touches: exit from a review stage to a verdict, credited to the actor who exited
    for _, r in g[g.st.isin(REVIEW)].iterrows():
        rerun = RULES["rerun_loop_is_not_a_touch"] and r.st == "In stage 2 review" and r.nx in {"Running trajectories","Running trajectories (Superreviewer)"}
        if r.nx not in NOT_A_VERDICT and not rerun:      # stage-2 -> re-run trajectories is a loop, not a review
            touches.append(dict(task_id=tid, reviewer=r.exited_who, stage=r.st, verdict=r.nx, at=r.exited_at))
    # --- audit outcomes: find the Ready-for-auditing entry that fed this audit, and who sent it there.
    #     SW-lane submission (Drafting/Needs Edits (Superwriter) -> RFA) => superwriter's audit, no reviewer blamed.
    #     Otherwise => most recent reviewer verdict before that RFA entry.
    rv = g[g.st.isin(REVIEW) & ~g.nx.isin(NOT_A_VERDICT)]
    rfa = g[g.st == "Ready for auditing"]
    def source(at):
        prev_rfa = rfa[rfa.entered_at <= at]
        if not len(prev_rfa): return ("unknown", None, None)
        e = prev_rfa.iloc[-1]
        if e.pv in {"Drafting (Superwriter)","Needs Edits (Superwriter)"}:
            return ("superwriter", None, e.entered_who)
        prior = rv[rv.exited_at <= e.entered_at]
        return ("reviewer", prior.exited_who.iloc[-1] if len(prior) else None, None)
    for _, a in outcomes.iterrows():
        lane, rev, swr = source(a.entered_at)
        audits.append(dict(task_id=tid, reviewer=rev, superwriter=swr, lane=lane,
            failed=a.nx in FAIL, at=a.exited_at, kind=a.st))
    # --- sent to audit (reviewer baseline): RFA entries not from the SW lane, credited to most recent reviewer
    for _, e in rfa.iterrows():
        if e.pv in {"Drafting (Superwriter)","Needs Edits (Superwriter)"}: continue
        prior = rv[rv.exited_at <= e.entered_at]
        if len(prior): audits.append(dict(task_id=tid, reviewer=prior.exited_who.iloc[-1], sent_to_audit_at=e.entered_at, kind="sent"))

T = pd.DataFrame(tasks); TO = pd.DataFrame(touches); A = pd.DataFrame(audits)
AO = A[A.kind != "sent"].copy(); AS = A[A.kind == "sent"].copy()

def tier(n, table, key):
    best = 0                                  # highest tier reached, never the sum
    for t in sorted(table, key=lambda t: t[key]):
        if n >= t[key]: best = t["usd"]
    return best

def count_streaks(seq):
    streaks = 0; i = 0
    while i < len(seq) - 1:
        if seq[i] and seq[i+1]:
            streaks += 1; i += 2 if RULES["streaks_as_separate_pairs"] else 1
        else: i += 1
    return streaks

def rate_bonus(rate, tiers):
    if rate is None: return 0
    best = 0
    for t in sorted(tiers, key=lambda t: -t["max_rate"]):
        if rate <= t["max_rate"]: best = t["usd"]
    return best

# ---------------- WRITERS ----------------
# Rates can change mid-week (writer_rate_changes). Each task is paid at the rates in force when its writer
# FIRST SUBMITTED it for review; a streak pair is paid at the rates of the task that completes the pair.
_changes = sorted(CFG.get("writer_rate_changes", []), key=lambda c: c["effective_from_utc"])
def writer_rates(first_submit):
    r = dict(WCFG)
    for c in _changes:
        if pd.notna(first_submit) and pd.Timestamp(first_submit) >= pd.Timestamp(c["effective_from_utc"]):
            r.update({k: v for k, v in c.items() if not k.startswith("_") and k != "effective_from_utc"})
    return r

def streak_pairs(seq):
    pairs = []; i = 0
    while i < len(seq) - 1:
        if seq[i] and seq[i+1]:
            pairs.append(i + 1); i += 2 if RULES["streaks_as_separate_pairs"] else 1
        else: i += 1
    return pairs                                   # index of the task completing each pair

W = T[(T.lane == "writer") & T.credited.notna() & T.passed_review_at.apply(inwin)].copy()
W["one_shot"] = W.writer_sendbacks.eq(0); W["two_shot"] = W.writer_sendbacks.eq(1); W["three_shot"] = W.writer_sendbacks.eq(2)
W["counts_throughput"] = ~W.last_audit_failed
if not RULES["two_shot_pays_even_if_audit_later_fails"]:
    W.loc[W.last_audit_failed, ["two_shot","three_shot"]] = False
rates = [writer_rates(fs) for fs in W.first_submit]
W["structure"] = [r.get("structure_name", "base") for r in rates]
W["task_usd"] = [r["one_shot_usd"] if o else r["two_shot_usd"] if t2 else r.get("three_shot_usd", 0) if t3 else 0
                 for r, o, t2, t3 in zip(rates, W.one_shot, W.two_shot, W.three_shot)]
W["streak_usd"] = 0
W = W.sort_values(["credited", "passed_review_at"])
for p, g in W.groupby("credited"):
    for j in streak_pairs(list(g.one_shot)):
        idx = g.index[j]; W.loc[idx, "streak_usd"] = writer_rates(W.loc[idx, "first_submit"])["streak_usd"]
rows = []
for p, g in W.groupby("credited"):
    tp = int(g.counts_throughput.sum())
    sh = lambda col: int(g[col].sum())
    pay = lambda mask: int((g.task_usd[mask]).sum() + (g.streak_usd[mask]).sum())
    base_name = WCFG.get("structure_name", "base")
    rows.append(dict(person=p, passed=len(g), one_shots=sh("one_shot"), streaks=int((g.streak_usd > 0).sum()),
        two_shots=sh("two_shot"), three_shots=sh("three_shot"), throughput_tasks=tp,
        one_shot_usd=int(g.task_usd[g.one_shot].sum()), streak_usd=int(g.streak_usd.sum()),
        two_shot_usd=int(g.task_usd[g.two_shot].sum()), three_shot_usd=int(g.task_usd[g.three_shot].sum()),
        throughput_usd=tier(tp, WCFG["throughput_tiers"], "min_tasks"),
        usd_base_rules=pay(g.structure == base_name), usd_new_rules=pay(g.structure != base_name),
        tasks=", ".join(g.task_name.astype(str))))
WR = pd.DataFrame(rows)
if len(WR): WR["total_usd_before_AHT_gate"] = WR[["one_shot_usd","streak_usd","two_shot_usd","three_shot_usd","throughput_usd"]].sum(axis=1)
WTASKS = W[["task_id","task_name","credited","first_submit","passed_review_at","writer_sendbacks","structure","task_usd","streak_usd","counts_throughput"]]

# ---------------- REVIEWERS ----------------
TOw = TO[TO["at"].apply(inwin)]
touch_n = TOw.groupby("reviewer").size()
sent_n = AS[AS.sent_to_audit_at.apply(inwin)].drop_duplicates(["task_id","reviewer"]).groupby("reviewer").size()
AOr = AO[AO.reviewer.notna()]
dr = AOr.groupby("reviewer").agg(audited=("failed","size"), failed=("failed","sum"))
dr["defect_rate"] = dr.failed / dr.audited
people = sorted(set(touch_n.index) | set(sent_n.index))
rows = []
for p in people:
    t = int(touch_n.get(p, 0)); s = int(sent_n.get(p, 0))
    a = int(dr.audited.get(p, 0)); f = int(dr.failed.get(p, 0)); rate = f / a if a else None
    qualifies = s >= RCFG["gate"]["min_sent_to_audit_in_window"] and rate is not None and rate <= RCFG["gate"]["all_time_defect_rate_max"]
    rows.append(dict(person=p, touches=t, sent_to_audit=s, audited_all_time=a, failed_all_time=f,
        defect_rate=None if rate is None else round(rate, 3), qualifies=qualifies,
        touch_usd=tier(t, RCFG["touch_tiers"], "min_touches") if qualifies else 0,
        defect_usd=rate_bonus(rate, RCFG["defect_rate_tiers"]) if qualifies else 0,
        why_not="" if qualifies else (f"<{RCFG['gate']['min_sent_to_audit_in_window']} sent to audit" if s < RCFG["gate"]["min_sent_to_audit_in_window"] else "no audited tasks yet" if rate is None else f"defect rate >{RCFG['gate']['all_time_defect_rate_max']:.0%}")))
RV = pd.DataFrame(rows)
if len(RV): RV["total_usd"] = RV.touch_usd + RV.defect_usd

# ---------------- SUPERWRITERS ----------------
S = T[T.lane == "superwriter"].copy()
AO["at"] = pd.to_datetime(AO["at"], utc=True)
T14_START = min(DATA_THROUGH, WIN_END) - pd.Timedelta(days=SCFG["gate"]["defect_rate_window_days"])
swa = AO[(AO.lane == "superwriter") & AO.superwriter.notna()]
sw_out = swa.groupby("superwriter").agg(audited=("failed","size"), failed=("failed","sum"))
sw_t14 = swa[swa["at"] >= T14_START].groupby("superwriter").agg(audited=("failed","size"), failed=("failed","sum"))
rows = []
for p, g in S.groupby("superwriter"):
    sub = g[g.sw_first_submit.apply(inwin)]
    done = g[g.rfd_at.apply(inwin)].sort_values("rfd_at")
    streaks = count_streaks(list(done.sw_sendbacks.eq(0)))
    one = int(done.sw_sendbacks.eq(0).sum())
    a = int(sw_out.audited.get(p, 0)); f = int(sw_out.failed.get(p, 0)); rate = f / a if a else None
    a14 = int(sw_t14.audited.get(p, 0)); f14 = int(sw_t14.failed.get(p, 0)); r14 = f14 / a14 if a14 else None
    rows.append(dict(person=p, submitted_to_audit=len(sub), delivered=len(done), one_shots=one, streaks=streaks,
        audited_t14=a14, failed_t14=f14, defect_rate_t14=None if r14 is None else round(r14, 3),
        audited_all_time=a, failed_all_time=f, defect_rate_all_time=None if rate is None else round(rate, 3),
        defect_ok=(r14 is None or r14 < SCFG["gate"]["defect_rate_below"]), one_shot_usd=SCFG["one_shot_usd"]*one, streak_usd=SCFG["streak_usd"]*streaks,
        throughput_usd=tier(len(sub), SCFG["throughput_tiers"], "min_tasks")))
SWR = pd.DataFrame(rows)
if len(SWR): SWR["total_usd_before_AHT_gate"] = (SWR.one_shot_usd + SWR.streak_usd + SWR.throughput_usd).where(SWR.defect_ok, 0)

# ---------------- OPS ALERTS ----------------
cur = L.sort_values("seq").groupby("task_id").tail(1)
ne_rounds = L[L.st.isin(W_SB)].groupby("task_id").size()
alerts_3rd = T.assign(rounds=T.task_id.map(ne_rounds).fillna(0).astype(int)).pipe(lambda d: d[(d.rounds >= RULES["alert_needs_edits_rounds"]) & ~d.current.isin(STG["terminal"])])
now = DATA_THROUGH
stuck = cur[~cur.st.isin({"Ready for delivery","Discarded","RFD audit pass","Holdout"})].copy()
stuck["days_in_status"] = ((now - stuck.entered_at).dt.total_seconds() / 86400).round(1)
stuck = stuck.sort_values("days_in_status", ascending=False)[["task_id","task_name","st","owner","days_in_status"]]

# ---------------- MORE ALERTS ----------------
DATA_NOW = DATA_THROUGH
# (a) claimed and idle: task sits in an owned work status, with an owner, longer than alert_idle_days.
#     If the export carries last_edit_at (newer ledger.sql), idle = time since the last edit instead.
curw = cur[cur.st.isin(set(STG["owned_work"])) & cur.owner_id.notna()].copy()
if "last_edit_at" in curw.columns:
    last = pd.to_datetime(curw.last_edit_at, utc=True, format="ISO8601").fillna(curw.entered_at)
else:
    last = curw.entered_at
curw["idle_days"] = ((DATA_NOW - last).dt.total_seconds() / 86400).round(1)
idle = curw[curw.idle_days >= RULES["alert_idle_days"]].sort_values("idle_days", ascending=False)[["task_id","task_name","st","owner","idle_days"]]
# (b) new work while Needs Edits are open: a writer claims a fresh task while another of theirs waits in Needs Edits
ne = L[L.st.isin(W_SB | set(STG["superwriter_sendback"])) & L.owner.notna()][["task_id","owner","entered_at","exited_at"]].copy()
ne["exited_at"] = ne.exited_at.fillna(DATA_NOW + pd.Timedelta(days=1))
claims = L[(L.st.isin({"Drafting","Drafting (Superwriter)"})) & (L.pv.isin({"Ready for writing","Ready for writing (Superwriter)"}))][["task_id","task_name","entered_who","entered_at"]]
rows = []
for _, c in claims.iterrows():
    open_ne = ne[(ne.owner == c.entered_who) & (ne.task_id != c.task_id) & (ne.entered_at <= c.entered_at) & (ne.exited_at > c.entered_at)]
    if len(open_ne):
        rows.append(dict(person=c.entered_who, claimed_task=c.task_name, claimed_at=c.entered_at, open_needs_edits=len(open_ne),
                         waiting_tasks=", ".join(open_ne.task_id.str[5:13])))
NWO = pd.DataFrame(rows)
# (c) off-flow moves: status changes that match no action in the live workflow (admin overrides, retired paths)
flow = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "enki_flow_transitions.csv"))
allowed = set(zip(flow.from_status, flow.to_status))
mv = L[L.pv.notna() & (L.pv != L.st)]   # same->same = Studio status-id migrations, not moves
mv = mv[["task_id","task_name","pv","st","entered_who","entered_at"]]
off = mv[[(a, b) not in allowed for a, b in zip(mv.pv, mv.st)]]
OFF = off.groupby(["pv","st"]).agg(moves=("task_id","size"), people=("entered_who","nunique"), last=("entered_at","max")).reset_index().sort_values("moves", ascending=False)

is_expert = lambda p: isinstance(p, str) and p.endswith(RULES["payout_email_domain"])
for df in (WR, RV, SWR):
    if len(df): df.insert(1, "expert", df.person.map(is_expert))
# self-routing: same person moves own task Drafting -> Ready for writing -> Drafting (Superwriter) (skips review)
selfroute = []
for tid, g in L.sort_values(["task_id","seq"]).groupby("task_id"):
    g = g.reset_index(drop=True)
    for i in range(len(g) - 2):
        a, b, c = g.iloc[i], g.iloc[i+1], g.iloc[i+2]
        if a.st == "Drafting" and b.st == "Ready for writing" and c.st == "Drafting (Superwriter)" and a.exited_who == c.entered_who:
            selfroute.append(dict(task_id=tid, task_name=a.task_name, person=a.exited_who, at=b.entered_at,
                minutes=round((c.entered_at - b.entered_at).total_seconds() / 60, 1)))
SR = pd.DataFrame(selfroute)
out = os.environ.get("BONUS_OUT", os.path.join(HERE, "out")); os.makedirs(out, exist_ok=True)
T.to_csv(f"{out}/tasks_derived.csv", index=False); TO.to_csv(f"{out}/review_touches.csv", index=False); AO.to_csv(f"{out}/audit_outcomes.csv", index=False)
WR.to_csv(f"{out}/bonus_writers.csv", index=False); WTASKS.to_csv(f"{out}/bonus_writer_tasks.csv", index=False); RV.to_csv(f"{out}/bonus_reviewers.csv", index=False); SWR.to_csv(f"{out}/bonus_superwriters.csv", index=False)
alerts_3rd.to_csv(f"{out}/alert_3plus_needs_edits.csv", index=False); stuck.to_csv(f"{out}/alert_stuck.csv", index=False); SR.to_csv(f"{out}/alert_self_routed_to_sw.csv", index=False); idle.to_csv(f"{out}/alert_claimed_idle.csv", index=False); NWO.to_csv(f"{out}/alert_new_work_with_open_edits.csv", index=False); OFF.to_csv(f"{out}/alert_off_flow_moves.csv", index=False)
print("config:", CFG["week_label"], "| data through", DATA_THROUGH, "| unknown statuses:", unknown)
print("tasks", len(T), "| writer-lane passed in window", len(W), "| touches in window", len(TOw), "| audit outcomes all-time", len(AO))
