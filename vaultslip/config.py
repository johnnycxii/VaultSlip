# vaultslip/config.py
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from dotenv import load_dotenv
from .constants import DEFAULT_THRESHOLDS

load_dotenv(override=False)

def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or str(val).strip() == ""):
        raise RuntimeError(f"Missing required env key: {name}")
    return val if val is not None else ""

def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default))
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try: return float(raw) if raw is not None else float(default)
    except Exception: return float(default)

def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try: return int(raw) if raw is not None else int(default)
    except Exception: return int(default)

def _split_csv(name: str, default_csv: str) -> List[str]:
    raw = os.getenv(name, default_csv)
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    return [p.upper() for p in parts]

@dataclass(frozen=True)
class ChainConfig:
    name: str
    rpc_uri: str
    chain_id: Optional[int] = None

@dataclass
class Settings:
    # App
    APP_ENV: str = field(default_factory=lambda: _get_env("APP_ENV", "prod"))
    LOG_LEVEL: str = field(default_factory=lambda: _get_env("LOG_LEVEL", "INFO"))
    RUN_MODE: List[str] = field(default_factory=lambda: _split_csv("RUN_MODE", "discover,watch,claim"))
    # Wallets
    HOT_WALLET_MNEMONIC: str = field(default_factory=lambda: _get_env("HOT_WALLET_MNEMONIC", ""))
    HOT_WALLET_COUNT: int = field(default_factory=lambda: _get_int("HOT_WALLET_COUNT", 12))
    SWEEP_WALLET: str = field(default_factory=lambda: _get_env("SWEEP_WALLET", ""))
    # Telegram
    BOT_TOKEN: str = field(default_factory=lambda: _get_env("BOT_TOKEN", ""))
    CHAT_ID: str = field(default_factory=lambda: _get_env("CHAT_ID", ""))
    # Safety thresholds
    MAX_PARALLEL_CLAIMS: int = field(default_factory=lambda: _get_int("MAX_PARALLEL_CLAIMS", int(DEFAULT_THRESHOLDS["MAX_PARALLEL_CLAIMS"])))
    MIN_PROFIT_USD: float = field(default_factory=lambda: _get_float("MIN_PROFIT_USD", float(DEFAULT_THRESHOLDS["MIN_PROFIT_USD"])))
    GAS_MAX_GWEI: float = field(default_factory=lambda: _get_float("GAS_MAX_GWEI", float(DEFAULT_THRESHOLDS["GAS_MAX_GWEI"])))
    CLAIM_INTERVAL_SECONDS: int = field(default_factory=lambda: _get_int("CLAIM_INTERVAL_SECONDS", int(DEFAULT_THRESHOLDS["CLAIM_INTERVAL_SECONDS"])))
    WALLET_ROTATION_EVERY: int = field(default_factory=lambda: _get_int("WALLET_ROTATION_EVERY", int(DEFAULT_THRESHOLDS["WALLET_ROTATION_EVERY"])))
    HONEYPOT_STRICT: bool = field(default_factory=lambda: _get_bool("HONEYPOT_STRICT", bool(DEFAULT_THRESHOLDS["HONEYPOT_STRICT"])))
    REQUIRE_HISTORY: bool = field(default_factory=lambda: _get_bool("REQUIRE_HISTORY", bool(DEFAULT_THRESHOLDS["REQUIRE_HISTORY"])))
    # Chains
    CHAINS: List[str] = field(default_factory=lambda: _split_csv("CHAINS", "ETH,POLY,CELO"))
    RPCS: Dict[str, str] = field(default_factory=dict)
    # Discovery tuning
    DISCOVERY_FUNCTION_SIGS: List[str] = field(default_factory=lambda: _split_csv("DISCOVERY_FUNCTION_SIGS", "claim,withdraw,refundOverpayment,collect,redeem"))
    DISCOVERY_EVENT_SIGS: List[str] = field(default_factory=lambda: [e for e in _get_env("DISCOVERY_EVENT_SIGS","RefundProcessed(address,uint256);UnclaimedRewards(address,uint256)").split(";") if e.strip()])
    BYTECODE_PATTERNS: List[str] = field(default_factory=lambda: _split_csv("BYTECODE_PATTERNS", "open_claim,external_withdraw,escrow_overflow"))
    HISTORY_LOOKBACK_BLOCKS: int = field(default_factory=lambda: _get_int("HISTORY_LOOKBACK_BLOCKS", 100000))
    # Simulation & gas modeling
    SIMULATION_TIMEOUT_MS: int = field(default_factory=lambda: _get_int("SIMULATION_TIMEOUT_MS", 3000))
    GAS_SAFETY_MULTIPLIER: float = field(default_factory=lambda: _get_float("GAS_SAFETY_MULTIPLIER", 1.15))
    GAS_HISTORICAL_WINDOW_BLOCKS: int = field(default_factory=lambda: _get_int("GAS_HISTORICAL_WINDOW_BLOCKS", 5000))
    # Executor
    SWEEP_TOKEN: str = field(default_factory=lambda: _get_env("SWEEP_TOKEN", "ETH"))
    POST_CLAIM_SWEEP: bool = field(default_factory=lambda: _get_bool("POST_CLAIM_SWEEP", True))
    DELAY_AFTER_CLAIM_MS: int = field(default_factory=lambda: _get_int("DELAY_AFTER_CLAIM_MS", 800))
    # Telemetry
    METRICS_WEBHOOK_URL: str = field(default_factory=lambda: _get_env("METRICS_WEBHOOK_URL", ""))
    METRICS_SAMPLE_RATE: float = field(default_factory=lambda: _get_float("METRICS_SAMPLE_RATE", 0.5))

    def get_chain_rpc(self, chain_name: str) -> Optional[str]:
        key = f"RPC_URI_{chain_name.upper()}"
        return os.getenv(key)

    def load_rpcs(self) -> None:
        self.RPCS = {}
        for c in self.CHAINS:
            uri = self.get_chain_rpc(c)
            if uri:
                self.RPCS[c] = uri

settings = Settings()
settings.load_rpcs()
