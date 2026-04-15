from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import AssetSpec


DEFAULT_QUOTE_ASSETS = (
    "BTC|coingecko|bitcoin|BTC|USD;"
    "ETH|coingecko|ethereum|ETH|USD;"
    "SOL|coingecko|solana|SOL|USD;"
    "SPX|yahoo|^GSPC|S&P 500|USD"
)


def _load_dotenv(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_quote_assets(raw: str) -> list[AssetSpec]:
    assets: list[AssetSpec] = []
    for chunk in raw.split(";"):
        item = chunk.strip()
        if not item:
            continue
        parts = [part.strip() for part in item.split("|")]
        if len(parts) != 5:
            continue
        key, provider, instrument, label, suffix = parts
        if not key or provider not in {"coingecko", "yahoo"} or not instrument:
            continue
        assets.append(
            AssetSpec(
                key=key.upper(),
                provider=provider,
                instrument=instrument,
                label=label or key.upper(),
                suffix=suffix or "",
            )
        )
    return assets


@dataclass(frozen=True)
class AppConfig:
    timezone: str
    openai_enabled: bool
    openai_api_key: str
    openai_api_base: str
    openai_model: str
    telegram_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    state_dir: Path
    openclaw_repo: str
    quotes_file: Path
    quote_assets: list[AssetSpec]
    openai_max_output_tokens: int

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_config() -> AppConfig:
    root = Path.cwd()
    _load_dotenv(root)
    state_dir = Path(os.getenv("STATE_DIR", "./state"))
    if not state_dir.is_absolute():
        state_dir = (root / state_dir).resolve()

    quotes_file = root / "data" / "quotes.txt"
    quote_assets = _parse_quote_assets(os.getenv("QUOTE_ASSETS", DEFAULT_QUOTE_ASSETS))
    if not quote_assets:
        quote_assets = _parse_quote_assets(DEFAULT_QUOTE_ASSETS)

    return AppConfig(
        timezone=os.getenv("DIGEST_TIMEZONE", "Europe/Moscow"),
        openai_enabled=_env_bool("OPENAI_ENABLED", False),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_max_output_tokens=_env_int("OPENAI_MAX_OUTPUT_TOKENS", 350),
        telegram_enabled=_env_bool("TELEGRAM_ENABLED", False),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        state_dir=state_dir,
        openclaw_repo=os.getenv("OPENCLAW_REPO", "openclaw/openclaw"),
        quotes_file=quotes_file,
        quote_assets=quote_assets,
    )
