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
            "BRENT": QuoteSnapshot(symbol="BRENT", label="Brent", price=88.4, change_24h=-1.2, suffix="USD"),
            "USDRUB": QuoteSnapshot(symbol="USDRUB", label="USD/RUB", price=92.5, change_24h=0.8, suffix="RUB"),
            "EURRUB": QuoteSnapshot(symbol="EURRUB", label="EUR/RUB", price=99.7, change_24h=0.4, suffix="RUB"),
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
        self.assertIn("<b>Дайджест на", message)
        self.assertIn('Rates stay high (<a href="https://example.com/a">Reuters</a>)', message)
        self.assertIn('New AI model ships (<a href="https://example.com/b">The Verge AI</a>)', message)
        self.assertIn("- Brent: 88.40 USD (-1.20%)", message)
        self.assertIn("- USD/RUB: 92.50 RUB (+0.80%)", message)
        self.assertIn("- EUR/RUB: 99.70 RUB (+0.40%)", message)

    def test_fallback_daily_message_escapes_html(self) -> None:
        finance = [
            NewsItem(
                title="Rates <b>stay</b> high",
                source="Reuters & Co",
                published_at="2026-04-14T06:00:00Z",
                url="https://example.com/a",
                summary="Summary",
            )
        ]
        ai = []
        quotes = {
            "BTC": QuoteSnapshot(symbol="BTC", label="BTC", price=80000.0, change_24h=1.5, suffix="USD"),
            "ETH": QuoteSnapshot(symbol="ETH", label="ETH", price=4000.0, change_24h=-0.5, suffix="USD"),
            "SOL": QuoteSnapshot(symbol="SOL", label="SOL", price=180.0, change_24h=3.2, suffix="USD"),
            "BRENT": QuoteSnapshot(symbol="BRENT", label="Brent", price=88.4, change_24h=-1.2, suffix="USD"),
            "USDRUB": QuoteSnapshot(symbol="USDRUB", label="USD/RUB", price=92.5, change_24h=0.8, suffix="RUB"),
            "EURRUB": QuoteSnapshot(symbol="EURRUB", label="EUR/RUB", price=99.7, change_24h=0.4, suffix="RUB"),
            "SPX": QuoteSnapshot(symbol="SPX", label="S&P 500", price=5100.0, change_24h=0.4, suffix="USD"),
        }

        message = fallback_daily_message(
            finance_items=finance,
            ai_items=ai,
            quotes=quotes,
            quote_of_day="Price < Value",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )

        self.assertIn("Rates &lt;b&gt;stay&lt;/b&gt; high", message)
        self.assertIn("Reuters &amp; Co", message)
        self.assertIn("Price &lt; Value", message)
        self.assertNotIn("Price < Value", message)
        self.assertIn('Rates &lt;b&gt;stay&lt;/b&gt; high (<a href="https://example.com/a">Reuters &amp; Co</a>)', message)

    def test_fallback_daily_message_uses_translated_overrides(self) -> None:
        finance = [
            NewsItem(
                title="Bank stock climbs",
                source="Yahoo Finance",
                published_at="2026-04-14T06:00:00Z",
                url="https://example.com/a",
                summary="Summary",
            )
        ]
        ai = []
        quotes = {
            "BTC": QuoteSnapshot(symbol="BTC", label="BTC", price=80000.0, change_24h=1.5, suffix="USD"),
            "ETH": QuoteSnapshot(symbol="ETH", label="ETH", price=4000.0, change_24h=-0.5, suffix="USD"),
            "SOL": QuoteSnapshot(symbol="SOL", label="SOL", price=180.0, change_24h=3.2, suffix="USD"),
            "BRENT": QuoteSnapshot(symbol="BRENT", label="Brent", price=88.4, change_24h=-1.2, suffix="USD"),
            "USDRUB": QuoteSnapshot(symbol="USDRUB", label="USD/RUB", price=92.5, change_24h=0.8, suffix="RUB"),
            "EURRUB": QuoteSnapshot(symbol="EURRUB", label="EUR/RUB", price=99.7, change_24h=0.4, suffix="RUB"),
            "SPX": QuoteSnapshot(symbol="SPX", label="S&P 500", price=5100.0, change_24h=0.4, suffix="USD"),
        }

        message = fallback_daily_message(
            finance_items=finance,
            ai_items=ai,
            quotes=quotes,
            quote_of_day="Well done is better than well said.",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
            translated_finance_titles=["Акции банка растут"],
            translated_quote_of_day="Хорошо сделано лучше, чем хорошо сказано.",
        )

        self.assertIn('Акции банка растут (<a href="https://example.com/a">Yahoo Finance</a>)', message)
        self.assertIn("Хорошо сделано лучше, чем хорошо сказано.", message)


if __name__ == "__main__":
    unittest.main()
