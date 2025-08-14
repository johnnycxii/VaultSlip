# vaultslip/discovery/repo_watcher.py
"""
Curated repo watcher (local only).
- Reads data/repos.json (your curated list of known-good contracts)
- Emits Candidate objects tagged origin="repo"
- Safe no-op if file missing/invalid
Expected JSON (array of objects):
[
  {"chain":"ETH","contract":"0xABC...","pattern":"open_claim","notes":"my source"},
  {"chain":"POLY","contract":"0xDEF...","pattern":"external_withdraw"}
]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from web3 import Web3

from vaultslip.state.models import Candidate

REPO_FILE = Path("data") / "repos.json"


def _load() -> list:
    if not REPO_FILE.exists():
        return []
    try:
        raw = REPO_FILE.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def scan_curated(limit: int | None = None) -> List[Candidate]:
    out: List[Candidate] = []
    for item in _load():
        try:
            chain = str(item.get("chain", "")).upper()
            addr = Web3.to_checksum_address(str(item.get("contract", "")))
            pattern = str(item.get("pattern", "open_claim")).strip().lower()
            notes = item.get("notes")
            c = Candidate(chain=chain, contract=addr, origin="repo", pattern=pattern, notes=notes)
            out.append(c)
            if limit is not None and len(out) >= limit:
                break
        except Exception:
            continue
    return out
