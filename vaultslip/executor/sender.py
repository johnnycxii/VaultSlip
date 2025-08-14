# vaultslip/executor/sender.py
"""
Live-send toggle & signer path for VaultSlip.

- Absolutely NO broadcast unless EXECUTE_LIVE=true in settings (env).
- Signs with Keyring (HD wallets); never prints secrets.
- Fills chainId & nonce safely; uses legacy gasPrice (simple & reliable).
- Mirrors dry-run behavior with structured results.

Usage (example):
    from vaultslip.executor.sender import guarded_send, should_execute_live
    res = guarded_send(chain="ETH", wallet_index=0, tx=tx_dict)
    # res.ok, res.sent, res.tx_hash, res.reason

This module does not estimate gas. Callers should supply gas & gasPrice (see wallet.gas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from web3 import Web3

from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.wallet.keyring import get_keyring
from vaultslip.wallet.nonce_manager import get_next_nonce, bump_nonce
from vaultslip.config import settings
from vaultslip.logging_utils import get_claims_logger, get_security_logger

log_claims = get_claims_logger()
log_sec = get_security_logger()


@dataclass(slots=True, frozen=True)
class SendResult:
    ok: bool
    sent: bool
    reason: str
    tx_hash: Optional[str]
    tx: Dict[str, Any]


def _bool_env(attr: str, default: bool = False) -> bool:
    # Be tolerant if the setting doesn't exist yet
    val = getattr(settings, attr, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        return v in ("1", "true", "yes", "on")
    return default


def should_execute_live() -> bool:
    """
    Global hard gate. Returns True only if EXECUTE_LIVE=true.
    Tip: keep this false until Steps 32–35 are done.
    """
    return _bool_env("EXECUTE_LIVE", False)


def _ensure_base_fields(chain: str, tx: Dict[str, Any]) -> tuple[Optional[Web3], Optional[str], Optional[str]]:
    ccfg = get_chain(chain)
    if not ccfg:
        return None, None, "chain_not_configured"
    w3 = get_client(ccfg)
    if "from" not in tx or "to" not in tx:
        return None, None, "tx_missing_from_or_to"
    try:
        from_addr = Web3.to_checksum_address(tx["from"])
        _ = Web3.to_checksum_address(tx["to"])
    except Exception:
        return None, None, "bad_address_format"
    return w3, from_addr, None


def _fill_defaults(w3: Web3, chain: str, from_addr: str, tx: Dict[str, Any]) -> None:
    # chainId
    if "chainId" not in tx:
        try:
            tx["chainId"] = int(w3.eth.chain_id)
        except Exception:
            # Fall back to common ids is dangerous; prefer explicit failure later
            pass
    # nonce
    if "nonce" not in tx:
        try:
            tx["nonce"] = get_next_nonce(chain, from_addr)
        except Exception:
            # leave unset; signing will fail and we log it
            pass


def guarded_send(*, chain: str, wallet_index: int, tx: Dict[str, Any]) -> SendResult:
    """
    If EXECUTE_LIVE=false -> returns ok=True, sent=False, reason='dry_run', with tx echoed.
    If true -> signs & broadcasts. On success, bumps nonce in cache and returns sent=True.
    """
    # Always validate basic fields first
    w3, from_addr, err = _ensure_base_fields(chain, tx)
    if err:
        log_sec.info("send_guard_reject", extra={"chain": chain, "reason": err, "tx": tx})
        return SendResult(ok=False, sent=False, reason=err, tx_hash=None, tx=tx)

    # Fill chainId/nonce if missing
    _fill_defaults(w3, chain, from_addr, tx)

    # Hard gate
    if not should_execute_live():
        # Mirror dry-run output; nothing is signed or sent
        log_claims.info("dry_run_send_blocked", extra={"chain": chain, "tx_preview": tx})
        return SendResult(ok=True, sent=False, reason="dry_run", tx_hash=None, tx=tx)

    # Sanity: require gas & gasPrice (we use legacy gas to stay universal)
    if "gas" not in tx or "gasPrice" not in tx:
        log_sec.info("send_guard_reject", extra={"chain": chain, "reason": "gas_fields_missing", "tx": tx})
        return SendResult(ok=False, sent=False, reason="gas_fields_missing", tx_hash=None, tx=tx)

    # Sign
    try:
        kr = get_keyring()
        acct = kr.account(wallet_index)
        signed = w3.eth.account.sign_transaction(tx, private_key=acct.key)
    except Exception as e:
        log_sec.info("sign_exception", extra={"chain": chain, "err": str(e)})
        return SendResult(ok=False, sent=False, reason="sign_failed", tx_hash=None, tx=tx)

    # Broadcast
    try:
        raw = signed.rawTransaction
        txh = w3.eth.send_raw_transaction(raw)
        hex_hash = txh.hex()
        bump_nonce(chain, from_addr)  # optimistic bump
        log_claims.info("tx_broadcast", extra={"chain": chain, "tx_hash": hex_hash})
        return SendResult(ok=True, sent=True, reason="sent", tx_hash=hex_hash, tx=tx)
    except Exception as e:
        # Do not bump nonce on broadcast failure
        log_sec.info("broadcast_exception", extra={"chain": chain, "err": str(e)})
        return SendResult(ok=False, sent=False, reason="broadcast_failed", tx_hash=None, tx=tx)
