# vaultslip/executor/claim_router.py
"""
Claim router with DRY/LIVE toggle + Value Estimator v1 + ABI-aware fallback.

Order:
  1) Zero-arg sim (claim_sim.simulate_candidate)
  2) If that fails, ABI-guided sim (abi_sim.abi_guided_simulate)
  3) Safety, optional history
  4) Value estimate (native balance)
  5) Gas/profit guard
  6) Draft TX (always), LIVE send only if dry_run=False AND EXECUTE_LIVE=true
  7) Optional sweep drafts

Everything remains read-only by default.
"""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Optional

from eth_utils import keccak
from web3 import Web3

from vaultslip.config import settings
from vaultslip.state.models import Candidate, ClaimResult
from vaultslip.verifier.claim_sim import simulate_candidate
from vaultslip.verifier.abi_sim import abi_guided_simulate
from vaultslip.safety.honeypot_rules import evaluate_safety
from vaultslip.verifier.history_check import verify_history
from vaultslip.safety.gas_sentry import gas_profit_ok
from vaultslip.wallet.keyring import get_keyring
from vaultslip.wallet.nonce_manager import get_next_nonce
from vaultslip.wallet.gas import current_gas_price_wei, apply_safety, build_tx_skeleton
from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.verifier.abi_fetch import fetch_abi
from vaultslip.verifier.value_estimator import estimate_value_usd
from vaultslip.executor.sweeper import draft_best_effort_sweeps
from vaultslip.executor.sender import guarded_send, should_execute_live
from vaultslip.logging_utils import get_claims_logger, get_security_logger

log_claims = get_claims_logger()
log_sec = get_security_logger()


def _selector_from_name(name: str) -> bytes:
    sig = name if "(" in name else f"{name}()"
    return keccak(text=sig)[:4]


