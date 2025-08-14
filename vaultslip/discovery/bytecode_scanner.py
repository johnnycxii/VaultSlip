# vaultslip/discovery/bytecode_scanner.py
"""
Bytecode scanner (read-only) for VaultSlip.
- Fetches contract bytecode via RPC
- Applies conservative, explainable heuristics to flag potential residual-payout sources
- Emits Candidate objects (no writes, no approvals)
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from web3 import Web3

from vaultslip.chains.evm_client import get_client
from vaultslip.chains.registry import get_chain
from vaultslip.discovery.signatures import BYTECODE_PATTERNS
from vaultslip.state.models import Candidate
from vaultslip.state import store


# ---- Helpers ----------------------------------------------------------------

def _get_code_bytes(w3: Web3, address: str) -> bytes:
    code_hex = w3.eth.get_code(Web3.to_checksum_address(address)).hex()
    # strip "0x"
    return bytes.fromhex(code_hex[2:]) if code_hex and code_hex.startswith("0x") else b""


def _contains_opcode(code: bytes, opcode_hex: str) -> bool:
    """
    Cheap check for an opcode byte presence, e.g. CALL=0xf1, DELEGATECALL=0xf4, SELFDESTRUCT=0xff, CREATE2=0xf5.
    This is a heuristic; not a full disassembly.
    """
    try:
        target = bytes.fromhex(opcode_hex.lower().replace("0x", ""))
        return target in code
    except Exception:
        return False


def _score_patterns(code: bytes) -> List[str]:
    """
    Heuristic pattern labelling.
    We keep this conservative to avoid noise; it's a starting point for discovery.
    """
    labels: List[str] = []

    # Rule of thumb: sizable contracts only (skip proxies with near-empty code)
    if len(code) < 600:  # ~ minimal non-trivial runtime
        return labels

    has_call = _contains_opcode(code, "0xf1")
    has_delegatecall = _contains_opcode(code, "0xf4")
    has_selfdestruct = _contains_opcode(code, "0xff")
    has_create2 = _contains_opcode(code, "0xf5")

    # "open_claim": external balance-moving call path but without delegatecall/selfdestruct/create2 in the same runtime
    if has_call and not (has_delegatecall or has_selfdestruct or has_create2):
        labels.append("open_claim")

    # "external_withdraw": presence of CALL plus RETURN (0xf3) suggests controlled external transfers
    if has_call and _contains_opcode(code, "0xf3"):
        labels.append("external_withdraw")

    # "escrow_overflow": larger bytecode with multiple CALLs is a weak indicator of custodial flows
    if has_call and code.count(bytes.fromhex("f1")) >= 3:
        labels.append("escrow_overflow")

    # Keep only labels we officially expose (defensive)
    labels = [lbl for lbl in labels if lbl in BYTECODE_PATTERNS]
    # Dedup while preserving order
    seen = set()
    out: List[str] = []
    for l in labels:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out


def _make_candidate(chain: str, address: str, pattern: str, blk: Optional[int]) -> Candidate:
    return Candidate(
        chain=chain,
        contract=Web3.to_checksum_address(address),
        origin="bytecode",
        pattern=pattern,
        discovered_block=blk,
        notes=None,
    )


# ---- Public API --------------------------------------------------------------

def scan_single(chain: str, address: str) -> List[Candidate]:
    """
    Scan one contract address on a given chain.
    Returns 0..N Candidates (typically 0..3) depending on matched patterns.
    """
    ccfg = get_chain(chain)
    if not ccfg:
        return []
    w3 = get_client(ccfg)
    try:
        code = _get_code_bytes(w3, address)
    except Exception:
        return []

    labels = _score_patterns(code)
    if not labels:
        return []

    # Use current block for reference; failure to fetch shouldn't break candidates
    try:
        blk = int(w3.eth.block_number)
    except Exception:
        blk = None

    cands = [_make_candidate(chain, address, lbl, blk) for lbl in labels]
    return cands


def scan_batch(chain: str, addresses: Iterable[str]) -> List[Candidate]:
    """
    Scan a batch of addresses on one chain, skipping those we've already seen.
    De-duplicates via store.candidate_seen().
    """
    out: List[Candidate] = []
    for addr in addresses:
        # De-dupe by address+pattern key after we compute labels
        cands = scan_single(chain, addr)
        for c in cands:
            if not store.candidate_seen(c.key()):
                store.mark_candidate_seen(c.key())
                store.save_candidate(c)
                out.append(c)
    return out
