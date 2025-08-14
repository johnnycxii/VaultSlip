# run.py
"""
VaultSlip dry-run harness (zero-drift, single entrypoint).

Subcommands:
  python run.py discover   [--events] [--repos] [--addresses 0xabc,0xdef] [--chain ETH] [--window 3000] [--chunk 600] [--limit 5] [--notify]
  python run.py route      [--limit 5] [--notify] [--ethusd 3000] [--preview-sweeps]
  python run.py cycle      [--events] [--repos] [--addresses ...] [--chain ETH] [--window 3000] [--chunk 600] [--limit 5] [--notify] [--ethusd 3000] [--preview-sweeps]

Notes:
- No transactions are sent. This drafts decisions only.
- Telegram pings are optional via --notify (uses BOT_TOKEN/CHAT_ID).
"""

from __future__ import annotations

import argparse
from typing import List, Optional

from vaultslip.config import settings
from vaultslip.logging_utils import get_logger
from vaultslip.telemetry import send_telegram
from vaultslip.discovery.event_scanner import scan_all_enabled
from vaultslip.discovery.bytecode_scanner import scan_single as scan_bytecode_single
from vaultslip.discovery.repo_watcher import scan_curated
from vaultslip.discovery.intake import intake_single_batch
from vaultslip.state.models import Candidate, ClaimResult
from vaultslip.executor.claim_router import process_candidate

log = get_logger("vaultslip.run")


def _ping(text: str, notify: bool) -> None:
    if notify:
        send_telegram(text)


def _addr_list(arg: Optional[str] | List[str]) -> List[str]:
    if not arg:
        return []
    if isinstance(arg, list):
        out: List[str] = []
        for a in arg:
            if "," in a:
                out.extend([x.strip() for x in a.split(",") if x.strip()])
            else:
                out.append(a.strip())
        return out
    return [x.strip() for x in str(arg).split(",") if x.strip()]


def _discover_events(window: int, chunk: int, limit: int, notify: bool) -> List[Candidate]:
    log.info(f"scan_events window={window} chunk={chunk}")
    cands = scan_all_enabled(block_window=window, chunk_size=chunk)
    accepted = intake_single_batch(cands, max_new=limit)
    if accepted:
        _ping(f"🧭 VaultSlip: {len(accepted)} new event candidates", notify)
        for c in accepted:
            log.info("candidate_new", extra={"candidate": c.to_dict()})
    else:
        log.info("no_new_candidates_from_events")
    return accepted


def _discover_repos(limit: int, notify: bool) -> List[Candidate]:
    cands = scan_curated(limit=limit)
    accepted = intake_single_batch(cands)
    if accepted:
        _ping(f"📦 VaultSlip: {len(accepted)} curated repo candidates", notify)
        for c in accepted:
            log.info("candidate_new", extra={"candidate": c.to_dict()})
    else:
        log.info("no_curated_repo_candidates")
    return accepted


def _discover_addresses(addresses: List[str], chain: str, limit: int, notify: bool) -> List[Candidate]:
    out: List[Candidate] = []
    for addr in addresses[:limit]:
        cands = scan_bytecode_single(chain, addr)
        if not cands:
            continue
        out.extend(intake_single_batch(cands))
    if out:
        _ping(f"🧭 VaultSlip: {len(out)} new bytecode candidates on {chain}", notify)
        for c in out:
            log.info("candidate_new", extra={"candidate": c.to_dict()})
    else:
        log.info("no_new_candidates_from_addresses")
    return out


def _route(cands: List[Candidate], limit: int, notify: bool, ethusd: float, preview_sweeps: bool) -> None:
    if not cands:
        log.info("nothing_to_route")
        return
    count = 0
    for c in cands:
        if count >= limit:
            break
        res: ClaimResult = process_candidate(
            c,
            dry_run=True,
            eth_usd=float(ethusd),
            min_profit_usd=None,
            preview_sweeps_on_reject=preview_sweeps,
        )
        log.info("route_result", extra={"candidate": c.to_dict(), "ok": res.ok, "msg": res.message})
        if notify:
            status = "✅" if res.ok else "❌"
            _ping(f"{status} {c.chain}:{c.contract} – {res.message}", notify)
        count += 1