def process_candidate(
    cand: Candidate,
    *,
    dry_run: bool = True,
    eth_usd: float = 3000.0,
    min_profit_usd: Optional[float] = None,
    preview_sweeps_on_reject: bool = False,
) -> ClaimResult:
    t0 = int(time.time())

    # 1) Try zero-arg sim first
    sim = simulate_candidate(cand)

    # 2) If zero-arg failed, try ABI-guided simulation
    if not sim.ok or not sim.success_fn:
        sim2 = abi_guided_simulate(cand)
        if sim2.ok and sim2.success_fn:
            sim = sim2  # adopt ABI-guided result
        else:
            msg = f"no_viable_callpath: {sim.reason if sim.reason else 'unknown'} / {sim2.reason}"
            log_sec.info(msg, extra={"cand": cand.to_dict(), "sim0": asdict(sim), "sim1": asdict(sim2), "mode": "DRY" if dry_run else "LIVE"})
            if preview_sweeps_on_reject and settings.POST_CLAIM_SWEEP:
                sweeps = draft_best_effort_sweeps(cand.chain, wallet_index=0)
                log_claims.info("sweep_preview_on_reject", extra={"cand": cand.to_dict(), "sweeps": sweeps, "mode": "DRY" if dry_run else "LIVE"})
            return ClaimResult(
                chain=cand.chain,
                contract=Web3.to_checksum_address(cand.contract),
                tx_sent=False,
                tx_hash=None,
                sweep_tx_hash=None,
                value_token="ETH",
                value_amount=0.0,
                value_usd=0.0,
                gas_usd=0.0,
                profit_usd=0.0,
                ok=False,
                message=msg,
                timestamp=t0,
            )

    # SAFETY onward stay the same as Step 32
    ccfg = get_chain(cand.chain)
    if not ccfg:
        return ClaimResult(
            chain=cand.chain,
            contract=Web3.to_checksum_address(cand.contract),
            tx_sent=False,
            tx_hash=None,
            sweep_tx_hash=None,
            value_token="ETH",
            value_amount=0.0,
            value_usd=0.0,
            gas_usd=0.0,
            profit_usd=0.0,
            ok=False,
            message="chain_not_configured",
            timestamp=t0,
        )
    w3 = get_client(ccfg)
    abi = fetch_abi(cand.chain, cand.contract)
    safe_ok, safe_reasons = evaluate_safety(w3, cand.contract, abi)
    if not safe_ok:
        msg = f"safety_blocked: {safe_reasons}"
        log_sec.info(msg, extra={"cand": cand.to_dict(), "safe": safe_reasons, "mode": "DRY" if dry_run else "LIVE"})
        if preview_sweeps_on_reject and settings.POST_CLAIM_SWEEP:
            sweeps = draft_best_effort_sweeps(cand.chain, wallet_index=0)
            log_claims.info("sweep_preview_on_reject", extra={"cand": cand.to_dict(), "sweeps": sweeps, "mode": "DRY" if dry_run else "LIVE"})
        return ClaimResult(
            chain=cand.chain,
            contract=Web3.to_checksum_address(cand.contract),
            tx_sent=False,
            tx_hash=None,
            sweep_tx_hash=None,
            value_token="ETH",
            value_amount=0.0,
            value_usd=0.0,
            gas_usd=0.0,
            profit_usd=0.0,
            ok=False,
            message=msg,
            timestamp=t0,
        )

    if settings.REQUIRE_HISTORY:
        hv = verify_history(cand.chain, cand.contract, min_distinct_callers=3)
        if not hv.ok:
            msg = f"history_not_verified: {hv.reason} ({hv.distinct_callers})"
            log_sec.info(msg, extra={"cand": cand.to_dict(), "hist": asdict(hv), "mode": "DRY" if dry_run else "LIVE"})
            if preview_sweeps_on_reject and settings.POST_CLAIM_SWEEP:
                sweeps = draft_best_effort_sweeps(cand.chain, wallet_index=0)
                log_claims.info("sweep_preview_on_reject", extra={"cand": cand.to_dict(), "sweeps": sweeps, "mode": "DRY" if dry_run else "LIVE"})
            return ClaimResult(
                chain=cand.chain,
                contract=Web3.to_checksum_address(cand.contract),
                tx_sent=False,
                tx_hash=None,
                sweep_tx_hash=None,
                value_token="ETH",
                value_amount=0.0,
                value_usd=0.0,
                gas_usd=0.0,
                profit_usd=0.0,
                ok=False,
                message=msg,
                timestamp=t0,
            )

    # Value estimate (native only, conservative)
    val = estimate_value_usd(chain=cand.chain, contract=cand.contract, w3=w3, eth_usd_fallback=eth_usd)
    est_token = str(val.get("value_token", "ETH"))
    est_amount = float(val.get("value_amount", 0.0))
    payout_usd = float(val.get("value_usd", 0.0))

    # Gas guard
    gas_price = apply_safety(current_gas_price_wei(cand.chain))
    gas_limit = sim.gas_estimate or 120_000

    verdict = gas_profit_ok(
        est_payout_usd=payout_usd,
        gas_limit=gas_limit,
        gas_price_wei=gas_price,
        eth_usd=float(eth_usd),
        min_profit_usd=min_profit_usd,
    )
    if not verdict.ok:
        msg = f"gas_profit_reject: {verdict.reason}"
        log_sec.info(msg, extra={"cand": cand.to_dict(), "verdict": asdict(verdict), "est": val, "mode": "DRY" if dry_run else "LIVE"})
        if preview_sweeps_on_reject and settings.POST_CLAIM_SWEEP:
            sweeps = draft_best_effort_sweeps(cand.chain, wallet_index=0)
            log_claims.info("sweep_preview_on_reject", extra={"cand": cand.to_dict(), "sweeps": sweeps, "mode": "DRY" if dry_run else "LIVE"})
        return ClaimResult(
            chain=cand.chain,
            contract=Web3.to_checksum_address(cand.contract),
            tx_sent=False,
            tx_hash=None,
            sweep_tx_hash=None,
            value_token=est_token,
            value_amount=est_amount,
            value_usd=payout_usd,
            gas_usd=verdict.est_gas_usd or 0.0,
            profit_usd=verdict.est_profit_usd or 0.0,
            ok=False,
            message=msg,
            timestamp=t0,
        )

    # Draft TX
    kr = get_keyring()
    from_addr = kr.entry(0).address
    to_addr = Web3.to_checksum_address(cand.contract)
    data = _selector_from_name(sim.success_fn)  # includes "(address)" if that was the winner
    tx = build_tx_skeleton(
        chain=cand.chain,
        from_addr=from_addr,
        to_addr=to_addr,
        data=data,
        value_wei=0,
        gas_limit=gas_limit,
        gas_price_wei=gas_price,
    )
    try:
        tx["nonce"] = get_next_nonce(cand.chain, from_addr)
    except Exception:
        pass

    # DRY vs LIVE
    live_allowed = (not dry_run) and should_execute_live()
    if not live_allowed:
        log_claims.info("draft_tx", extra={"cand": cand.to_dict(), "tx": {k: (v.hex() if isinstance(v, (bytes, bytearray)) else v) for k, v in tx.items()}, "est": val, "mode": "DRY"})
        if settings.POST_CLAIM_SWEEP:
            sweeps = draft_best_effort_sweeps(cand.chain, wallet_index=0)
            log_claims.info("draft_sweeps", extra={"cand": cand.to_dict(), "sweeps": sweeps, "mode": "DRY"})
        return ClaimResult(
            chain=cand.chain,
            contract=to_addr,
            tx_sent=False,
            tx_hash=None,
            sweep_tx_hash=None,
            value_token=est_token,
            value_amount=est_amount,
            value_usd=payout_usd,
            gas_usd=0.0,
            profit_usd=0.0,
            ok=True,
            message="draft_tx_ready_with_sweeps" if settings.POST_CLAIM_SWEEP else "draft_tx_ready",
            timestamp=t0,
        )

    send_res = guarded_send(chain=cand.chain, wallet_index=0, tx=tx)
    if send_res.sent:
        log_claims.info("tx_sent", extra={"cand": cand.to_dict(), "tx_hash": send_res.tx_hash, "est": val, "mode": "LIVE"})
        if settings.POST_CLAIM_SWEEP:
            sweeps = draft_best_effort_sweeps(cand.chain, wallet_index=0)
            log_claims.info("draft_sweeps_post_send", extra={"cand": cand.to_dict(), "sweeps": sweeps, "mode": "LIVE"})
        return ClaimResult(
            chain=cand.chain,
            contract=to_addr,
            tx_sent=True,
            tx_hash=send_res.tx_hash,
            sweep_tx_hash=None,
            value_token=est_token,
            value_amount=est_amount,
            value_usd=payout_usd,
            gas_usd=0.0,
            profit_usd=0.0,
            ok=True,
            message="tx_broadcast",
            timestamp=t0,
        )

    log_sec.info("live_send_failed", extra={"cand": cand.to_dict(), "reason": send_res.reason, "est": val, "mode": "LIVE"})
    return ClaimResult(
        chain=cand.chain,
        contract=to_addr,
        tx_sent=False,
        tx_hash=None,
        sweep_tx_hash=None,
        value_token=est_token,
        value_amount=est_amount,
        value_usd=payout_usd,
        gas_usd=0.0,
        profit_usd=0.0,
        ok=False,
        message=f"live_send_failed: {send_res.reason}",
        timestamp=t0,
    )
