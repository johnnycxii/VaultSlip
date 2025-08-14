# vaultslip/executor/scheduler.py
"""
VaultSlip scheduler:
- Jittered intervals between claim attempts
- Wallet rotation counter honoring settings.WALLET_ROTATION_EVERY
- Per-chain rate-limit via MAX_PARALLEL_CLAIMS (coarse token bucket)
- Stateless API + a small in-memory state for the current process
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, Iterator, Optional, Tuple

from vaultslip.config import settings
from vaultslip.wallet.keyring import get_keyring


@dataclass(slots=True, frozen=True)
class Tick:
    """A single scheduling decision."""
    chain: str
    wallet_index: int
    sleep_ms_next: int
    reason: str


class _RateLimiter:
    """
    Very simple token bucket per chain: at each tick we allow up to MAX_PARALLEL_CLAIMS
    "in flight". Since our current loop is synchronous, this acts as a coarse rate limiter.
    """
    def __init__(self, capacity: int):
        self.capacity = max(1, int(capacity))
        self.inflight: Dict[str, int] = { }

    def can_proceed(self, chain: str) -> bool:
        return self.inflight.get(chain, 0) < self.capacity

    def mark_start(self, chain: str) -> None:
        self.inflight[chain] = self.inflight.get(chain, 0) + 1

    def mark_done(self, chain: str) -> None:
        cur = self.inflight.get(chain, 0)
        self.inflight[chain] = max(0, cur - 1)


class Scheduler:
    """
    Provides jittered ticks with rotating wallet indices.
    Usage:
        sch = Scheduler(chains=['ETH','POLY'])
        for tick in sch.loop():
            # do work for tick.chain with wallet index tick.wallet_index
            time.sleep(tick.sleep_ms_next/1000)
    """
    def __init__(self, chains: list[str]):
        if not chains:
            raise ValueError("Scheduler requires at least one chain.")
        self.chains = [c.upper() for c in chains]
        self.kr = get_keyring()
        self.rotate_every = max(1, int(settings.WALLET_ROTATION_EVERY))
        self.interval_ms = max(50, int(settings.CLAIM_INTERVAL_SECONDS) * 1000)
        self.rl = _RateLimiter(settings.MAX_PARALLEL_CLAIMS)

        # runtime counters
        self._tick_count = 0
        self._wallet_index = 0

    def _next_wallet_index(self) -> int:
        if (self._tick_count % self.rotate_every) == 0 and self._tick_count > 0:
            self._wallet_index = (self._wallet_index + 1) % self.kr.size
        return self._wallet_index

    def _jitter_ms(self) -> int:
        # ±15% jitter
        base = self.interval_ms
        delta = int(base * 0.15)
        return base + random.randint(-delta, +delta)

    def loop(self) -> Iterator[Tick]:
        """
        Infinite generator of scheduling ticks. Caller should break on external signals.
        """
        while True:
            self._tick_count += 1

            # Round-robin chains (simple)
            chain = self.chains[(self._tick_count - 1) % len(self.chains)]

            # Rate-limit check
            if not self.rl.can_proceed(chain):
                # back off a bit and retry
                yield Tick(chain=chain, wallet_index=self._next_wallet_index(), sleep_ms_next=250, reason="rate_limited")
                continue

            # Assign wallet
            wi = self._next_wallet_index()

            # Compute next sleep with jitter
            sleep_ms = self._jitter_ms()

            yield Tick(chain=chain, wallet_index=wi, sleep_ms_next=sleep_ms, reason="ok")

    # Hooks for marking lifecycle (optional for future async usage)
    def mark_start(self, chain: str) -> None:
        self.rl.mark_start(chain.upper())

    def mark_done(self, chain: str) -> None:
        self.rl.mark_done(chain.upper())
