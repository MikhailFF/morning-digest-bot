from __future__ import annotations

from html import escape
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
        "Translate English news titles and the quote of the day into natural Russian.\n"
        "Keep it compact.\n"
        "Do not add disclaimers, caveats, or meta commentary.\n"
        "Do not write phrases like 'not financial advice', 'Insert current price here', or 'based on the provided data'.\n"
        "Do not use HTML tags.\n"
        "Structure exactly as:\n"
        "1) 5 главных новостей финансов и экономики\n"
        "2) 3 новости ИИ\n"
        "3) Котировки\n"
        "4) Цитата дня\n"
        "Each news item must be one short line in the format: translated title (source) - full URL.\n"
        "If a section has fewer items than requested, include only what exists.\n"
        "Do not use markdown tables.\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_daily_translation_prompt(finance_items: list[NewsItem], ai_items: list[NewsItem], quote_of_day: str) -> str:
    payload = {
        "finance_titles": [item.title for item in finance_items[:5]],
        "ai_titles": [item.title for item in ai_items[:3]],
        "quote_of_day": quote_of_day,
    }
    return (
        "Translate the supplied English text into natural Russian for a Telegram digest.\n"
        "Return strict JSON only, without markdown fences or explanations.\n"
        'Use exactly this shape: {"finance_titles":["..."],"ai_titles":["..."],"quote_of_day":"..."}.\n'
        "Preserve the number of titles in each array.\n"
        "Do not translate brand names or publication names unless there is a common Russian form.\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def fallback_daily_message(
    finance_items: list[NewsItem],
    ai_items: list[NewsItem],
    quotes: dict[str, QuoteSnapshot],
    quote_of_day: str,
    now_local: datetime,
    *,
    translated_finance_titles: list[str] | None = None,
    translated_ai_titles: list[str] | None = None,
    translated_quote_of_day: str | None = None,
) -> str:
    def fmt_news_item(index: int, item: NewsItem, translated_title: str | None) -> str:
        title = escape((translated_title or item.title).strip())
        source = escape(item.source)
        url = escape(item.url)
        return f'{index}. {title} (<a href="{url}">{source}</a>)'

    def fmt_quote(symbol: str) -> str:
        quote = quotes[symbol]
        if quote.price is None:
            return f"- {escape(quote.label)}: н/д"
        if quote.change_24h is None:
            return f"- {escape(quote.label)}: {quote.price:.2f} {escape(quote.suffix)}"
        return f"- {escape(quote.label)}: {quote.price:.2f} {escape(quote.suffix)} ({quote.change_24h:+.2f}%)"

    parts = [f"<b>Дайджест на {now_local.strftime('%d.%m.%Y %H:%M')}</b>"]
    parts.append("")
    parts.append("<b>1) Финансы и экономика</b>")
    if finance_items:
        for index, item in enumerate(finance_items[:5], start=1):
            translated_title = None
            if translated_finance_titles and index <= len(translated_finance_titles):
                translated_title = translated_finance_titles[index - 1]
            parts.append(fmt_news_item(index, item, translated_title))
    else:
        parts.append("Нет достаточно свежих новостей.")

    parts.append("")
    parts.append("<b>2) ИИ</b>")
    if ai_items:
        for index, item in enumerate(ai_items[:3], start=1):
            translated_title = None
            if translated_ai_titles and index <= len(translated_ai_titles):
                translated_title = translated_ai_titles[index - 1]
            parts.append(fmt_news_item(index, item, translated_title))
    else:
        parts.append("Нет достаточно свежих новостей.")

    parts.append("")
    parts.append("<b>3) Котировки</b>")
    for symbol in ("BTC", "ETH", "SOL", "SPX"):
        parts.append(fmt_quote(symbol))

    parts.append("")
    parts.append("<b>4) Цитата дня</b>")
    parts.append(escape((translated_quote_of_day or quote_of_day).strip()))
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
