# vaultslip/wallet/gas.py
"""
Gas helpers for VaultSlip.
- Live gas price fetch
- Safety multiplier / ceilings
- Build a base transaction dict (chain-agnostic)
"""

from __future__ import annotations

from typing import Dict, Optional

from web3 import Web3

from vaultslip.config import settings
from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client


def current_gas_price_wei(chain: str) -> Optional[int]:
    ccfg = get_chain(chain)
    if not ccfg:
        return None
    try:
        w3 = get_client(ccfg)
        return int(w3.eth.gas_price)
    except Exception:
        return None


def apply_safety(gas_price_wei: Optional[int]) -> Optional[int]:
    if gas_price_wei is None:
        return None
    mult = float(settings.GAS_SAFETY_MULTIPLIER)
    return int(gas_price_wei * mult)


def build_tx_skeleton(
    *,
    chain: str,
    from_addr: str,
    to_addr: str,
    data: bytes = b"",
    value_wei: int = 0,
    gas_limit: Optional[int] = None,
    gas_price_wei: Optional[int] = None,
) -> Dict:
    """
    Build a basic EVM tx dict. Nonce is filled by the executor using nonce_manager.
    If gas_limit is None, caller can run estimate_gas before finalizing send.
    """
    to_addr = Web3.to_checksum_address(to_addr)
    from_addr = Web3.to_checksum_address(from_addr)
    tx = {
        "from": from_addr,
        "to": to_addr,
        "value": int(value_wei),
        "data": data if isinstance(data, (bytes, bytearray)) else bytes(data),
    }
    if gas_limit is not None:
        tx["gas"] = int(gas_limit)
    if gas_price_wei is not None:
        tx["gasPrice"] = int(gas_price_wei)
    return tx
