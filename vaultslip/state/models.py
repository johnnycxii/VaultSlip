# vaultslip/state/models.py
"""
Typed data models used across VaultSlip.
These are intentionally minimal and serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


# A raw candidate source discovered by scanners (function/event/bytecode pattern).
@dataclass(slots=True)
class Candidate:
    chain: str                     # e.g., "ETH", "POLY"
    contract: str                  # 0x-prefixed address
    origin: str                    # "bytecode" | "event" | "repo"
    pattern: str                   # label, e.g. "open_claim", "refundOverpayment"
    discovered_block: Optional[int] = None
    notes: Optional[str] = None

    def key(self) -> str:
        # Unique-ish identity for de-duplication
        return f"{self.chain}:{self.contract}:{self.pattern}"

    def to_dict(self) -> Dict:
        return asdict(self)


# Verdict after simulation + safety checks (pre-claim decision).
@dataclass(slots=True)
class Verdict:
    candidate_key: str
    eligible: bool
    reason: str                    # human-readable summary
    est_payout_token: str          # e.g., "ETH", "WETH", "USDC"
    est_payout_amount: float       # numeric units of the token
    est_payout_usd: float          # convenience field after fx conversion
    est_gas_usd: float
    profit_usd: float
    safety_passed: bool
    history_verified: bool
    timestamp: int                 # unix seconds

    def to_dict(self) -> Dict:
        return asdict(self)


# A source is a verified contract we continue to watch over time.
@dataclass(slots=True)
class Source:
    chain: str
    contract: str
    first_seen_block: Optional[int]
    last_seen_block: Optional[int]
    patterns: List[str]            # e.g., ["open_claim", "external_withdraw"]
    verified: bool                 # passed all checks at least once
    last_verdict: Optional[Verdict] = None

    def id(self) -> str:
        return f"{self.chain}:{self.contract}"

    def to_dict(self) -> Dict:
        d = asdict(self)
        if self.last_verdict:
            d["last_verdict"] = self.last_verdict.to_dict()
        return d


# Result of an attempted claim (dry-run or live).
@dataclass(slots=True)
class ClaimResult:
    chain: str
    contract: str
    tx_sent: bool
    tx_hash: Optional[str]         # None in dry-run
    sweep_tx_hash: Optional[str]   # if POST_CLAIM_SWEEP true and sent
    value_token: str
    value_amount: float
    value_usd: float
    gas_usd: float
    profit_usd: float
    ok: bool
    message: str                   # reason or summary
    timestamp: int

    def to_dict(self) -> Dict:
        return asdict(self)
