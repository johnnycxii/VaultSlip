# vaultslip/constants.py
from pathlib import Path

# ---- Discovery patterns (extended later via /data/signatures.json) ----
DEFAULT_FUNCTION_SIGS = ["claim", "withdraw", "refundOverpayment", "collect", "redeem"]

DEFAULT_EVENT_SIGS = [
    "RefundProcessed(address,uint256)",
    "UnclaimedRewards(address,uint256)",
    "Payout(address,uint256)",
]

# High-level bytecode/semantic labels (matched in discovery/safety)
BYTECODE_PATTERN_LABELS = ["open_claim", "external_withdraw", "escrow_overflow"]

# ---- Honeypot / trap denylist (checked in safety/honeypot_rules.py) ----
OPCODE_DENY_KEYWORDS = {"DELEGATECALL", "SELFDESTRUCT", "CREATE2"}
ABI_DENY_FUNCTIONS = {"approve(address,uint256)"}

# ---- Default thresholds (overridable by .env) ----
DEFAULT_THRESHOLDS = {
    "MIN_PROFIT_USD": 8.0,
    "GAS_MAX_GWEI": 35.0,
    "CLAIM_INTERVAL_SECONDS": 45,
    "WALLET_ROTATION_EVERY": 8,
    "HONEYPOT_STRICT": True,
    "REQUIRE_HISTORY": True,
    "MAX_PARALLEL_CLAIMS": 4,
}

# ---- Logging destinations ----
LOG_DIR = Path("logs")
LOG_FILES = {
    "app": LOG_DIR / "app.log",
    "claims": LOG_DIR / "claims.log",
    "security": LOG_DIR / "security.log",
}
