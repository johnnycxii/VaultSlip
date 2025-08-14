# vaultslip/logging_utils.py
from __future__ import annotations
import json, logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict
from .constants import LOG_FILES, LOG_DIR

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k not in {"args","asctime","created","exc_info","exc_text","filename","funcName","levelname",
                         "levelno","lineno","module","msecs","message","msg","name","pathname","process",
                         "processName","relativeCreated","stack_info","thread","threadName"}:
                payload[k] = v
        return json.dumps(payload, ensure_ascii=False)

def _ensure_dirs() -> None:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

def _make_handler(path: Path) -> RotatingFileHandler:
    h = RotatingFileHandler(str(path), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(JsonFormatter()); h.setLevel(logging.INFO); return h

def get_logger(name: str = "vaultslip") -> logging.Logger:
    _ensure_dirs()
    lg = logging.getLogger(name)
    if getattr(lg, "_vaultslip_configured", False): return lg
    lg.setLevel(logging.INFO)
    lg.addHandler(_make_handler(LOG_FILES["app"]))
    ch = logging.StreamHandler(); ch.setLevel(logging.INFO); ch.setFormatter(JsonFormatter()); lg.addHandler(ch)
    setattr(lg, "_vaultslip_configured", True)
    return lg

def get_claims_logger() -> logging.Logger:
    _ensure_dirs()
    lg = logging.getLogger("vaultslip.claims")
    if getattr(lg, "_vaultslip_configured", False): return lg
    lg.setLevel(logging.INFO); lg.addHandler(_make_handler(LOG_FILES["claims"])); lg.addHandler(logging.StreamHandler())
    setattr(lg, "_vaultslip_configured", True); return lg

def get_security_logger() -> logging.Logger:
    _ensure_dirs()
    lg = logging.getLogger("vaultslip.security")
    if getattr(lg, "_vaultslip_configured", False): return lg
    lg.setLevel(logging.INFO); lg.addHandler(_make_handler(LOG_FILES["security"])); lg.addHandler(logging.StreamHandler())
    setattr(lg, "_vaultslip_configured", True); return lg
