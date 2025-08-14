# vaultslip/verifier/claim_sim.py
"""
Read-only claim simulation for VaultSlip.
- Attempts conservative zero-arg calls for claim-like functions (claim(), withdraw(), collect(), redeem())
- Uses eth_call (static) to detect non-reverting paths
- Optionally estimates gas via estimate_gas (still read-only)
- Does NOT send transactions or perform approvals
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from eth_utils import keccak, to_checksum_address
from web3 import Web3

from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.config import settings
from vaultslip.state.models import Candidate


# Only zero-arg forms are attempted here. Parametric forms are verified in later stages with ABI knowledge.
_ZERO_ARG_NAMES = [n for n in settings.DISCOVERY_FUNCTION_SIGS if n in {"claim", "withdraw", "collect", "redeem"}]


def _selector(signature: str) -> bytes:
    """
    Given a full signature like 'claim()' return 4-byte selector.
    Assumes zero-arg. We generate 'name()' from plain name if needed.
    """
    sig = signature if "(" in signature else f"{signature}()"
    return keccak(text=sig)[:4]


@dataclass(slots=True)
class SimResult:
    ok: bool
    reason: str
    fn_tried: Optional[str]
    success_fn: Optional[str]
    gas_estimate: Optional[int]          # units of gas (not wei)
    gas_price_wei: Optional[int]         # wei per gas at time of check
    call_return_len: Optional[int]


def _eth_call(w3: Web3, to_addr: str, data: bytes) -> Tuple[bool, Optional[bytes]]:
    try:
        res: bytes = w3.eth.call({"to": to_addr, "data": data})
        return True, res or b""
    except Exception:
        return False, None


def _estimate_gas(w3: Web3, from_addr: str, to_addr: str, data: bytes) -> Optional[int]:
    try:
        return int(w3.eth.estimate_gas({"from": from_addr, "to": to_addr, "data": data}))
    except Exception:
        return None


def simulate_candidate(candidate: Candidate) -> SimResult:
    """
    Try zero-arg claim-like function calls on the candidate's contract.
    Conservative: success = non-reverting call; we'll refine eligibility/value later.
    """
    ccfg = get_chain(candidate.chain)
    if not ccfg:
        return SimResult(False, "chain_not_configured", None, None, None, None, None)
    w3 = get_client(ccfg)

    to_addr = to_checksum_address(candidate.contract)
    from_addr = to_checksum_address("0x0000000000000000000000000000000000000001")  # inert placeholder

    gas_price = None
    try:
        gas_price = int(w3.eth.gas_price)
    except Exception:
        gas_price = None

    # Try each zero-arg candidate function
    for name in _ZERO_ARG_NAMES:
        sig_sel = _selector(name)
        ok, ret = _eth_call(w3, to_addr, sig_sel)
        if not ok:
            continue

        # If call didn't revert, consider it a potential claim path.
        gas_est = _estimate_gas(w3, from_addr, to_addr, sig_sel)

        return SimResult(
            ok=True,
            reason="eth_call_success",
            fn_tried=name + "()",
            success_fn=name + "()",
            gas_estimate=gas_est,
            gas_price_wei=gas_price,
            call_return_len=len(ret) if ret is not None else None,
        )

    return SimResult(
        ok=False,
        reason="no_zeroarg_claim_paths_found",
        fn_tried=None,
        success_fn=None,
        gas_estimate=None,
        gas_price_wei=gas_price,
        call_return_len=None,
    )
