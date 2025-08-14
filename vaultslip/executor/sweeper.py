# vaultslip/executor/sweeper.py
"""
Sweep helpers (dry-run):
- Build native sweep tx (ETH/MATIC/CELO) from hot wallet -> SWEEP_WALLET
- Build ERC20 sweep tx (transfer all) using minimal ABI encode
- No sending here; returns tx dicts for the executor to sign/send later
"""

from __future__ import annotations

from typing import Optional, Dict

from eth_abi import encode as abi_encode
from eth_utils import keccak
from web3 import Web3

from vaultslip.config import settings
from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.wallet.gas import current_gas_price_wei, apply_safety, build_tx_skeleton
from vaultslip.wallet.nonce_manager import get_next_nonce
from vaultslip.wallet.keyring import get_keyring


# --- helpers -----------------------------------------------------------------

def _selector(sig: str) -> bytes:
    # e.g. "transfer(address,uint256)"
    return keccak(text=sig)[:4]


def _erc20_transfer_data(to_addr: str, amount_wei: int) -> bytes:
    sel = _selector("transfer(address,uint256)")
    data = sel + abi_encode(["address", "uint256"], [Web3.to_checksum_address(to_addr), int(amount_wei)])
    return data


# --- public API --------------------------------------------------------------

def draft_native_sweep(chain: str, from_addr: str, *, leave_wei: int = 0, gas_limit: int = 35_000) -> Optional[Dict]:
    """
    Draft a native-asset sweep tx (sending balance - leave_wei).
    Returns tx dict with nonce, gasPrice, gas prefilled; or None on failure.
    """
    ccfg = get_chain(chain)
    if not ccfg:
        return None
    w3 = get_client(ccfg)
    try:
        bal = int(w3.eth.get_balance(Web3.to_checksum_address(from_addr)))
    except Exception:
        return None
    value = max(0, bal - int(leave_wei))
    if value <= 0:
        return None

    gp = apply_safety(current_gas_price_wei(chain))
    if gp is None:
        return None

    tx = build_tx_skeleton(
        chain=chain,
        from_addr=from_addr,
        to_addr=settings.SWEEP_WALLET,
        value_wei=value,
        data=b"",
        gas_limit=gas_limit,
        gas_price_wei=gp,
    )
    try:
        tx["nonce"] = get_next_nonce(chain, from_addr)
    except Exception:
        pass
    return tx


def draft_erc20_sweep(chain: str, token: str, from_addr: str, *, gas_limit: int = 75_000) -> Optional[Dict]:
    """
    Draft an ERC20 sweep (transfer entire token balance to SWEEP_WALLET).
    Uses minimal call to balanceOf and transfer; no approvals.
    Returns tx dict or None on failure/zero balance.
    """
    ccfg = get_chain(chain)
    if not ccfg:
        return None
    w3 = get_client(ccfg)

    # balanceOf(from)
    try:
        balof_sel = _selector("balanceOf(address)")
        bal_data = balof_sel + abi_encode(["address"], [Web3.to_checksum_address(from_addr)])
        raw = w3.eth.call({"to": Web3.to_checksum_address(token), "data": bal_data})
        if not raw:
            return None
        # decode uint256 (padded 32 bytes)
        bal = int.from_bytes(raw[-32:], "big")
    except Exception:
        return None

    if bal <= 0:
        return None

    gp = apply_safety(current_gas_price_wei(chain))
    if gp is None:
        return None

    tx = build_tx_skeleton(
        chain=chain,
        from_addr=from_addr,
        to_addr=token,
        data=_erc20_transfer_data(settings.SWEEP_WALLET, bal),
        value_wei=0,
        gas_limit=gas_limit,
        gas_price_wei=gp,
    )
    try:
        tx["nonce"] = get_next_nonce(chain, from_addr)
    except Exception:
        pass
    return tx


def draft_best_effort_sweeps(chain: str, wallet_index: int) -> Dict[str, Optional[Dict]]:
    """
    Convenience: build both native + ERC20(USDC/WETH/etc) sweeps if non-zero.
    Returns dict with keys: native, usdc, weth (may be None if zero).
    Token addresses should be supplied later via config; here we only show native.
    """
    kr = get_keyring()
    from_addr = kr.entry(wallet_index).address
    out: Dict[str, Optional[Dict]] = {}

    out["native"] = draft_native_sweep(chain, from_addr)
    # Placeholders for future token sweeps (disabled until tokens list is configured)
    out["usdc"] = None
    out["weth"] = None
    return out
