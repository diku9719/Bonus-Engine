"""POST /api/refresh — pull live task history from RL Studio and recompute the dashboard.

Runs on Vercel (Python runtime). Behind middleware.js, so only logged-in users reach it.
The Studio key never leaves the server. The SQL is fixed in engine/enki_ledger_api.sql;
nothing the browser sends is passed to Studio.

Vercel environment variables:
  STUDIO_API_KEY         required  the RL Studio key (rls-sk-...)
  STUDIO_AUTH            optional  "bearer" (default: Authorization: Bearer <key>) or "x-api-key"
  STUDIO_CAMPAIGN_ID     optional  default camp_0d3de3902b854d7f8d5fc03b8490aa60 (Project Enki 2 (WS)); sent as X-Campaign-Id
  STUDIO_COMPANY_ID      optional  default comp_2fa4115109d741cd94a3c409ed89e61f (the company Studio uses for this project); sent as X-Company-Id
  STUDIO_EXTRA_HEADERS   optional  JSON object of extra headers if Studio needs them, e.g. {"x-company-id": "comp_..."}
  STUDIO_API_URL         optional  default https://api.studio.mercor.com/querier/unstructured
  STUDIO_USER_AGENT      optional  default "enki-metrics-dashboard/1.0". Studio sits behind Cloudflare, which blocks
                                   Python's default "Python-urllib" signature (error 1010).
"""
from http.server import BaseHTTPRequestHandler
import csv, glob, json, os, subprocess, sys, tempfile, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the metrics/ folder (Vercel Root Directory)
ENGINE = os.path.join(ROOT, "engine")   # bonus_engine.py, build_site.py, settings, status map, query
SQL_FILE = os.path.join(ENGINE, "enki_ledger_api.sql")
REUSE_S = 60                          # a refresh within 60 s of the last one (same server) reuses that result
_last = {"t": 0.0, "data": None}
WEEK_NAMES = ["meta", "writers", "reviewers", "superwriters", "auditors", "waiting", "alerts"]   # one set per bonus week
SHARED = ["pipeline", "ledger"]                                                              # same for every week


def studio_query(sql):
    url = os.environ.get("STUDIO_API_URL", "https://api.studio.mercor.com/querier/unstructured")
    key = os.environ.get("STUDIO_API_KEY", "")
    if not key:
        raise RuntimeError("STUDIO_API_KEY is not set in the Vercel project")
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": os.environ.get("STUDIO_USER_AGENT", "enki-metrics-dashboard/1.0"),
               # Studio scopes the querier to one project: it answers "X-Campaign-Id header required" without this
               "X-Campaign-Id": os.environ.get("STUDIO_CAMPAIGN_ID", "camp_0d3de3902b854d7f8d5fc03b8490aa60"),
               "X-Company-Id": os.environ.get("STUDIO_COMPANY_ID", "comp_2fa4115109d741cd94a3c409ed89e61f")}
    if os.environ.get("STUDIO_AUTH", "bearer").lower() == "x-api-key":
        headers["x-api-key"] = key
    else:
        headers["Authorization"] = "Bearer " + key
    if os.environ.get("STUDIO_EXTRA_HEADERS"):
        headers.update(json.loads(os.environ["STUDIO_EXTRA_HEADERS"]))
    req = urllib.request.Request(url, data=json.dumps({"query": sql}).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read()[:2000].decode("utf-8", "replace")
        try:                                   # Cloudflare / FastAPI JSON errors: keep the readable part
            j = json.loads(raw)
            detail = j.get("title") or j.get("detail") or raw
            if j.get("error_code"):
                detail = f"{detail} (Cloudflare {j['error_code']})"
        except ValueError:
            detail = raw[:200]
        raise RuntimeError(f"Studio answered {e.code}: {detail}") from None


def rebuild(answer, work):
    cols, rows = answer.get("column_names"), answer.get("rows")
    if not cols or rows is None:
        raise RuntimeError(f"Unexpected Studio answer (keys: {sorted(answer)[:6]})")
    if len(rows) >= 50000:
        raise RuntimeError("Studio returned 50,000 rows, the query limit; raise LIMIT in enki_ledger_api.sql")
    ledger = os.path.join(work, "ledger.csv")
    with open(ledger, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols] if isinstance(r, dict) else r)
    # one run per bonus week (engine/weeks/*.json), in parallel; each run is the engine then the site builder
    weeks = sorted(glob.glob(os.path.join(ENGINE, "weeks", "*.json")))
    if not weeks:
        raise RuntimeError("No week settings in engine/weeks/")
    procs = {}
    for cfg in weeks:
        wid = os.path.splitext(os.path.basename(cfg))[0]
        env = dict(os.environ, BONUS_CONFIG=cfg, BONUS_OUT=os.path.join(work, wid, "out"), SITE_DATA=os.path.join(work, wid, "data"))
        cmd = f'"{sys.executable}" "{os.path.join(ENGINE, "bonus_engine.py")}" "{ledger}" && "{sys.executable}" "{os.path.join(ENGINE, "build_site.py")}" "{ledger}"'
        procs[wid] = subprocess.Popen(cmd, shell=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    by_week = {}
    for wid, p in procs.items():
        _, err = p.communicate(timeout=50)
        if p.returncode != 0:
            raise RuntimeError(f"week {wid} failed: {err.strip()[-300:]}")
        by_week[wid] = {n: json.load(open(os.path.join(work, wid, "data", f"{n}.json"))) for n in WEEK_NAMES}
    last = list(by_week)[-1]
    out = {n: json.load(open(os.path.join(work, last, "data", f"{n}.json"))) for n in SHARED}
    out["weeks"] = [{"id": w, "label": by_week[w]["meta"].get("week", w)} for w in by_week]
    out["by_week"] = by_week
    return out


class handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(405, {"error": "Use POST"})

    def do_POST(self):
        now = time.time()
        if _last["data"] is not None and now - _last["t"] < REUSE_S:
            return self._send(200, _last["data"])   # protects Studio from bursts; data is at most a minute old
        started = time.time()
        try:
            sql = open(SQL_FILE).read()
            sql = "\n".join(l for l in sql.splitlines() if not l.startswith("--"))
            answer = studio_query(sql)
            with tempfile.TemporaryDirectory() as work:
                data = rebuild(answer, work)
            data["refreshed_at"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
            data["refresh_seconds"] = round(time.time() - started, 1)
            _last.update(t=time.time(), data=data)
            self._send(200, data)
        except Exception as e:  # message only; never the key
            self._send(502, {"error": str(e)[:400]})
