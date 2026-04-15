from __future__ import annotations

import json
from typing import Literal
from urllib.request import Request, urlopen

from .config import AppConfig


def send_telegram_message(config: AppConfig, message: str) -> Literal["sent", "disabled", "missing_config", "failed"]:
    if not config.telegram_enabled:
        return "disabled"
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return "missing_config"

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
        return "sent"
    except Exception:
        return "failed"
