# vaultslip/verifier/abi_sim.py
"""
ABI-aware claim simulation (read-only).

- Tries common claim-like functions using the contract ABI.
- Supports zero-arg and single address arg (uses wallet[0]).
- Uses eth_call only (never broadcasts).
"""

from __future__ import annotations
from typing import List, Optional, Tuple

from web3 import Web3
from eth_abi import encode as abi_encode  # provided with web3 deps
from eth_utils import keccak

from vaultslip.state.models import Candidate
from vaultslip.verifier.claim_sim import SimResult  # <-- correct source
from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.wallet.keyring import get_keyring
from vaultslip.verifier.abi_fetch import fetch_abi

# Names we consider "claim-like"
CANDIDATE_FN_NAMES = {
    "claim", "withdraw", "collect", "redeem", "release",
    "harvest", "getReward", "claimRewards", "withdrawRewards",
}

def _is_claim_like(fn_name: str) -> bool:
    low = fn_name.lower()
    return any(low == n.lower() for n in CANDIDATE_FN_NAMES)

def _pick_wallet_addr() -> str:
    return get_keyring().entry(0).address

def _encode_selector(sig: str) -> bytes:
    return keccak(text=sig)[:4]

def _build_call_data(fn_name: str, inputs: List[dict], wallet_addr: str) -> Optional[bytes]:
    # zero-arg
    if len(inputs) == 0:
        sig = f"{fn_name}()"
        return _encode_selector(sig)
    # single-arg(address)
    if len(inputs) == 1 and inputs[0].get("type") == "address":
        sig = f"{fn_name}(address)"
        selector = _encode_selector(sig)
        data = selector + abi_encode(["address"], [Web3.to_checksum_address(wallet_addr)])
        return data
    # ignore multi-arg for v1
    return None

def _try_call(w3: Web3, to_addr: str, data: bytes) -> Tuple[bool, Optional[int], Optional[int]]:
    try:
        ret = w3.eth.call({"to": Web3.to_checksum_address(to_addr), "data": data}, block_identifier="latest")
        ret_len = len(ret) if isinstance(ret, (bytes, bytearray)) else 0
        # best-effort gas estimate
        gas_est = None
        try:
            gas_est = w3.eth.estimate_gas({"to": Web3.to_checksum_address(to_addr), "data": data})
        except Exception:
            pass
        return True, gas_est, ret_len
    except Exception:
        return False, None, None

def abi_guided_simulate(cand: Candidate) -> SimResult:
    abi = fetch_abi(cand.chain, cand.contract)
    if not isinstance(abi, list) or not abi:
        return SimResult(ok=False, reason="no_abi", fn_tried=None, success_fn=None, gas_estimate=None, gas_price_wei=None, call_return_len=None)

    ccfg = get_chain(cand.chain)
    if not ccfg:
        return SimResult(ok=False, reason="chain_not_configured", fn_tried=None, success_fn=None, gas_estimate=None, gas_price_wei=None, call_return_len=None)
    w3 = get_client(ccfg)

    wallet_addr = _pick_wallet_addr()
    tried: List[str] = []

    fn_entries = [e for e in abi if e.get("type") == "function"]
    prioritized = [e for e in fn_entries if _is_claim_like(str(e.get("name", "")))]
    fallback = [e for e in fn_entries if len(e.get("inputs", [])) in (0, 1)]
    candidates = prioritized + [e for e in fallback if e not in prioritized]

    for f in candidates:
        name = str(f.get("name", ""))
        inputs = f.get("inputs", [])
        data = _build_call_data(name, inputs, wallet_addr)
        if data is None:
            continue
        label = name if len(inputs) == 0 else f"{name}(address)"
        tried.append(label)
        ok, gas_est, ret_len = _try_call(w3, cand.contract, data)
        if ok:
            return SimResult(
                ok=True,
                reason="ok",
                fn_tried=label,
                success_fn=label,
                gas_estimate=gas_est,
                gas_price_wei=None,
                call_return_len=ret_len,
            )

    return SimResult(ok=False, reason="abi_paths_exhausted", fn_tried=", ".join(tried) if tried else None, success_fn=None, gas_estimate=None, gas_price_wei=None, call_return_len=None)
