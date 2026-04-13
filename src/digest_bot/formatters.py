from __future__ import annotations

import json
from datetime import datetime

from .models import NewsItem, OpenClawRelease, QuoteSnapshot


def compact_payload(finance_items: list[NewsItem], ai_items: list[NewsItem], quotes: dict[str, QuoteSnapshot], quote_of_day: str) -> dict:
    return {
        "finance_items": [item.__dict__ for item in finance_items],
        "ai_items": [item.__dict__ for item in ai_items],
        "quotes": {key: value.__dict__ for key, value in quotes.items()},
        "quote_of_day": quote_of_day,
    }


def build_daily_prompt(payload: dict) -> str:
    return (
        "You are formatting a Telegram market digest.\n"
        "Use only the provided data.\n"
        "Do not invent facts.\n"
        "Output in Russian.\n"
        "Keep it compact.\n"
        "Structure exactly as:\n"
        "1) 5 главных новостей финансов и экономики\n"
        "2) 3 новости ИИ\n"
        "3) Котировки\n"
        "4) Цитата дня\n"
        "Each news item must be one short line with source in parentheses.\n"
        "If a section has fewer items than requested, include only what exists.\n"
        "Do not use markdown tables.\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def fallback_daily_message(finance_items: list[NewsItem], ai_items: list[NewsItem], quotes: dict[str, QuoteSnapshot], quote_of_day: str, now_local: datetime) -> str:
    def fmt_quote(symbol: str) -> str:
        quote = quotes[symbol]
        if quote.price is None:
            return f"- {quote.label}: н/д"
        if quote.change_24h is None:
            return f"- {quote.label}: {quote.price:.2f} {quote.suffix}"
        return f"- {quote.label}: {quote.price:.2f} {quote.suffix} ({quote.change_24h:+.2f}%)"

    parts = [f"Дайджест на {now_local.strftime('%d.%m.%Y %H:%M')}"]
    parts.append("")
    parts.append("1) Финансы и экономика")
    if finance_items:
        for index, item in enumerate(finance_items[:5], start=1):
            parts.append(f"{index}. {item.title} ({item.source})")
    else:
        parts.append("Нет достаточно свежих новостей.")

    parts.append("")
    parts.append("2) ИИ")
    if ai_items:
        for index, item in enumerate(ai_items[:3], start=1):
            parts.append(f"{index}. {item.title} ({item.source})")
    else:
        parts.append("Нет достаточно свежих новостей.")

    parts.append("")
    parts.append("3) Котировки")
    for symbol in ("BTC", "ETH", "SOL", "SPX"):
        parts.append(fmt_quote(symbol))

    parts.append("")
    parts.append("4) Цитата дня")
    parts.append(quote_of_day)
    return "\n".join(parts)


def build_openclaw_prompt(release: OpenClawRelease, previous_seen_version: str) -> str:
    return (
        "You are formatting a short Russian Telegram note about a new OpenClaw release.\n"
        "Use only the supplied release data.\n"
        "Explain briefly what changed and then give a recommendation in one of these forms: "
        "'ставить', 'можно подождать', 'не ставить сейчас'.\n"
        "Do not over-explain.\n\n"
        f"PREVIOUS_VERSION: {previous_seen_version or 'unknown'}\n"
        f"DATA:\n{json.dumps(release.__dict__, ensure_ascii=False, indent=2)}"
    )


def fallback_openclaw_message(release: OpenClawRelease) -> str:
    return (
        f"Обновление OpenClaw: {release.title} ({release.version})\n"
        f"Дата: {release.published_at or 'н/д'}\n"
        f"Что изменилось: {release.notes[:500] or 'Нет описания релиза.'}\n"
        "Оценка: можно подождать и проверить changelog перед установкой."
    )
