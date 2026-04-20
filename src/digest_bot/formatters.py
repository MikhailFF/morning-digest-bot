from __future__ import annotations

from html import escape
import json
from datetime import datetime

from .models import NewsItem, OpenClawRelease, QuoteSnapshot
from .utils import truncate_to_sentences

SUMMARY_MAX_SENTENCES = 3
SUMMARY_MAX_CHARS = 320

QUOTE_DISPLAY_ORDER = (
    ("BTC", "BTC"),
    ("ETH", "ETH"),
    ("SOL", "SOL"),
    ("BRENT", "Brent"),
    ("USDRUB", "USD/RUB"),
    ("EURRUB", "EUR/RUB"),
    ("SPX", "S&P 500"),
)

FINANCE_SECTION_TITLE = "🪙 Финансы и экономика"
STOCK_FOCUS_SECTION_TITLE = "💸 Акции в фокусе"
CRYPTO_FOCUS_SECTION_TITLE = "💎 Крипта в фокусе"
AI_SECTION_TITLE = "🤖 ИИ"
QUOTES_SECTION_TITLE = "📈 Котировки"
QUOTE_OF_DAY_SECTION_TITLE = "👨🏻‍🎓 Цитата дня"


def compact_payload(
    finance_items: list[NewsItem],
    single_stock_items: list[NewsItem],
    crypto_items: list[NewsItem],
    ai_items: list[NewsItem],
    quotes: dict[str, QuoteSnapshot],
    quote_of_day: str,
) -> dict:
    return {
        "finance_items": [item.__dict__ for item in finance_items],
        "single_stock_items": [item.__dict__ for item in single_stock_items],
        "crypto_items": [item.__dict__ for item in crypto_items],
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
        f"1) {FINANCE_SECTION_TITLE}\n"
        f"2) {STOCK_FOCUS_SECTION_TITLE} (only if single_stock_items is not empty)\n"
        f"3) {CRYPTO_FOCUS_SECTION_TITLE} (only if crypto_items is not empty)\n"
        f"4) {AI_SECTION_TITLE}\n"
        f"5) {QUOTES_SECTION_TITLE}\n"
        f"6) {QUOTE_OF_DAY_SECTION_TITLE}\n"
        "Each news item must be one short line in the format: translated title (source) - full URL.\n"
        "If a section has fewer items than requested, include only what exists.\n"
        "Do not use markdown tables.\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _prep_summary(item: NewsItem) -> str:
    return truncate_to_sentences(
        item.summary, max_sentences=SUMMARY_MAX_SENTENCES, max_chars=SUMMARY_MAX_CHARS
    )


def build_daily_translation_prompt(
    finance_items: list[NewsItem],
    single_stock_items: list[NewsItem],
    crypto_items: list[NewsItem],
    ai_items: list[NewsItem],
    quote_of_day: str,
) -> str:
    payload = {
        "finance_titles": [item.title for item in finance_items[:5]],
        "finance_summaries": [_prep_summary(item) for item in finance_items[:5]],
        "stock_focus_titles": [item.title for item in single_stock_items[:3]],
        "stock_focus_summaries": [_prep_summary(item) for item in single_stock_items[:3]],
        "crypto_titles": [item.title for item in crypto_items[:3]],
        "crypto_summaries": [_prep_summary(item) for item in crypto_items[:3]],
        "ai_titles": [item.title for item in ai_items[:3]],
        "ai_summaries": [_prep_summary(item) for item in ai_items[:3]],
        "quote_of_day": quote_of_day,
    }
    return (
        "Translate the supplied English text into natural Russian for a Telegram digest.\n"
        "Return strict JSON only, without markdown fences or explanations.\n"
        'Use exactly this shape: {"finance_titles":["..."],"finance_summaries":["..."],'
        '"stock_focus_titles":["..."],"stock_focus_summaries":["..."],'
        '"crypto_titles":["..."],"crypto_summaries":["..."],'
        '"ai_titles":["..."],"ai_summaries":["..."],"quote_of_day":"..."}.\n'
        "Preserve the number of entries in each array; align each *_summaries[i] with *_titles[i].\n"
        "Each summary must be natural Russian, at most 3 sentences and at most 320 characters, conveying the core fact only.\n"
        "If a source summary is empty, return an empty string at the same index.\n"
        "If quote_of_day contains '|' between the quote text and author, preserve that delimiter in the translated quote_of_day.\n"
        "Do not translate brand names or publication names unless there is a common Russian form.\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def fallback_daily_message(
    finance_items: list[NewsItem],
    single_stock_items: list[NewsItem],
    crypto_items: list[NewsItem],
    ai_items: list[NewsItem],
    quotes: dict[str, QuoteSnapshot],
    quote_of_day: str,
    now_local: datetime,
    *,
    translated_finance_titles: list[str] | None = None,
    translated_stock_focus_titles: list[str] | None = None,
    translated_crypto_titles: list[str] | None = None,
    translated_ai_titles: list[str] | None = None,
    translated_finance_summaries: list[str] | None = None,
    translated_stock_focus_summaries: list[str] | None = None,
    translated_crypto_summaries: list[str] | None = None,
    translated_ai_summaries: list[str] | None = None,
    translated_quote_of_day: str | None = None,
) -> str:
    def fmt_quote_of_day(text: str) -> list[str]:
        raw = text.strip()
        quote_text, separator, author = raw.partition("|")
        lines = [f"<blockquote>{escape(quote_text.strip())}</blockquote>"]
        if separator and author.strip():
            lines.append(f"<i>- {escape(author.strip())}</i>")
        return lines

    def pick_summary(
        item: NewsItem, index: int, translated: list[str] | None
    ) -> str:
        if translated and index < len(translated):
            candidate = (translated[index] or "").strip()
            if candidate:
                return truncate_to_sentences(
                    candidate, SUMMARY_MAX_SENTENCES, SUMMARY_MAX_CHARS
                )
        return truncate_to_sentences(
            item.summary or "", SUMMARY_MAX_SENTENCES, SUMMARY_MAX_CHARS
        )

    def fmt_summary_block(summary: str) -> str | None:
        if not summary.strip():
            return None
        return f"<blockquote expandable>{escape(summary.strip())}</blockquote>"

    def fmt_news_item(index: int, item: NewsItem, translated_title: str | None) -> str:
        title = escape((translated_title or item.title).strip())
        source = escape(item.source)
        url = escape(item.url)
        return f'{index}. {title} (<a href="{url}">{source}</a>)'

    def fmt_stock_focus_item(index: int, item: NewsItem, translated_title: str | None) -> str:
        title = escape((translated_title or item.title).strip())
        suffix = ""
        if item.price_change_24h is not None:
            suffix = f" ({item.price_change_24h:+.2f}% за сутки)"
        source = escape(item.source)
        url = escape(item.url)
        return f'{index}. {title}{suffix} (<a href="{url}">{source}</a>)'

    def fmt_quote(symbol: str) -> str:
        if symbol not in quotes:
            for quote_symbol, label in QUOTE_DISPLAY_ORDER:
                if quote_symbol == symbol:
                    return f"- {escape(label)}: н/д"
            return f"- {escape(symbol)}: н/д"
        quote = quotes[symbol]
        if quote.price is None:
            return f"- {escape(quote.label)}: н/д"
        if quote.change_24h is None:
            return f"- {escape(quote.label)}: {quote.price:.2f} {escape(quote.suffix)}"
        return f"- {escape(quote.label)}: {quote.price:.2f} {escape(quote.suffix)} ({quote.change_24h:+.2f}%)"

    parts = [f"<b>Дайджест на {now_local.strftime('%d.%m.%Y %H:%M')}</b>"]
    parts.append("")
    section_number = 1

    parts.append(f"<b>{section_number}) {FINANCE_SECTION_TITLE}</b>")
    if finance_items:
        for index, item in enumerate(finance_items[:5], start=1):
            translated_title = None
            if translated_finance_titles and index <= len(translated_finance_titles):
                translated_title = translated_finance_titles[index - 1]
            parts.append(fmt_news_item(index, item, translated_title))
            summary_block = fmt_summary_block(
                pick_summary(item, index - 1, translated_finance_summaries)
            )
            if summary_block:
                parts.append(summary_block)
    else:
        parts.append("Нет достаточно свежих новостей.")
    section_number += 1

    if single_stock_items:
        parts.append("")
        parts.append(f"<b>{section_number}) {STOCK_FOCUS_SECTION_TITLE}</b>")
        for index, item in enumerate(single_stock_items[:3], start=1):
            translated_title = None
            if translated_stock_focus_titles and index <= len(translated_stock_focus_titles):
                translated_title = translated_stock_focus_titles[index - 1]
            parts.append(fmt_stock_focus_item(index, item, translated_title))
            summary_block = fmt_summary_block(
                pick_summary(item, index - 1, translated_stock_focus_summaries)
            )
            if summary_block:
                parts.append(summary_block)
        section_number += 1

    parts.append("")
    if crypto_items:
        parts.append(f"<b>{section_number}) {CRYPTO_FOCUS_SECTION_TITLE}</b>")
        for index, item in enumerate(crypto_items[:3], start=1):
            translated_title = None
            if translated_crypto_titles and index <= len(translated_crypto_titles):
                translated_title = translated_crypto_titles[index - 1]
            parts.append(fmt_news_item(index, item, translated_title))
            summary_block = fmt_summary_block(
                pick_summary(item, index - 1, translated_crypto_summaries)
            )
            if summary_block:
                parts.append(summary_block)
        section_number += 1
        parts.append("")

    parts.append(f"<b>{section_number}) {AI_SECTION_TITLE}</b>")
    if ai_items:
        for index, item in enumerate(ai_items[:3], start=1):
            translated_title = None
            if translated_ai_titles and index <= len(translated_ai_titles):
                translated_title = translated_ai_titles[index - 1]
            parts.append(fmt_news_item(index, item, translated_title))
            summary_block = fmt_summary_block(
                pick_summary(item, index - 1, translated_ai_summaries)
            )
            if summary_block:
                parts.append(summary_block)
    else:
        parts.append("Нет достаточно свежих новостей.")
    section_number += 1

    parts.append("")
    parts.append(f"<b>{section_number}) {QUOTES_SECTION_TITLE}</b>")
    for symbol, _label in QUOTE_DISPLAY_ORDER:
        parts.append(fmt_quote(symbol))
    section_number += 1

    parts.append("")
    parts.append(f"<b>{section_number}) {QUOTE_OF_DAY_SECTION_TITLE}</b>")
    parts.extend(fmt_quote_of_day(translated_quote_of_day or quote_of_day))
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
