# vaultslip/discovery/intake.py
"""
Candidate intake & de-duplication for VaultSlip.
- Merge candidates from multiple discovery channels
- Persist only NEW items into the store
- Return the list of newly accepted candidates (for downstream verification)
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from vaultslip.state.models import Candidate
from vaultslip.state import store


def _accept(c: Candidate) -> bool:
    """Return True if this candidate was not seen before and is now persisted."""
    key = c.key()
    if store.candidate_seen(key):
        return False
    store.mark_candidate_seen(key)
    store.save_candidate(c)
    return True


def intake_candidates(batches: Sequence[Iterable[Candidate]], max_new: int | None = None) -> List[Candidate]:
    """
    Ingests multiple batches of Candidate objects (e.g., from bytecode, events, repo).
    De-duplicates with the persistent store.
    Returns the list of newly-accepted candidates (order preserved by batch order).
    If max_new is set, stop after that many new candidates are accepted.
    """
    accepted: List[Candidate] = []
    count_new = 0

    for batch in batches:
        for c in batch:
            if _accept(c):
                accepted.append(c)
                count_new += 1
                if max_new is not None and count_new >= max_new:
                    return accepted
    return accepted


def intake_single_batch(batch: Iterable[Candidate], max_new: int | None = None) -> List[Candidate]:
    """Convenience wrapper for one batch."""
    return intake_candidates([batch], max_new=max_new)
