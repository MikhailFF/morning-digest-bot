from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AppConfig


@dataclass(frozen=True)
class TelegramSendResult:
    ok: bool
    error: str = ""


def send_telegram_message(config: AppConfig, message: str) -> TelegramSendResult:
    if not config.telegram_enabled:
        return TelegramSendResult(ok=False, error="TELEGRAM_ENABLED is false.")
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return TelegramSendResult(ok=False, error="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
    if not message.strip():
        return TelegramSendResult(ok=False, error="Message is empty.")
    if len(message) > 4096:
        return TelegramSendResult(ok=False, error="Message exceeds Telegram 4096-character limit.")

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML",
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
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        return TelegramSendResult(ok=False, error=f"HTTP {exc.code}: {details}")
    except URLError as exc:
        return TelegramSendResult(ok=False, error=f"Network error: {exc.reason}")
    except Exception as exc:
        return TelegramSendResult(ok=False, error=str(exc))

    if response_payload.get("ok") is True:
        return TelegramSendResult(ok=True)
    return TelegramSendResult(ok=False, error=str(response_payload.get("description") or "Telegram API returned ok=false."))
