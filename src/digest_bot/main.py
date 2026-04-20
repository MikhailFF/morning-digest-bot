from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .config import load_config
from .fetchers import (
    AI_RSS_SOURCES,
    CRYPTO_RSS_SOURCES,
    FINANCE_RSS_SOURCES,
    enrich_single_stock_news,
    fetch_brent_quote,
    fetch_crypto_quotes,
    fetch_eur_rub_quote,
    fetch_openclaw_release,
    fetch_rss_news,
    fetch_rss_news_with_fallback,
    fetch_sp500_quote,
    fetch_usd_rub_quote,
    select_quote_of_day,
    select_crypto_focus_news,
    split_finance_news,
)
from .formatters import build_daily_prompt, build_daily_translation_prompt, build_openclaw_prompt, compact_payload, fallback_daily_message, fallback_openclaw_message
from .llm import render_with_llm, translate_daily_content
from .models import NewsItem, OpenClawRelease, QuoteSnapshot
from .storage import append_fallback_log, ensure_state_dir, read_json, write_json
from .telegram import TelegramSendResult, send_telegram_message
from .utils import normalize_title, sha256_json

SUSPICIOUS_LLM_PHRASES = (
    "not financial advice",
    "insert current price here",
    "based on the provided data",
    "i cannot",
    "i can't",
    "as an ai",
    "financial advisor",
)


