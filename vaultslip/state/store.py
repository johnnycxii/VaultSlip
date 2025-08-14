# vaultslip/state/store.py
"""
Lightweight persistent KV store for VaultSlip using sqlitedict.
- De-duplicates Candidates
- Persists Sources and last Verdicts
- Simple append log for ClaimResults (optional)
"""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sqlitedict import SqliteDict

from vaultslip.state.models import Candidate, Source, Verdict, ClaimResult


_DB_PATH = Path("data") / "vaultslip_state.sqlite"
_LOCK = threading.RLock()


@contextmanager
def _open(db_path: Path = _DB_PATH):
    # autocommit=True -> writes are flushed on setitem
    with _LOCK:  # coarse-grained safety
        db = SqliteDict(str(db_path), autocommit=True)
        try:
            yield db
        finally:
            db.close()


# ---- Keys / Buckets ---------------------------------------------------------

_BUCKET_CANDIDATES = "candidates"   # key: candidate.key() -> Candidate.to_dict()
_BUCKET_SOURCES    = "sources"      # key: source.id() -> Source.to_dict()
_BUCKET_VERDICTS   = "verdicts"     # key: candidate.key() -> Verdict.to_dict()
_BUCKET_RESULTS    = "claim_results"  # append-only: idx -> ClaimResult.to_dict()
_BUCKET_SEEN       = "seen_keys"    # key: candidate.key() -> 1


def _bucket_key(bucket: str, key: str) -> str:
    return f"{bucket}:{key}"


# ---- Candidate de-dup & storage --------------------------------------------

def candidate_seen(key: str) -> bool:
    with _open() as db:
        return _bucket_key(_BUCKET_SEEN, key) in db


def mark_candidate_seen(key: str) -> None:
    with _open() as db:
        db[_bucket_key(_BUCKET_SEEN, key)] = 1


def save_candidate(c: Candidate) -> None:
    with _open() as db:
        db[_bucket_key(_BUCKET_CANDIDATES, c.key())] = c.to_dict()


def get_candidate(key: str) -> Optional[Candidate]:
    with _open() as db:
        raw = db.get(_bucket_key(_BUCKET_CANDIDATES, key))
    if not raw:
        return None
    return Candidate(**raw)


def iter_candidates() -> Iterable[Candidate]:
    with _open() as db:
        for k in db.keys():
            if k.startswith(_BUCKET_CANDIDATES + ":"):
                raw = db[k]
                if raw:
                    yield Candidate(**raw)


# ---- Sources ----------------------------------------------------------------

def save_source(src: Source) -> None:
    with _open() as db:
        db[_bucket_key(_BUCKET_SOURCES, src.id())] = src.to_dict()


def get_source(source_id: str) -> Optional[Source]:
    with _open() as db:
        raw = db.get(_bucket_key(_BUCKET_SOURCES, source_id))
    if not raw:
        return None
    # last_verdict is already dict shape compatible with dataclass init
    lv = raw.get("last_verdict")
    if lv:
        raw["last_verdict"] = Verdict(**lv)
    return Source(**raw)


def iter_sources() -> Iterable[Source]:
    with _open() as db:
        for k in db.keys():
            if k.startswith(_BUCKET_SOURCES + ":"):
                raw = db[k]
                if raw:
                    lv = raw.get("last_verdict")
                    if lv:
                        raw["last_verdict"] = Verdict(**lv)
                    yield Source(**raw)


# ---- Verdicts ---------------------------------------------------------------

def save_verdict(v: Verdict) -> None:
    with _open() as db:
        db[_bucket_key(_BUCKET_VERDICTS, v.candidate_key)] = v.to_dict()


def get_verdict(candidate_key: str) -> Optional[Verdict]:
    with _open() as db:
        raw = db.get(_bucket_key(_BUCKET_VERDICTS, candidate_key))
    if not raw:
        return None
    return Verdict(**raw)


# ---- Claim results (append-only) -------------------------------------------

def append_claim_result(res: ClaimResult) -> int:
    """
    Appends a claim result and returns its numeric index.
    """
    with _open() as db:
        # Find next index cheaply (store a counter)
        counter_key = "_meta:results_counter"
        idx = int(db.get(counter_key, -1)) + 1
        db[counter_key] = idx
        db[_bucket_key(_BUCKET_RESULTS, str(idx))] = res.to_dict()
        return idx


def iter_claim_results(start: int = 0) -> Iterable[Tuple[int, ClaimResult]]:
    with _open() as db:
        # iterate by numeric index in order
        counter = int(db.get("_meta:results_counter", -1))
        for idx in range(start, counter + 1):
            raw = db.get(_bucket_key(_BUCKET_RESULTS, str(idx)))
            if raw:
                yield idx, ClaimResult(**raw)


# ---- Utilities --------------------------------------------------------------

def reset_store(confirm: bool = False) -> None:
    """
    DANGER: wipes the entire state database if confirm=True.
    """
    if not confirm:
        raise RuntimeError("Refusing to reset store without confirm=True")
    if _DB_PATH.exists():
        _DB_PATH.unlink()
