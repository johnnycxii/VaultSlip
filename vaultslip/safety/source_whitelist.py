# vaultslip/safety/source_whitelist.py
"""
Allowlist / blocklist enforcement for VaultSlip.
- Reads /data/allowlist_sources.json and /data/blocklists.json
- Provides is_allowed(chain, contract) and is_blocked(chain, contract)
- Supports pattern-level allow (optional)
- Safe if files are empty or missing
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from web3 import Web3

ALLOWLIST_FILE = Path("data") / "allowlist_sources.json"  # format: [{"chain":"ETH","contract":"0x..","patterns":["open_claim"]}, ...]
BLOCKLIST_FILE = Path("data") / "blocklists.json"         # format: {"contracts":{"ETH":["0x..","0x.."], "POLY":[...]}, "patterns":["foo","bar"]}


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw or "{}")
    except Exception:
        return None


def _norm_addr(addr: str) -> str:
    try:
        return Web3.to_checksum_address(addr)
    except Exception:
        return addr


class Lists:
    def __init__(self):
        self.allowed_by_chain: Dict[str, Set[str]] = {}
        self.allowed_patterns_by_addr: Dict[Tuple[str, str], Set[str]] = {}
        self.blocked_by_chain: Dict[str, Set[str]] = {}
        self.blocked_patterns: Set[str] = set()

    @classmethod
    def load(cls) -> "Lists":
        inst = cls()

        # Load allowlist
        al = _read_json(ALLOWLIST_FILE)
        if isinstance(al, list):
            for item in al:
                try:
                    chain = str(item.get("chain", "")).upper()
                    addr = _norm_addr(item.get("contract", ""))
                    if not chain or not addr:
                        continue
                    inst.allowed_by_chain.setdefault(chain, set()).add(addr)
                    pats = item.get("patterns")
                    if isinstance(pats, list) and pats:
                        inst.allowed_patterns_by_addr[(chain, addr)] = {str(p).strip().lower() for p in pats if str(p).strip()}
                except Exception:
                    continue

        # Load blocklists
        bl = _read_json(BLOCKLIST_FILE) or {}
        contracts = bl.get("contracts", {})
        if isinstance(contracts, dict):
            for chain, addrs in contracts.items():
                if not isinstance(addrs, list):
                    continue
                c = str(chain).upper()
                inst.blocked_by_chain.setdefault(c, set()).update(_norm_addr(a) for a in addrs if a)

        pats = bl.get("patterns", [])
        if isinstance(pats, list):
            inst.blocked_patterns = {str(p).strip().lower() for p in pats if str(p).strip()}

        return inst


_LISTS = Lists.load()


def refresh() -> None:
    """Reload lists from disk (call if files change)."""
    global _LISTS
    _LISTS = Lists.load()


def is_blocked(chain: str, contract: str, pattern: Optional[str] = None) -> bool:
    c = chain.upper()
    a = _norm_addr(contract)
    if a in _LISTS.blocked_by_chain.get(c, set()):
        return True
    if pattern and str(pattern).strip().lower() in _LISTS.blocked_patterns:
        return True
    return False


def is_allowed(chain: str, contract: str, pattern: Optional[str] = None) -> bool:
    """
    If allowlist is empty, we treat it as "allow all unless blocked".
    If allowlist has entries, we require (chain, contract) to be present.
    If patterns are specified for an allowed address, the pattern must match.
    """
    c = chain.upper()
    a = _norm_addr(contract)

    # If no allow entries at all -> permissive unless blocked
    has_any_allow = any(_LISTS.allowed_by_chain.values())
    if not has_any_allow:
        # allow if not blocked
        if is_blocked(c, a, pattern):
            return False
        return True

    # Strict: require address in allowlist
    if a not in _LISTS.allowed_by_chain.get(c, set()):
        return False

    # If patterns are specified for this address, the pattern must match
    if pattern:
        pats = _LISTS.allowed_patterns_by_addr.get((c, a))
        if isinstance(pats, set) and pats:
            return str(pattern).strip().lower() in pats

    return True
