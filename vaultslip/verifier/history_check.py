# vaultslip/verifier/history_check.py
"""
History verification for VaultSlip.
- Heuristic: consider a contract safer if multiple distinct third-party callers
  have successfully interacted with it in the recent past.
- Implementation:
  * Scan logs for the contract over a lookback window (chunked)
  * For each log's txHash, fetch receipt and read tx "from" + status
  * Count distinct successful callers
- Conservative: returns False if RPC fails or no logs found.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from web3 import Web3

from vaultslip.chains.registry import get_chain
from vaultslip.chains.evm_client import get_client
from vaultslip.config import settings


@dataclass(slots=True)
class HistoryVerdict:
    ok: bool
    reason: str
    distinct_callers: int
    window_blocks: int


def _chunk_ranges(latest: int, window: int, chunk: int) -> List[Tuple[int, int]]:
    start = max(0, latest - window + 1)
    out: List[Tuple[int, int]] = []
    cur = start
    while cur <= latest:
        end = min(cur + chunk - 1, latest)
        out.append((cur, end))
        cur = end + 1
    return out


def _fetch_logs(w3: Web3, address: str, start: int, end: int) -> List[Dict]:
    try:
        return w3.eth.get_logs({"fromBlock": start, "toBlock": end, "address": address})
    except Exception:
        return []


def _caller_from_receipt(w3: Web3, tx_hash: str) -> Optional[str]:
    try:
        rcpt = w3.eth.get_transaction_receipt(tx_hash)
        if rcpt is None or getattr(rcpt, "status", 0) != 1:
            return None
        # Need the tx to get the sender ("from")
        tx = w3.eth.get_transaction(tx_hash)
        return Web3.to_checksum_address(tx["from"])
    except Exception:
        return None


def distinct_success_callers(chain: str, contract: str, lookback_blocks: Optional[int] = None,
                              chunk_size: int = 2_000, max_receipts: int = 1_000) -> int:
    """
    Returns the count of distinct successful caller addresses over the lookback window.
    Limits receipt processing to max_receipts for performance.
    """
    ccfg = get_chain(chain)
    if not ccfg:
        return 0
    w3 = get_client(ccfg)

    try:
        latest = int(w3.eth.block_number)
    except Exception:
        return 0

    window = int(lookback_blocks or settings.HISTORY_LOOKBACK_BLOCKS)
    addr = Web3.to_checksum_address(contract)

    ranges = _chunk_ranges(latest, window, chunk_size)
    callers: Set[str] = set()
    processed = 0

    for (start, end) in ranges:
        logs = _fetch_logs(w3, addr, start, end)
        for lg in logs:
            if processed >= max_receipts:
                break
            tx_hash = lg["transactionHash"].hex()
            caller = _caller_from_receipt(w3, tx_hash)
            if caller:
                callers.add(caller)
            processed += 1
        if processed >= max_receipts:
            break

    return len(callers)


def verify_history(chain: str, contract: str, min_distinct_callers: int = 3,
                   lookback_blocks: Optional[int] = None) -> HistoryVerdict:
    """
    Returns HistoryVerdict indicating whether this contract shows a healthy pattern of
    third-party successful interactions recently.
    """
    count = distinct_success_callers(chain, contract, lookback_blocks=lookback_blocks)
    window = int(lookback_blocks or settings.HISTORY_LOOKBACK_BLOCKS)

    if count >= int(min_distinct_callers):
        return HistoryVerdict(ok=True, reason="distinct_callers_threshold_met",
                              distinct_callers=count, window_blocks=window)
    if count == 0:
        return HistoryVerdict(ok=False, reason="no_successful_logs_found",
                              distinct_callers=0, window_blocks=window)
    return HistoryVerdict(ok=False, reason="insufficient_distinct_callers",
                          distinct_callers=count, window_blocks=window)
