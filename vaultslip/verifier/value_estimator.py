# vaultslip/verifier/value_estimator.py
"""
Value Estimator v1 (read-only, conservative)

Scope:
- Native coin only (ETH / MATIC / CELO): queries contract balance via eth_getBalance.
- Converts to USD using per-chain native price:
    - If present in settings: NATIVE_USD_ETH, NATIVE_USD_POLY, NATIVE_USD_CELO
    - Else uses the eth_usd fallback passed by the caller for all chains.

Notes:
- No token pricing yet (ERC-20 support arrives in v2).
- Intentionally conservative: assumes at most the FULL native balance is withdrawable.
- Returns a small dict; callers can map into their own result types.
"""

from __future__ import annotations

from typing import Dict, Tuple

from web3 import Web3

from vaultslip.config import settings


def _native_symbol(chain: str) -> str:
    c = chain.upper()
    if c == "ETH":
        return "ETH"
    if c in ("POLY", "POLYGON"):
        return "MATIC"
    if c == "CELO":
        return "CELO"
    return "NATIVE"


def _native_price_usd(chain: str, eth_usd_fallback: float) -> float:
    """
    Pull a per-chain native price from settings if available; otherwise use fallback.
    Optional .env keys:
      NATIVE_USD_ETH, NATIVE_USD_POLY, NATIVE_USD_CELO
    """
    c = chain.upper()
    key = {
        "ETH": "NATIVE_USD_ETH",
        "POLY": "NATIVE_USD_POLY",
        "POLYGON": "NATIVE_USD_POLY",
        "CELO": "NATIVE_USD_CELO",
    }.get(c)
    if key and hasattr(settings, key):
        try:
            v = float(getattr(settings, key))  # type: ignore[attr-defined]
            if v > 0:
                return v
        except Exception:
            pass
    # Fallback: use eth_usd_fallback for all chains if nothing specific provided
    try:
        f = float(eth_usd_fallback)
        if f > 0:
            return f
    except Exception:
        pass
    return 0.0


def estimate_value_usd(
    *,
    chain: str,
    contract: str,
    w3: Web3,
    eth_usd_fallback: float,
) -> Dict[str, float | str]:
    """
    Conservative native value estimator.

    Returns:
      {
        "value_token": <symbol>,    # e.g., "ETH"/"MATIC"/"CELO"
        "value_amount": <float>,    # native units (ETH/MATIC/CELO)
        "value_usd": <float>        # USD estimate
      }
    """
    out = {
        "value_token": _native_symbol(chain),
        "value_amount": 0.0,
        "value_usd": 0.0,
    }

    try:
        bal_wei = int(w3.eth.get_balance(Web3.to_checksum_address(contract)))
    except Exception:
        return out

    if bal_wei <= 0:
        return out

    native_price = _native_price_usd(chain, eth_usd_fallback)
    if native_price <= 0:
        return out

    amount_native = bal_wei / 1e18
    out["value_amount"] = amount_native
    out["value_usd"] = amount_native * native_price
    return out