def _load_daily_fixture(path: str) -> tuple[list[NewsItem], list[NewsItem], list[NewsItem], list[NewsItem], dict[str, QuoteSnapshot], str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    finance_items = [NewsItem(**item) for item in payload["finance_items"]]
    single_stock_items = [NewsItem(**item) for item in payload.get("single_stock_items", [])]
    crypto_items = [NewsItem(**item) for item in payload.get("crypto_items", [])]
    ai_items = [NewsItem(**item) for item in payload["ai_items"]]
    quotes = {key: QuoteSnapshot(**value) for key, value in payload["quotes"].items()}
    return finance_items, single_stock_items, crypto_items, ai_items, quotes, payload["quote_of_day"]


def _load_release_fixture(path: str) -> OpenClawRelease:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return OpenClawRelease(**payload)


def _delivery_config_error(dry_run: bool, config) -> str:
    if dry_run:
        return ""
    if not config.telegram_enabled:
        return "Telegram delivery is disabled. Set TELEGRAM_ENABLED=true for live runs."
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return "Telegram delivery is enabled but TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing."
    return ""


def _validate_daily_message(message: str) -> tuple[bool, str]:
    stripped = message.strip()
    if not stripped:
        return False, "LLM returned an empty message."

    lowered = stripped.casefold()
    for phrase in SUSPICIOUS_LLM_PHRASES:
        if phrase in lowered:
            return False, f"LLM output contains suspicious phrase: {phrase!r}."

    # Ignore the known HTML tags we emit in the deterministic formatter
    # (bold headers, links, italic author line, and collapsible blockquotes for
    # the quote of the day and per-item summaries).
    sanitized = re.sub(
        r"</?(?:b|i|a|blockquote)(?:\s+[^>]*)?>", "", stripped, flags=re.IGNORECASE
    )
    if "<" in sanitized or ">" in sanitized:
        return False, "LLM output contains HTML-like markup."

    section_numbers = [int(match.group(1)) for match in re.finditer(r"(?m)^(\d+)\)", stripped)]
    if len(section_numbers) < 4 or len(section_numbers) > 6 or section_numbers != list(range(1, len(section_numbers) + 1)):
        return False, "LLM output is missing required sections or section numbering is invalid."

    if len([line for line in stripped.splitlines() if line.strip()]) < 8:
        return False, "LLM output is too short for a full digest."

    return True, ""


def _build_daily_message(
    config,
    finance_items: list[NewsItem],
    single_stock_items: list[NewsItem],
    crypto_items: list[NewsItem],
    ai_items: list[NewsItem],
    quotes: dict[str, QuoteSnapshot],
    quote_of_day: str,
    now_local: datetime,
) -> str:
    translated_finance_titles: list[str] | None = None
    translated_stock_focus_titles: list[str] | None = None
    translated_crypto_titles: list[str] | None = None
    translated_ai_titles: list[str] | None = None
    translated_finance_summaries: list[str] | None = None
    translated_stock_focus_summaries: list[str] | None = None
    translated_crypto_summaries: list[str] | None = None
    translated_ai_summaries: list[str] | None = None
    translated_quote_of_day: str | None = None

    translation_payload = translate_daily_content(
        config,
        build_daily_translation_prompt(finance_items, single_stock_items, crypto_items, ai_items, quote_of_day),
    )
    if translation_payload:
        def _extract_list(key: str, expected_count: int) -> list[str] | None:
            raw = translation_payload.get(key)
            if isinstance(raw, list) and len(raw) == expected_count:
                return [str(item).strip() for item in raw]
            return None

        expected_finance_count = min(len(finance_items), 5)
        expected_stock_focus_count = min(len(single_stock_items), 3)
        expected_crypto_count = min(len(crypto_items), 3)
        expected_ai_count = min(len(ai_items), 3)

        translated_finance_titles = _extract_list("finance_titles", expected_finance_count)
        translated_stock_focus_titles = _extract_list("stock_focus_titles", expected_stock_focus_count)
        translated_crypto_titles = _extract_list("crypto_titles", expected_crypto_count)
        translated_ai_titles = _extract_list("ai_titles", expected_ai_count)
        translated_finance_summaries = _extract_list("finance_summaries", expected_finance_count)
        translated_stock_focus_summaries = _extract_list("stock_focus_summaries", expected_stock_focus_count)
        translated_crypto_summaries = _extract_list("crypto_summaries", expected_crypto_count)
        translated_ai_summaries = _extract_list("ai_summaries", expected_ai_count)

        quote_payload = translation_payload.get("quote_of_day")
        if isinstance(quote_payload, str) and quote_payload.strip():
            translated_quote_of_day = quote_payload.strip()

    return fallback_daily_message(
        finance_items,
        single_stock_items,
        crypto_items,
        ai_items,
        quotes,
        quote_of_day,
        now_local,
        translated_finance_titles=translated_finance_titles,
        translated_stock_focus_titles=translated_stock_focus_titles,
        translated_crypto_titles=translated_crypto_titles,
        translated_ai_titles=translated_ai_titles,
        translated_finance_summaries=translated_finance_summaries,
        translated_stock_focus_summaries=translated_stock_focus_summaries,
        translated_crypto_summaries=translated_crypto_summaries,
        translated_ai_summaries=translated_ai_summaries,
        translated_quote_of_day=translated_quote_of_day,
    )


def _log_send_failure(config, name: str, send_result: TelegramSendResult, message: str) -> str:
    log_path = append_fallback_log(
        config.state_dir,
        name,
        f"reason: {send_result.error or 'unknown'}\n\n{message}",
    )
    return str(log_path)


def run_daily(dry_run: bool, fixture_path: str | None, force_send: bool = False) -> int:
    config = load_config()
    ensure_state_dir(config.state_dir)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(config.tzinfo)
    delivery_error = _delivery_config_error(dry_run, config)
    if delivery_error:
        print(delivery_error)
        return 1

    if fixture_path:
        finance_items, single_stock_items, crypto_items, ai_items, quotes, quote_of_day = _load_daily_fixture(fixture_path)
    else:
        finance_candidates = fetch_rss_news(FINANCE_RSS_SOURCES, now_utc, limit=18)
        # Crypto pool prefers dedicated crypto feeds but still looks at general
        # finance feeds for policy/regulation cross-coverage.
        crypto_candidates = fetch_rss_news(
            [*CRYPTO_RSS_SOURCES, *FINANCE_RSS_SOURCES], now_utc, limit=40
        )
        crypto_items = select_crypto_focus_news(crypto_candidates)
        crypto_urls = {item.url for item in crypto_items}
        crypto_titles = {normalize_title(item.title) for item in crypto_items}
        finance_candidates = [
            item
            for item in finance_candidates
            if item.url not in crypto_urls and normalize_title(item.title) not in crypto_titles
        ]
        finance_items, single_stock_items = split_finance_news(finance_candidates)
        single_stock_items = enrich_single_stock_news(single_stock_items)
        # AI feeds often publish less than daily; expand window until we have
        # at least 3 fresh items, capped at 72h.
        ai_items = fetch_rss_news_with_fallback(
            AI_RSS_SOURCES, now_utc, limit=8, min_items=3, fallback_hours=(24, 48, 72)
        )
        quotes = fetch_crypto_quotes()
        quotes["BRENT"] = fetch_brent_quote()
        quotes["USDRUB"] = fetch_usd_rub_quote()
        quotes["EURRUB"] = fetch_eur_rub_quote()
        quotes["SPX"] = fetch_sp500_quote()
        quote_of_day = select_quote_of_day(config.quotes_file, now_local.strftime("%Y-%m-%d"))

    payload = compact_payload(finance_items, single_stock_items, crypto_items, ai_items, quotes, quote_of_day)
    digest_hash = sha256_json(payload)
    digest_state_path = config.state_dir / "daily_digest_state.json"
    state = read_json(digest_state_path)
    if not force_send and state.get("last_date") == now_local.strftime("%Y-%m-%d"):
        print("Daily digest already sent today; skipping duplicate send.")
        return 0

    message = _build_daily_message(config, finance_items, single_stock_items, crypto_items, ai_items, quotes, quote_of_day, now_local)

    if dry_run:
        print(message)
        return 0

    send_result = send_telegram_message(config, message)
    if send_result.ok:
        write_json(
            digest_state_path,
            {
                "last_date": now_local.strftime("%Y-%m-%d"),
                "last_digest_hash": digest_hash,
                "last_sent_at": now_utc.isoformat().replace("+00:00", "Z"),
            },
        )
        print("Daily digest sent.")
        return 0

    log_path = _log_send_failure(config, "daily_digest_failed", send_result, message)
    print(f"Telegram send failed; message saved to {log_path}")
    return 1


def run_weekly_openclaw(dry_run: bool, fixture_path: str | None) -> int:
    config = load_config()
    ensure_state_dir(config.state_dir)
    delivery_error = _delivery_config_error(dry_run, config)
    if delivery_error:
        print(delivery_error)
        return 1

    release = _load_release_fixture(fixture_path) if fixture_path else fetch_openclaw_release(config.openclaw_repo)
    if release is None:
        print("Could not fetch OpenClaw release.")
        return 1

    state_path = config.state_dir / "openclaw_release_state.json"
    state = read_json(state_path)
    previous_seen_version = str(state.get("last_seen_version", ""))

    if not dry_run and previous_seen_version == release.version:
        print("No new OpenClaw release.")
        return 0

    message = render_with_llm(config, build_openclaw_prompt(release, previous_seen_version))
    if not message:
        message = fallback_openclaw_message(release)

    if dry_run:
        print(message)
        return 0

    send_result = send_telegram_message(config, message)
    if send_result.ok:
        write_json(
            state_path,
            {
                "last_seen_version": release.version,
                "last_checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "release_url": release.url,
            },
        )
        print("OpenClaw update sent.")
        return 0

    log_path = _log_send_failure(config, "openclaw_failed", send_result, message)
    print(f"Telegram send failed; message saved to {log_path}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Morning digest bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daily = subparsers.add_parser("daily", help="Run daily digest")
    daily.add_argument("--dry-run", action="store_true")
    daily.add_argument("--fixture", help="Load digest payload from local JSON fixture")
    daily.add_argument("--force", action="store_true", help="Bypass daily duplicate protection for manual sends")

    weekly = subparsers.add_parser("weekly-openclaw", help="Run weekly OpenClaw release digest")
    weekly.add_argument("--dry-run", action="store_true")
    weekly.add_argument("--fixture", help="Load OpenClaw release payload from local JSON fixture")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "daily":
        return run_daily(dry_run=args.dry_run, fixture_path=args.fixture, force_send=args.force)
    if args.command == "weekly-openclaw":
        return run_weekly_openclaw(dry_run=args.dry_run, fixture_path=args.fixture)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