def main() -> None:
    ap = argparse.ArgumentParser(description="VaultSlip dry-run harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # discover
    ap_d = sub.add_parser("discover", help="discover and persist new candidates")
    ap_d.add_argument("--events", action="store_true", help="scan recent logs on enabled chains")
    ap_d.add_argument("--repos", action="store_true", help="scan curated repo list in data/repos.json")
    ap_d.add_argument("--addresses", nargs="*", help="explicit addresses (comma or space separated)")
    ap_d.add_argument("--chain", type=str, default="ETH", help="chain for --addresses scan")
    ap_d.add_argument("--window", type=int, default=3000, help="event scan window (blocks)")
    ap_d.add_argument("--chunk", type=int, default=600, help="event scan chunk size")
    ap_d.add_argument("--limit", type=int, default=5, help="max new candidates to accept")
    ap_d.add_argument("--notify", action="store_true", help="send Telegram pings")

    # route
    ap_r = sub.add_parser("route", help="route a set supplied in this invocation (typically after discover)")
    ap_r.add_argument("--limit", type=int, default=5, help="max candidates to route")
    ap_r.add_argument("--notify", action="store_true", help="send Telegram pings")
    ap_r.add_argument("--ethusd", type=float, default=3000.0, help="manual ETHUSD for gas calc")
    ap_r.add_argument("--preview-sweeps", action="store_true", help="log draft sweep txs even on rejects")

    # cycle (discover + route)
    ap_c = sub.add_parser("cycle", help="discover then immediately route")
    ap_c.add_argument("--events", action="store_true")
    ap_c.add_argument("--repos", action="store_true")
    ap_c.add_argument("--addresses", nargs="*", help="explicit addresses (comma or space separated)")
    ap_c.add_argument("--chain", type=str, default="ETH")
    ap_c.add_argument("--window", type=int, default=3000)
    ap_c.add_argument("--chunk", type=int, default=600)
    ap_c.add_argument("--limit", type=int, default=5)
    ap_c.add_argument("--notify", action="store_true")
    ap_c.add_argument("--ethusd", type=float, default=3000.0)
    ap_c.add_argument("--preview-sweeps", action="store_true")

    args = ap.parse_args()
    log.info("vaultslip_cli_start", extra={"env": settings.APP_ENV, "chains": settings.CHAINS, "cmd": args.cmd})

    if args.cmd == "discover":
        accepted: List[Candidate] = []
        if args.events:
            accepted.extend(_discover_events(args.window, args.chunk, args.limit, args.notify))
        if args.repos:
            accepted.extend(_discover_repos(args.limit, args.notify))
        addrs = _addr_list(args.addresses)
        if addrs:
            accepted.extend(_discover_addresses(addrs, args.chain.upper(), args.limit, args.notify))
        if not accepted:
            log.info("no_new_candidates")
        else:
            log.info("discover_done", extra={"accepted": len(accepted)})

    elif args.cmd == "route":
        # Intentionally requires candidates from same invocation (we don’t auto-pull a queue).
        log.info("route_requires_candidates_from_cycle", extra={"hint": "use cycle or pass candidates programmatically"})
        # No-op; kept for interface parity.

    elif args.cmd == "cycle":
        accepted: List[Candidate] = []
        if args.events:
            accepted.extend(_discover_events(args.window, args.chunk, args.limit, args.notify))
        if args.repos:
            accepted.extend(_discover_repos(args.limit, args.notify))
        addrs = _addr_list(args.addresses)
        if addrs:
            accepted.extend(_discover_addresses(addrs, args.chain.upper(), args.limit, args.notify))
        _route(accepted, args.limit, args.notify, ethusd=args.ethusd, preview_sweeps=args.preview_sweeps)
        log.info("cycle_done", extra={"accepted": len(accepted)})

    log.info("vaultslip_cli_done")


if __name__ == "__main__":
    main()
