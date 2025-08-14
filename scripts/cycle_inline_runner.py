import os, sys, json, importlib, re, time

repo = os.environ.get("VS_REPO_ROOT") or os.getcwd()
if repo not in sys.path:
    sys.path.insert(0, repo)

os.environ["EXECUTE_LIVE"] = "false"

# Force 5s HTTP timeouts (affects web3 HTTP)
try:
    import requests, requests.sessions
    _orig = requests.sessions.Session.request
    def _rq(self, method, url, **kw):
        kw.setdefault("timeout", 5)
        return _orig(self, method, url, **kw)
    requests.sessions.Session.request = _rq
except Exception as e:
    print("[cycle v11] timeout patch skipped:", type(e).__name__, e)

print("[cycle v11] start; repo=", repo, "rpc=", os.environ.get("RPC_URI"))

# Candidate set: up to 5 from data/queue.json, else fallback
cands = []
try:
    with open(os.path.join(repo, "data", "queue.json"), "r", encoding="utf-8") as f:
        q = json.load(f)
    if isinstance(q, list):
        for item in q[:5]:
            if isinstance(item, dict):
                addr = item.get("contract") or item.get("address")
                chain = (item.get("chain") or "ETH").upper()
                pattern = item.get("pattern") or "auto_cycle"
                if isinstance(addr, str) and re.fullmatch(r"0x[a-fA-F0-9]{40}", addr or ""):
                    cands.append((chain, addr, pattern))
except Exception:
    pass

if not cands:
    cands = [("ETH", "0x966a707d9787fd5be0c38900f393f0ff86a0ac1b", "manual_abi_sim")]

router = importlib.import_module("vaultslip.executor.claim_router")
C = getattr(router, "Candidate")

ran = oks = errs = 0
t0 = time.time()
for chain, addr, pattern in cands:
    try:
        cand = C(chain=chain, contract=addr, origin="cycle_dryrun", pattern=pattern)
        res = router.process_candidate(cand, dry_run=True)
        ok  = bool(getattr(res, "ok", False))
        msg = getattr(res, "message", "")
        print(f"[cycle v11] {chain} {addr[:10]} ok={ok} msg={msg}")
        oks += 1 if ok else 0
        ran += 1
    except Exception as e:
        print(f"[cycle v11] ERROR {chain} {addr[:10]} -> {type(e).__name__}: {e}")
        errs += 1

t1 = time.time()
print(f"[cycle v11] summary: ran={ran} ok={oks} errs={errs} elapsed={t1 - t0:.2f}s")
