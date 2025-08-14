# vaultslip/discovery/signatures.py
"""
Canonical signature set for discovery.
- Merges .env (settings.*) with /data/signatures.json (if present)
- Provides deduped, normalized lists of function names, event sigs, and pattern labels
- This is DATA-driven: adding to /data/signatures.json extends discovery WITHOUT code changes
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, TypedDict

from vaultslip.config import settings
from vaultslip.constants import DEFAULT_FUNCTION_SIGS, DEFAULT_EVENT_SIGS, BYTECODE_PATTERN_LABELS


SIG_FILE = Path("data") / "signatures.json"


class Signatures(TypedDict):
    function_names: List[str]   # e.g. ["claim","withdraw","refundOverpayment"]
    event_signatures: List[str] # e.g. ["RefundProcessed(address,uint256)"]
    bytecode_patterns: List[str]  # e.g. ["open_claim","external_withdraw","escrow_overflow"]


def _load_file() -> Dict:
    if SIG_FILE.exists():
        try:
            return json.loads(SIG_FILE.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {}
    return {}


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        k = it.strip()
        if not k:
            continue
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _normalize_func_names(items: List[str]) -> List[str]:
    # lowercase, strip spaces
    return _dedupe_keep_order([i.strip() for i in items])


def _normalize_event_sigs(items: List[str]) -> List[str]:
    # Keep exact case/signature text, just strip spaces
    return _dedupe_keep_order([i.strip() for i in items])


def _normalize_patterns(items: List[str]) -> List[str]:
    # labels become lowercase to be consistent
    return _dedupe_keep_order([i.strip().lower() for i in items])


def load_signatures() -> Signatures:
    """
    Merge order (priority from high to low):
      1) /data/signatures.json (user-extended)
      2) .env values (settings.DISCOVERY_* lists)
      3) built-in defaults from constants.py
    """
    file_data = _load_file()

    file_funcs = file_data.get("function_names", [])
    file_events = file_data.get("event_signatures", [])
    file_patterns = file_data.get("bytecode_patterns", [])

    env_funcs = settings.DISCOVERY_FUNCTION_SIGS or []
    env_events = settings.DISCOVERY_EVENT_SIGS or []
    env_patterns = settings.BYTECODE_PATTERNS or []

    funcs = _normalize_func_names(file_funcs + env_funcs + DEFAULT_FUNCTION_SIGS)
    events = _normalize_event_sigs(file_events + env_events + DEFAULT_EVENT_SIGS)
    patterns = _normalize_patterns(file_patterns + env_patterns + BYTECODE_PATTERN_LABELS)

    return Signatures(
        function_names=funcs,
        event_signatures=events,
        bytecode_patterns=patterns,
    )


# Convenience single-shot export for modules that just need lists
SIGS = load_signatures()
FUNCTION_NAMES: List[str] = SIGS["function_names"]
EVENT_SIGNATURES: List[str] = SIGS["event_signatures"]
BYTECODE_PATTERNS: List[str] = SIGS["bytecode_patterns"]
