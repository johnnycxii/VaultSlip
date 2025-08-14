# vaultslip/safety/gas_sentry.py
"""
Gas & profitability guardrails for VaultSlip.
- Enforce min profit (USD) after gas
- Enforce gas price ceilings
- Provide a single decision function: gas_profit_ok(...)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from vaultslip.config import settings


@dataclass(slots=True)
class GasProfitVerdict:
    ok: bool
    reason: str
    gas_price_gwei: Optional[float]
    gas_limit: Optional[int]
    est_gas_usd: Optional[float]
    est_payout_usd: Optional[float]
    est_profit_usd: Optional[float]
    thresholds: dict


def _wei_to_gwei(wei: int | None) -> Optional[float]:
    if wei is None:
        return None
    return float(wei) / 1e9


def _gas_cost_usd(gas_limit: Optional[int], gas_price_wei: Optional[int], eth_usd: float) -> Optional[float]:
    if gas_limit is None or gas_price_wei is None:
        return None
    # gas_cost = gas_limit * gas_price (in ETH) * ETHUSD
    return (gas_limit * (gas_price_wei / 1e18)) * eth_usd


def gas_profit_ok(
    *,
    est_payout_usd: Optional[float],
    gas_limit: Optional[int],
    gas_price_wei: Optional[int],
    eth_usd: float,
    min_profit_usd: Optional[float] = None,
    gas_max_gwei: Optional[float] = None,
    gas_safety_multiplier: Optional[float] = None,
) -> GasProfitVerdict:
    """
    Returns a GasProfitVerdict deciding whether to proceed.
    - If any required value is missing, defaults conservative (reject).
    - gas_max_gwei and min_profit_usd fallback to settings if not provided.
    """
    min_profit = settings.MIN_PROFIT_USD if min_profit_usd is None else float(min_profit_usd)
    max_gwei = settings.GAS_MAX_GWEI if gas_max_gwei is None else float(gas_max_gwei)
    mult = settings.GAS_SAFETY_MULTIPLIER if gas_safety_multiplier is None else float(gas_safety_multiplier)

    gwei = _wei_to_gwei(gas_price_wei)
    if gwei is None or gwei > max_gwei * mult:
        return GasProfitVerdict(
            ok=False,
            reason="gas_price_exceeds_ceiling",
            gas_price_gwei=gwei,
            gas_limit=gas_limit,
            est_gas_usd=None,
            est_payout_usd=est_payout_usd,
            est_profit_usd=None,
            thresholds={"GAS_MAX_GWEI": max_gwei, "GAS_SAFETY_MULTIPLIER": mult, "MIN_PROFIT_USD": min_profit},
        )

    if gas_limit is None or est_payout_usd is None:
        return GasProfitVerdict(
            ok=False,
            reason="missing_estimates",
            gas_price_gwei=gwei,
            gas_limit=gas_limit,
            est_gas_usd=None,
            est_payout_usd=est_payout_usd,
            est_profit_usd=None,
            thresholds={"GAS_MAX_GWEI": max_gwei, "GAS_SAFETY_MULTIPLIER": mult, "MIN_PROFIT_USD": min_profit},
        )

    gas_usd = _gas_cost_usd(gas_limit=int(gas_limit * mult), gas_price_wei=gas_price_wei, eth_usd=eth_usd)
    if gas_usd is None:
        return GasProfitVerdict(
            ok=False,
            reason="gas_cost_unavailable",
            gas_price_gwei=gwei,
            gas_limit=gas_limit,
            est_gas_usd=None,
            est_payout_usd=est_payout_usd,
            est_profit_usd=None,
            thresholds={"GAS_MAX_GWEI": max_gwei, "GAS_SAFETY_MULTIPLIER": mult, "MIN_PROFIT_USD": min_profit},
        )

    profit_usd = float(est_payout_usd) - float(gas_usd)
    if profit_usd < min_profit:
        return GasProfitVerdict(
            ok=False,
            reason="profit_below_minimum",
            gas_price_gwei=gwei,
            gas_limit=gas_limit,
            est_gas_usd=gas_usd,
            est_payout_usd=est_payout_usd,
            est_profit_usd=profit_usd,
            thresholds={"GAS_MAX_GWEI": max_gwei, "GAS_SAFETY_MULTIPLIER": mult, "MIN_PROFIT_USD": min_profit},
        )

    return GasProfitVerdict(
        ok=True,
        reason="gas_profit_ok",
        gas_price_gwei=gwei,
        gas_limit=gas_limit,
        est_gas_usd=gas_usd,
        est_payout_usd=est_payout_usd,
        est_profit_usd=profit_usd,
        thresholds={"GAS_MAX_GWEI": max_gwei, "GAS_SAFETY_MULTIPLIER": mult, "MIN_PROFIT_USD": min_profit},
    )
