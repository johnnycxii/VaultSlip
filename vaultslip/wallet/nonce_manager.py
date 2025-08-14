# vaultslip/wallet/nonce_manager.py
"""
Deterministic nonce management for VaultSlip.
- Reads on-chain nonce (pending) and caches per (chain,address)
- Provides get_next_nonce(...) and bump_nonce(...) helpers
- Thread-safe via a simple per-key lock
"""

from __future__ import annotations

import threading
from typing import Dict, Tuple

from web3 import Web3

from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client


# Cache: {(chain, address) -> nonce_int}
_NONCE_CACHE: Dict[Tuple[str, str], int] = {}
_LOCKS: Dict[Tuple[str, str], threading.Lock] = {}
_GLOBAL_LOCK = threading.RLock()


def _lock_for(key: Tuple[str, str]) -> threading.Lock:
    with _GLOBAL_LOCK:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


def _fetch_pending_nonce(w3: Web3, address: str) -> int:
    # 'pending' to include mempool txs
    return int(w3.eth.get_transaction_count(address, block_identifier="pending"))


def get_next_nonce(chain: str, address: str) -> int:
    """
    Returns the next nonce to use for (chain,address).
    If cache is empty/outdated, refresh from RPC 'pending'.
    """
    key = (chain.upper(), Web3.to_checksum_address(address))
    lock = _lock_for(key)
    with lock:
        ccfg = get_chain(chain)
        if not ccfg:
            raise RuntimeError(f"Chain not configured: {chain}")
        w3 = get_client(ccfg)
        onchain = _fetch_pending_nonce(w3, key[1])
        cached = _NONCE_CACHE.get(key)
        if cached is None or onchain > cached:
            _NONCE_CACHE[key] = onchain
            return onchain
        # Use cached (we increment locally after each send)
        return cached


def bump_nonce(chain: str, address: str) -> int:
    """
    Increments the cached nonce *locally* (after we construct/send a tx).
    Returns the incremented value.
    """
    key = (chain.upper(), Web3.to_checksum_address(address))
    lock = _lock_for(key)
    with lock:
        if key not in _NONCE_CACHE:
            # If not present, initialize from RPC
            ccfg = get_chain(chain)
            if not ccfg:
                raise RuntimeError(f"Chain not configured: {chain}")
            w3 = get_client(ccfg)
            _NONCE_CACHE[key] = _fetch_pending_nonce(w3, key[1])
        _NONCE_CACHE[key] += 1
        return _NONCE_CACHE[key]
