# vaultslip/verifier/abi_fetch.py
"""
ABI fetcher with local cache.
- Tries chain-specific explorers (Etherscan-style APIs) when keys are present
- Falls back to empty ABI ([]) if unavailable; verification/simulation should handle no-ABI paths
- Caches ABIs in data/cache/<CHAIN>_<ADDRESS>.abi.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from web3 import Web3

from vaultslip.config import settings

_CACHE_DIR = Path("data") / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---- Explorer routing --------------------------------------------------------

_EXPLORERS: Dict[str, Tuple[str, str]] = {
    # chain_name: (base_url, api_key_env)
    "ETH":  ("https://api.etherscan.io/api",              "ETHERSCAN_API_KEY"),
    "ARB":  ("https://api.arbiscan.io/api",               "ARBISCAN_API_KEY"),
    "OP":   ("https://api-optimistic.etherscan.io/api",   "OPTIMISTIC_ETHERSCAN_API_KEY"),
    "POLY": ("https://api.polygonscan.com/api",           "POLYGONSCAN_API_KEY"),
    "CELO": ("https://api.celoscan.io/api",               "CELOSCAN_API_KEY"),
}


def _cache_path(chain: str, address: str) -> Path:
    addr = Web3.to_checksum_address(address)
    return _CACHE_DIR / f"{chain.upper()}_{addr}.abi.json"


def _read_cache(chain: str, address: str) -> Optional[List[Dict[str, Any]]]:
    p = _cache_path(chain, address)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _write_cache(chain: str, address: str, abi: List[Dict[str, Any]]) -> None:
    p = _cache_path(chain, address)
    try:
        p.write_text(json.dumps(abi, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # cache write failures should not crash


def _etherscan_like_fetch(base_url: str, api_key: str, address: str) -> Optional[List[Dict[str, Any]]]:
    try:
        r = requests.get(
            base_url,
            params={"module": "contract", "action": "getabi", "address": address, "apikey": api_key},
            timeout=8,
        )
        if not r.ok:
            return None
        data = r.json()
        # Etherscan-style returns {"status":"1","message":"OK","result":"[...json abi..]"}
        result = data.get("result")
        if not result:
            return None
        # Some explorers already return parsed JSON; most return a JSON string
        if isinstance(result, str):
            return json.loads(result)
        if isinstance(result, list):
            return result
        return None
    except Exception:
        return None


def fetch_abi(chain: str, address: str) -> List[Dict[str, Any]]:
    """
    Returns a list ABI (can be empty). Never raises.
    Order:
      1) cache
      2) explorer (if configured)
      3) empty []
    """
    # 1) cache
    cached = _read_cache(chain, address)
    if isinstance(cached, list):
        return cached

    # 2) explorer
    chain = chain.upper()
    route = _EXPLORERS.get(chain)
    if route:
        base_url, key_env = route
        api_key = os.getenv(key_env, "")
        if api_key:
            abi = _etherscan_like_fetch(base_url, api_key, Web3.to_checksum_address(address))
            if isinstance(abi, list):
                _write_cache(chain, address, abi)
                return abi

    # 3) fallback: empty ABI (verification/simulation must handle ABI-less paths)
    return []


def has_function(abi: List[Dict[str, Any]], fn_name: str) -> bool:
    """Simple helper to check existence of a function by name in an ABI."""
    for e in abi:
        if e.get("type") == "function" and e.get("name") == fn_name:
            return True
    return False
