import csv, json
# id, name, category, active, rows, first, last, canonical, note
S = [
("f7a69922e72549879d3b9561a02b0cb2","Drafting","writing",1,4170,"2026-08-28","2026-10-29","Drafting",""),
("3d30884cb4284ad9b622c1702ae9f134","Needs Edits","writing",1,2161,"2026-08-28","2026-10-29","Needs Edits",""),
("18af2eb2be254a1f957157523b115528","Running trajectories","holding_tank",1,1881,"2026-09-05","2026-10-28","Running trajectories",""),
("798b0cf0d4274f29988cd9b0ef9024b7","In second pass","reviewing",0,876,"2026-09-02","2026-10-12","In stage 2 review","retired; renamed In stage 2 review on 10-12"),
("a155a35ad5cc4f70856b89922bad2723","Drafting (Superwriter)","writing",1,851,"2026-09-27","2026-10-29","Drafting (Superwriter)",""),
("bd091b43578a4f0483db8c219c150e7c","In review","reviewing",1,734,"2026-08-28","2026-10-29","In review",""),
("7a1b781ccd3b4c35b573d14738a182c4","Running trajectories (Superreviewer)","holding_tank",1,521,"2026-10-05","2026-10-29","Running trajectories (Superreviewer)",""),
("bcc78f26cd4e442ea14da4f620747142","In audit","auditing",1,466,"2026-09-27","2026-10-29","In audit",""),
("66a87eed88fb42d5a42083ce48b1accd","Ready for reviewing","reviewing",1,463,"2026-08-28","2026-10-29","Ready for reviewing",""),
("e710dbb97fbb49b28b405763f53de0dc","Ready for delivery","ready_for_delivery",1,401,"2026-09-01","2026-10-29","Ready for delivery",""),
("bf8de55e73b84efcb1ab0f7e2d895e69","Ready for auditing","auditing",1,287,"2026-09-27","2026-10-29","Ready for auditing",""),
("90acaedbddfd4e0aa58627b165c6e511","In stage 2 review","reviewing",1,273,"2026-10-12","2026-10-29","In stage 2 review",""),
("857d738f9f084803ab3098fbad280fad","Review check","holding_tank",1,263,"2026-09-02","2026-10-29","Review check",""),
("d10df246e931415ca7494af5d6096375","Needs Edits (Superwriter)","writing",1,221,"2026-09-29","2026-10-27","Needs Edits (Superwriter)",""),
("16b5fbddd62c4e68928f6c8400b1698e","In review (Superreviewer)","reviewing",1,202,"2026-09-24","2026-10-29","In review (Superreviewer)",""),
("9cfae4f2058d41fcb8f4a19fe70f683b","Passed audit","auditing",1,200,"2026-09-27","2026-10-29","Passed audit",""),
("9bba3533f0e1437689bcc07e772f3166","In audit","auditing",0,180,"2026-09-16","2026-09-27","In audit","retired audit-stage id, replaced 09-27"),
("ec7ab06682664341a4b311d0cc4489b4","Ready for writing","writing",1,136,"2026-08-26","2026-10-29","Ready for writing",""),
("c4d28e69563f4750b5fd6dd2b8b820a0","Ready for auditing","auditing",0,116,"2026-09-16","2026-09-27","Ready for auditing","retired audit-stage id, replaced 09-27"),
("b3717af3cb1b4244a66a69b3deb42775","Drafting (Superwriter)","writing",0,87,"2026-09-23","2026-09-27","Drafting (Superwriter)","retired superwriter id, replaced 09-27"),
("31754684285a451cb4a9f78087e68251","Failed audit","auditing",1,67,"2026-09-27","2026-10-29","Failed audit",""),
("09ce3d525e46467abac517268fe11f11","Passed audit","auditing",0,64,"2026-09-16","2026-09-27","Passed audit","retired audit-stage id, replaced 09-27"),
("e2182e865efb40079fb59312f7ef3483","Needs Edits (2nd pass)","writing",0,64,"2026-09-09","2026-10-12","Needs Edits (stage 2)","retired; renamed Needs Edits (stage 2) on 10-12"),
("a55b7aec74404878bf49ee8ce156227d","Ready for auditing","auditing",0,49,"2026-09-02","2026-09-16","Ready for auditing","retired audit-stage id (first gen)"),
("537dbc5e07e84fbb8c2d78832291aa8d","Holdout","holding_tank",1,49,"2026-09-14","2026-10-28","Holdout",""),
("872569198d9848f4bad6f1ddce62e77a","In RFD audit","auditing",1,30,"2026-10-24","2026-10-28","In RFD audit",""),
("35000c8c8bdd42469bd591911ea846e3","Failed audit","auditing",0,26,"2026-09-16","2026-09-27","Failed audit","retired audit-stage id, replaced 09-27"),
("229b740430314b848b33d8a96f373710","Ready for writing (Superwriter)","writing",1,25,"2026-09-29","2026-10-28","Ready for writing (Superwriter)",""),
("34ca383ce1794ebab24ccb3af1367f4d","Ready for RFD audit","auditing",1,22,"2026-10-23","2026-10-27","Ready for RFD audit",""),
("f1cfaea218154a9db6817f0bb271893f","RFD audit pass","auditing",1,19,"2026-10-26","2026-10-28","RFD audit pass",""),
("afd300231a1649ca9e11d296aa570450","In audit","auditing",0,15,"2026-09-11","2026-09-16","In audit","retired audit-stage id (first gen)"),
("f3577518b7f641ae907aac040701227a","Needs Edits (stage 2)","writing",1,14,"2026-10-12","2026-10-20","Needs Edits (stage 2)",""),
("5e2ce8da14404856879ad26be7f9a3dd","Drafting (Superwriter) [retiring]","writing",0,12,"2026-09-27","2026-09-27","Drafting (Superwriter)","bulk migration 09-27 23:02, not real work"),
("ed573cb6844b407e9d919322887faf94","UNRESOLVED (between In review and In second pass)","holding_tank?",0,8,"2026-09-02","2026-09-02","Running trajectories?","task page errors; inferred from neighbours"),
("8cbc81af79b44bdbbe906f8d5162641f","Discarded","discarded",1,5,"2026-10-07","2026-10-18","Discarded",""),
("f5d5660c6b5a463a87326df758a7c8f0","Passed audit","auditing",0,2,"2026-09-16","2026-09-16","Passed audit","retired audit-stage id (first gen)"),
("2f4480a250504272bafe375320df065c","Failed audit","auditing",0,1,"2026-09-16","2026-09-16","Failed audit","retired audit-stage id (first gen)"),
("b4813415f99d4d4e8fe36669696b7b67","RFD audit fail","auditing",1,1,"2026-10-28","2026-10-28","RFD audit fail",""),
]
SMOKE = ["86b87aca5f1440aca6896cf534b90a98","36a97e42de554d91bde924ba35259564","fa858d426c6b4b428be7257ad1429ca0","2f0d031f16734fdc828e28b7074adb43","ee59a02ce8964d24808bb28dd7a24693","1617730951cb41948c4c4f07cefabbf1","2cae32fff1364a3ba9c3a0df4d7ffdb7","24977696d777483aa8db0f7dc2391dd1","15777e581f8f439292e4f1cb52c80b66","d85afa37fe7c4c5f9589f70266cfea0d"]
WRITER_OWNED = {"Ready for writing","Drafting","Needs Edits","Needs Edits (stage 2)","Ready for writing (Superwriter)","Drafting (Superwriter)","Needs Edits (Superwriter)"}
WRITER_SENDBACK = {"Needs Edits","Needs Edits (stage 2)"}
SW_SENDBACK = {"Needs Edits (Superwriter)"}
REVIEW_STAGE = {"In review","In stage 2 review","In review (Superreviewer)"}
PASSED_REVIEW = {"Ready for auditing","In audit","Passed audit","Holdout","Ready for delivery","Ready for RFD audit","In RFD audit","RFD audit pass"}
AUDIT_WORK = {"In audit","In RFD audit"}
AUDIT_FAIL = {"Failed audit","RFD audit fail"}
rows=[]
for sid,name,cat,act,n,f,l,canon,note in S:
    rows.append(dict(status_id="wfsta_"+sid,name=name,canonical=canon,stage_category=cat,active=bool(act),rows=n,first_seen=f,last_seen=l,
        writer_owned=canon in WRITER_OWNED, writer_sendback=canon in WRITER_SENDBACK, superwriter_sendback=canon in SW_SENDBACK,
        review_stage=canon in REVIEW_STAGE, passed_review_band=canon in PASSED_REVIEW, audit_work=canon in AUDIT_WORK,
        audit_fail=canon in AUDIT_FAIL, note=note))
for sid in SMOKE:
    rows.append(dict(status_id="wfsta_"+sid,name="(pre-launch smoke test, 2026-08-25)",canonical="EXCLUDE",stage_category="",active=False,rows=None,first_seen="2026-08-25",last_seen="2026-08-25",
        writer_owned=False,writer_sendback=False,superwriter_sendback=False,review_stage=False,passed_review_band=False,audit_work=False,audit_fail=False,note="exclude"))
with open("enki_status_map.csv","w",newline="") as fh:
    w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
json.dump(rows,open("enki_status_map.json","w"),indent=1)
print(len(rows),"statuses;",sum(r["active"] for r in rows),"active;",sum(r["rows"] or 0 for r in rows),"rows mapped")
