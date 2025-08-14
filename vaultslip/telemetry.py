# vaultslip/telemetry.py
from __future__ import annotations
import json, requests
from typing import Any, Dict, Optional
from .config import settings

def send_telegram(text: str, disable_webpage_preview: bool = True) -> bool:
    token, chat_id = settings.BOT_TOKEN, settings.CHAT_ID
    if not token or not chat_id: return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": disable_webpage_preview, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=8)
        return bool(r.ok)
    except Exception:
        return False

def send_metrics(event: str, data: Optional[Dict[str, Any]] = None) -> None:
    hook = settings.METRICS_WEBHOOK_URL
    if not hook: return
    try:
        payload = {"event": event, "data": data or {}}
        requests.post(hook, data=json.dumps(payload), timeout=5, headers={"Content-Type": "application/json"})
    except Exception:
        pass
