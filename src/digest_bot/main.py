from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from .config import load_config
from .fetchers import (
    AI_RSS_SOURCES,
    FINANCE_RSS_SOURCES,
    fetch_crypto_quotes,
    fetch_openclaw_release,
    fetch_rss_news,
    fetch_sp500_quote,
    select_quote_of_day,
)
from .formatters import build_daily_prompt, build_openclaw_prompt, compact_payload, fallback_daily_message, fallback_openclaw_message
from .llm import render_with_llm
from .models import NewsItem, OpenClawRelease, QuoteSnapshot
from .storage import append_fallback_log, ensure_state_dir, read_json, write_json
from .telegram import send_telegram_message
from .utils import sha256_json


def _load_daily_fixture(path: str) -> tuple[list[NewsItem], list[NewsItem], dict[str, QuoteSnapshot], str]:
    payload = json.loads(open(path, encoding="utf-8").read())
    finance_items = [NewsItem(**item) for item in payload["finance_items"]]
    ai_items = [NewsItem(**item) for item in payload["ai_items"]]
    quotes = {key: QuoteSnapshot(**value) for key, value in payload["quotes"].items()}
    return finance_items, ai_items, quotes, payload["quote_of_day"]


def _load_release_fixture(path: str) -> OpenClawRelease:
    payload = json.loads(open(path, encoding="utf-8").read())
    return OpenClawRelease(**payload)


def run_daily(dry_run: bool, fixture_path: str | None) -> int:
    config = load_config()
    ensure_state_dir(config.state_dir)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(config.tzinfo)

    if fixture_path:
        finance_items, ai_items, quotes, quote_of_day = _load_daily_fixture(fixture_path)
    else:
        finance_items = fetch_rss_news(FINANCE_RSS_SOURCES, now_utc, limit=12)
        ai_items = fetch_rss_news(AI_RSS_SOURCES, now_utc, limit=8)
        quotes = fetch_crypto_quotes()
        quotes["SPX"] = fetch_sp500_quote()
        quote_of_day = select_quote_of_day(config.quotes_file, now_local.strftime("%Y-%m-%d"))

    payload = compact_payload(finance_items, ai_items, quotes, quote_of_day)
    digest_hash = sha256_json(payload)
    digest_state_path = config.state_dir / "daily_digest_state.json"
    state = read_json(digest_state_path)

    message = render_with_llm(config, build_daily_prompt(payload))
    if not message:
        message = fallback_daily_message(finance_items, ai_items, quotes, quote_of_day, now_local)

    if dry_run:
        print(message)
        return 0

    if state.get("last_digest_hash") == digest_hash and state.get("last_date") == now_local.strftime("%Y-%m-%d"):
        print("Digest unchanged for today; skipping duplicate send.")
        return 0

    sent = send_telegram_message(config, message)
    if sent:
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

    log_path = append_fallback_log(config.state_dir, "daily_digest_failed", message)
    print(f"Telegram send failed; message saved to {log_path}")
    return 1


def run_weekly_openclaw(dry_run: bool, fixture_path: str | None) -> int:
    config = load_config()
    ensure_state_dir(config.state_dir)
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

    sent = send_telegram_message(config, message)
    if sent:
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

    log_path = append_fallback_log(config.state_dir, "openclaw_failed", message)
    print(f"Telegram send failed; message saved to {log_path}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Morning digest bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daily = subparsers.add_parser("daily", help="Run daily digest")
    daily.add_argument("--dry-run", action="store_true")
    daily.add_argument("--fixture", help="Load digest payload from local JSON fixture")

    weekly = subparsers.add_parser("weekly-openclaw", help="Run weekly OpenClaw release digest")
    weekly.add_argument("--dry-run", action="store_true")
    weekly.add_argument("--fixture", help="Load OpenClaw release payload from local JSON fixture")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "daily":
        return run_daily(dry_run=args.dry_run, fixture_path=args.fixture)
    if args.command == "weekly-openclaw":
        return run_weekly_openclaw(dry_run=args.dry_run, fixture_path=args.fixture)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
