from __future__ import annotations

from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from digest_bot.formatters import fallback_daily_message
from digest_bot.models import NewsItem, QuoteSnapshot


class FormatterTests(unittest.TestCase):
    def test_fallback_daily_message_contains_sections(self) -> None:
        finance = [
            NewsItem(
                title="Rates stay high",
                source="Reuters",
                published_at="2026-04-14T06:00:00Z",
                url="https://example.com/a",
                summary="Summary",
            )
        ]
        ai = [
            NewsItem(
                title="New AI model ships",
                source="The Verge AI",
                published_at="2026-04-14T05:00:00Z",
                url="https://example.com/b",
                summary="Summary",
            )
        ]
        quotes = {
            "BTC": QuoteSnapshot(symbol="BTC", label="BTC", price=80000.0, change_24h=1.5, suffix="USD"),
            "ETH": QuoteSnapshot(symbol="ETH", label="ETH", price=4000.0, change_24h=-0.5, suffix="USD"),
            "SOL": QuoteSnapshot(symbol="SOL", label="SOL", price=180.0, change_24h=3.2, suffix="USD"),
            "SPX": QuoteSnapshot(symbol="SPX", label="S&P 500", price=5100.0, change_24h=0.4, suffix="USD"),
        }

        message = fallback_daily_message(
            finance_items=finance,
            ai_items=ai,
            quotes=quotes,
            quote_of_day="Price is what you pay.",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )
        self.assertIn("1) Финансы и экономика", message)
        self.assertIn("2) ИИ", message)
        self.assertIn("3) Котировки", message)
        self.assertIn("4) Цитата дня", message)


if __name__ == "__main__":
    unittest.main()
