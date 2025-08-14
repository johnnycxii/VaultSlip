# vaultslip/discovery/event_scanner.py
"""
Event-log scanner (read-only) for VaultSlip.
- Uses EVENT_SIGNATURES to build topics[0] filters
- Scans a recent block window per chain for matching logs
- Emits Candidate objects tagged origin="event"
"""

from __future__ import annotations

import time
from typing import Iterable, List, Optional, Tuple

from web3 import Web3

from vaultslip.chains.registry import enabled_chains, get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.discovery.signatures import EVENT_SIGNATURES
from vaultslip.state.models import Candidate
from vaultslip.state import store


def _topic0_hashes(w3: Web3) -> List[str]:
    # keccak of the full event signature string, e.g. "RefundProcessed(address,uint256)"
    return [w3.keccak(text=sig).hex() for sig in EVENT_SIGNATURES]


def _scan_range(w3: Web3, start_block: int, end_block: int, topic0s: List[str]) -> List[Tuple[str, int]]:
    """
    Returns list of (address, blockNumber) for any logs with topic0 in topic0s.
    """
    out: List[Tuple[str, int]] = []
    for t0 in topic0s:
        try:
            logs = w3.eth.get_logs({
                "fromBlock": start_block,
                "toBlock": end_block,
                "topics": [t0],
            })
        except Exception:
            # If an RPC errors due to range too large, caller should chunk; here we just skip silently
            logs = []
        for lg in logs:
            # Ensure address is checksummed
            addr = Web3.to_checksum_address(lg["address"])
            out.append((addr, int(lg["blockNumber"])))
    return out


def _chunked_scan(w3: Web3, window: int, chunk: int, topic0s: List[str]) -> List[Tuple[str, int]]:
    """
    Scans the last `window` blocks in chunks of `chunk` size to avoid RPC limits.
    """
    try:
        latest = int(w3.eth.block_number)
    except Exception:
        return []

    start = max(0, latest - window + 1)
    out: List[Tuple[str, int]] = []
    cur = start
    while cur <= latest:
        end = min(cur + chunk - 1, latest)
        out.extend(_scan_range(w3, cur, end, topic0s))
        cur = end + 1
    return out


def _make_candidate(chain: str, address: str, blk: int) -> Candidate:
    # We don't know the exact pattern from events alone; tag a generic label for now.
    return Candidate(
        chain=chain,
        contract=address,
        origin="event",
        pattern="event_payout",  # refined later during verification
        discovered_block=blk,
        notes=None,
    )


def scan_recent(chain: str, block_window: int = 20_000, chunk_size: int = 2_000) -> List[Candidate]:
    """
    Scan a single chain for recent payout-like events.
    - block_window: how many latest blocks to search
    - chunk_size: per-call range to stay below RPC limits
    """
    ccfg = get_chain(chain)
    if not ccfg:
        return []
    w3 = get_client(ccfg)

    topic0s = _topic0_hashes(w3)
    hits = _chunked_scan(w3, window=block_window, chunk=chunk_size, topic0s=topic0s)
    out: List[Candidate] = []
    for addr, blk in hits:
        c = _make_candidate(chain, addr, blk)
        if not store.candidate_seen(c.key()):
            store.mark_candidate_seen(c.key())
            store.save_candidate(c)
            out.append(c)
    return out


def scan_all_enabled(block_window: int = 20_000, chunk_size: int = 2_000) -> List[Candidate]:
    """
    Scan all enabled chains.
    """
    out: List[Candidate] = []
    for ccfg in enabled_chains():
        out.extend(scan_recent(ccfg.name, block_window=block_window, chunk_size=chunk_size))
    return out
