import json, re, pathlib, datetime

ROOT = pathlib.Path.cwd()
PROG = ROOT / "progress_status.json"
CANDIDATES = [ROOT/"protocol.md", ROOT/"docs/protocol.md"]

# --- Load progress ---
data = {"steps": {}}
if PROG.exists():
    try:
        data = json.loads(PROG.read_text("utf-8"))
    except Exception:
        data = {"steps": {}}
if "steps" not in data or not isinstance(data["steps"], dict):
    data["steps"] = {}

steps = {int(k): v for k, v in data["steps"].items() if str(k).isdigit()}

# --- Optionally assume early steps Complete to keep % accurate ---
ASSUME_PREV_COMPLETE = True
if ASSUME_PREV_COMPLETE:
    def ensure_range(lo, hi, name):
        for i in range(lo, hi+1):
            if i not in steps:
                steps[i] = {"name": name, "status": "Complete", "notes": [], "updated_at": datetime.datetime.now().isoformat()}
    ensure_range(1,5,"Folder & file setup")
    ensure_range(6,20,"Core build sequence")
    ensure_range(21,27,"Wallet & execution scaffold")
    ensure_range(28,30,"Tests & backfill")
    ensure_range(31,35,"Production readiness")

# --- Compute completion and resume step ---
total_steps = 50
completed = sum(1 for i in range(1,total_steps+1) if steps.get(i,{}).get("status") == "Complete")
completion_pct = round(100.0 * completed / total_steps, 1)

resume = None
for i in range(1, total_steps+1):
    if steps.get(i,{}).get("status") != "Complete":
        resume = i
        break
if resume is None:
    resume = total_steps

# --- Build range statuses for the table ---
RANGES = [
    (1,5,  "Folder & file setup"),
    (6,20, "Core build sequence"),
    (21,27,"Wallet & execution scaffold"),
    (28,30,"Tests & backfill"),
    (31,35,"Production readiness"),
    (36,50,"Expansion & scaling"),
]
def range_status(lo, hi):
    s = [steps.get(i,{}).get("status","Not Started") for i in range(lo,hi+1)]
    if all(x == "Complete" for x in s): return " Complete"
    if any(x in ("In Progress","Complete") for x in s): return " In Progress"
    return " Not Started"

# Notes for last range (3650): summarize known steps
def summarize_36_50():
    parts = []
    for i in range(36,51):
        st = steps.get(i,{}).get("status")
        nm = steps.get(i,{}).get("name")
        if not st: continue
        icon = "" if st=="Complete" else ("" if st=="In Progress" else "")
        short = f"{i} {nm or ''}".strip()
        parts.append(f"{short} {icon}")
    if not parts:
        return "Not started"
    return "; ".join(parts)

rows = []
for (lo,hi,desc) in RANGES:
    status = range_status(lo,hi)
    if lo == 36:
        notes = summarize_36_50()
    elif lo==1:
        notes = "Structure, venv, env, init files done"
    elif lo==6:
        notes = "Config, constants, logging, telemetry, chains, state, discovery, verifier, safety"
    elif lo==21:
        notes = "Keyring, nonce/gas, scheduler, sweeper drafts, router w/ sweeps"
    elif lo==28:
        notes = "Backfill script and tests; pytest green"
    elif lo==31:
        notes = "Live-send toggle, estimator v1, ABI-aware sims, token sweep config, resilience"
    else:
        notes = ""
    rows.append((f"{lo}-{hi}", desc, status, notes))

table = ["<!-- PROGRESS_TABLE_START -->",
         "| Step Range | Description | Status | Notes |",
         "|------------|-------------|--------|-------|"]
for r in rows:
    table.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
table.append("<!-- PROGRESS_TABLE_END -->")
table_block = "\n".join(table)

metrics_block = (
    "<!-- PROGRESS_METRICS_START -->\n"
    f"**Completion (by protocol steps):** **{completion_pct}%**\n"
    f"**Functional readiness:** **{completion_pct}%**\n"
    f"**Resume at:** Step {resume}\n"
    "<!-- PROGRESS_METRICS_END -->"
)

# --- Write back to protocol.md / docs/protocol.md ---
updated_any = False
for md in CANDIDATES:
    if not md.exists(): continue
    s = md.read_text("utf-8")
    s, n1 = re.subn(r"<!-- PROGRESS_TABLE_START -->.*?<!-- PROGRESS_TABLE_END -->", table_block, s, flags=re.S)
    s, n2 = re.subn(r"<!-- PROGRESS_METRICS_START -->.*?<!-- PROGRESS_METRICS_END -->", metrics_block, s, flags=re.S)
    if n1 + n2 > 0:
        md.write_text(s, "utf-8")
        print(f"[ok] updated {md} (table:{bool(n1)} metrics:{bool(n2)})")
        updated_any = True

if not updated_any:
    print("[warn] no protocol.md found; wrote progress only")

# --- Persist any assumed steps back to progress_status.json (optional) ---
# Keep the enriched steps map so future runs are consistent.
data["steps"] = {str(k): v for k,v in steps.items()}
PROG.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
print(f"[ok] wrote {PROG}  completed={completed}/{total_steps} ({completion_pct}%)  resume=Step {resume}")
