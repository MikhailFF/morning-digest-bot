from __future__ import annotations

from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from digest_bot.formatters import build_daily_translation_prompt, fallback_daily_message
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
        stock_focus = [
            NewsItem(
                title="Allbirds stock surges after AI pivot",
                source="Yahoo Finance",
                published_at="2026-04-14T05:30:00Z",
                url="https://example.com/stock",
                summary="Summary",
                ticker="BIRD",
                price_change_24h=6.2,
            )
        ]
        crypto = [
            NewsItem(
                title="US Senate advances stablecoin bill",
                source="Axios",
                published_at="2026-04-14T05:20:00Z",
                url="https://example.com/crypto",
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
            single_stock_items=stock_focus,
            crypto_items=crypto,
            ai_items=ai,
            quotes=quotes,
            quote_of_day="Price is what you pay.",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )
        self.assertIn("1) Финансы и экономика", message)
        self.assertIn("2) Акции в фокусе", message)
        self.assertIn("3) Крипто в фокусе", message)
        self.assertIn("4) ИИ", message)
        self.assertIn("5) Котировки", message)
        self.assertIn("6) Цитата дня", message)
        self.assertIn("<b>Дайджест на", message)
        self.assertIn('Rates stay high (<a href="https://example.com/a">Reuters</a>)', message)
        self.assertIn('Allbirds stock surges after AI pivot (+6.20% за сутки) (<a href="https://example.com/stock">Yahoo Finance</a>)', message)
        self.assertIn('US Senate advances stablecoin bill (<a href="https://example.com/crypto">Axios</a>)', message)
        self.assertIn('New AI model ships (<a href="https://example.com/b">The Verge AI</a>)', message)
        self.assertIn("- Brent: 88.40 USD (-1.20%)", message)
        self.assertIn("- USD/RUB: 92.50 RUB (+0.80%)", message)
        self.assertIn("- EUR/RUB: 99.70 RUB (+0.40%)", message)

    def test_fallback_daily_message_omits_stock_focus_section_when_empty(self) -> None:
        finance = [
            NewsItem(
                title="Rates stay high",
                source="Reuters",
                published_at="2026-04-14T06:00:00Z",
                url="https://example.com/a",
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
            single_stock_items=[],
            crypto_items=[],
            ai_items=[],
            quotes=quotes,
            quote_of_day="Price is what you pay.",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )

        self.assertNotIn("Акции в фокусе", message)
        self.assertIn("2) ИИ", message)
        self.assertIn("3) Котировки", message)
        self.assertIn("4) Цитата дня", message)

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
            single_stock_items=[],
            crypto_items=[],
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
            single_stock_items=[],
            crypto_items=[],
            ai_items=ai,
            quotes=quotes,
            quote_of_day="Well done is better than well said.",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
            translated_finance_titles=["Акции банка растут"],
            translated_quote_of_day="Хорошо сделано лучше, чем хорошо сказано.",
        )

        self.assertIn('Акции банка растут (<a href="https://example.com/a">Yahoo Finance</a>)', message)
        self.assertIn("Хорошо сделано лучше, чем хорошо сказано.", message)

    def test_fallback_daily_message_stock_focus_without_ticker_change_omits_suffix(self) -> None:
        stock_focus = [
            NewsItem(
                title="Company shares gain after guidance raise",
                source="CNBC Finance",
                published_at="2026-04-14T06:00:00Z",
                url="https://example.com/stock",
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
            finance_items=[],
            single_stock_items=stock_focus,
            crypto_items=[],
            ai_items=[],
            quotes=quotes,
            quote_of_day="Stay focused.",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )

        self.assertIn('Company shares gain after guidance raise (<a href="https://example.com/stock">CNBC Finance</a>)', message)
        self.assertNotIn("за сутки", message)

    def test_fallback_daily_message_omits_crypto_section_when_empty(self) -> None:
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
            finance_items=[],
            single_stock_items=[],
            crypto_items=[],
            ai_items=[],
            quotes=quotes,
            quote_of_day="Stay focused.",
            now_local=datetime(2026, 4, 14, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        )

        self.assertNotIn("Крипто в фокусе", message)
        self.assertIn("2) ИИ", message)
        self.assertIn("3) Котировки", message)
        self.assertIn("4) Цитата дня", message)

    def test_build_daily_translation_prompt_includes_crypto_titles(self) -> None:
        prompt = build_daily_translation_prompt(
            finance_items=[],
            single_stock_items=[],
            crypto_items=[
                NewsItem(
                    title="US Senate advances stablecoin bill",
                    source="Axios",
                    published_at="2026-04-14T05:20:00Z",
                    url="https://example.com/crypto",
                    summary="Summary",
                )
            ],
            ai_items=[],
            quote_of_day="Stay focused.",
        )

        self.assertIn('"crypto_titles": [', prompt)
        self.assertIn("US Senate advances stablecoin bill", prompt)


if __name__ == "__main__":
    unittest.main()
