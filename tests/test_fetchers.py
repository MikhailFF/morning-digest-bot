from __future__ import annotations

import io
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from digest_bot.fetchers import (
    enrich_single_stock_news,
    fetch_rss_news,
    fetch_rss_news_with_fallback,
    select_crypto_focus_news,
    split_finance_news,
)
from digest_bot.models import NewsItem, QuoteSnapshot


class FetcherTests(unittest.TestCase):
    def test_split_finance_news_extracts_single_stock_stories(self) -> None:
        items = [
            NewsItem(
                title="US inflation cools faster than expected",
                source="Reuters Markets",
                published_at="2026-04-14T06:00:00Z",
                url="https://example.com/macro",
                summary="Macro update",
            ),
            NewsItem(
                title="Allbirds stock surges after AI pivot",
                source="Yahoo Finance",
                published_at="2026-04-14T05:30:00Z",
                url="https://example.com/stock",
                summary="Single-company move",
            ),
        ]

        macro_items, single_stock_items = split_finance_news(items)

        self.assertEqual(["US inflation cools faster than expected"], [item.title for item in macro_items])
        self.assertEqual(["Allbirds stock surges after AI pivot"], [item.title for item in single_stock_items])

    def test_enrich_single_stock_news_uses_explicit_ticker(self) -> None:
        items = [
            NewsItem(
                title="Constellation Energy (CEG) stock jumps after outlook raise",
                source="Yahoo Finance",
                published_at="2026-04-14T05:30:00Z",
                url="https://example.com/stock",
                summary="Single-company move",
            )
        ]

        with patch(
            "digest_bot.fetchers.fetch_equity_quote",
            return_value=QuoteSnapshot(symbol="CEG", label="CEG", price=300.0, change_24h=8.4, suffix="USD"),
        ):
            enriched = enrich_single_stock_news(items)

        self.assertEqual("CEG", enriched[0].ticker)
        self.assertEqual(8.4, enriched[0].price_change_24h)

    def test_enrich_single_stock_news_leaves_move_empty_when_ticker_is_unknown(self) -> None:
        items = [
            NewsItem(
                title="Little-known startup shares jump on social-media buzz",
                source="CNBC Finance",
                published_at="2026-04-14T05:30:00Z",
                url="https://example.com/stock",
                summary="Single-company move",
            )
        ]

        enriched = enrich_single_stock_news(items)

        self.assertIsNone(enriched[0].ticker)
        self.assertIsNone(enriched[0].price_change_24h)

    def test_select_crypto_focus_news_keeps_high_signal_items_only(self) -> None:
        items = [
            NewsItem(
                title="US Senate advances stablecoin bill after bipartisan push",
                source="Axios",
                published_at="2026-04-14T07:00:00Z",
                url="https://example.com/crypto-1",
                summary="New crypto legislation would set rules for stablecoin issuers.",
            ),
            NewsItem(
                title="Protocol hacked for $120 million in latest DeFi exploit",
                source="The Block",
                published_at="2026-04-14T06:30:00Z",
                url="https://example.com/crypto-2",
                summary="Attack drained digital assets from the protocol treasury.",
            ),
            NewsItem(
                title="BlackRock files for spot Solana ETF in latest crypto push",
                source="NYT Business",
                published_at="2026-04-14T06:00:00Z",
                url="https://example.com/crypto-3",
                summary="The filing expands the firm's digital-asset ETF lineup.",
            ),
            NewsItem(
                title="Bitcoin price rises as traders await Fed meeting",
                source="Reuters Markets",
                published_at="2026-04-14T05:30:00Z",
                url="https://example.com/crypto-4",
                summary="The crypto market was broadly higher in early trading.",
            ),
        ]

        selected = select_crypto_focus_news(items)

        self.assertEqual(
            [
                "US Senate advances stablecoin bill after bipartisan push",
                "Protocol hacked for $120 million in latest DeFi exploit",
                "BlackRock files for spot Solana ETF in latest crypto push",
            ],
            [item.title for item in selected],
        )

    def test_select_crypto_focus_news_caps_results_and_dedupes_similar_events(self) -> None:
        items = [
            NewsItem(
                title="US Senate advances stablecoin bill after bipartisan push",
                source="Axios",
                published_at="2026-04-14T07:00:00Z",
                url="https://example.com/crypto-a",
                summary="New crypto legislation would set rules for stablecoin issuers.",
            ),
            NewsItem(
                title="Stablecoin bill advances in US Senate after bipartisan negotiations",
                source="The Block",
                published_at="2026-04-14T06:55:00Z",
                url="https://example.com/crypto-b",
                summary="Lawmakers moved a major crypto bill ahead.",
            ),
            NewsItem(
                title="Crypto exchange shuts down withdrawals after security breach",
                source="The Block",
                published_at="2026-04-14T06:30:00Z",
                url="https://example.com/crypto-c",
                summary="Customers were unable to access digital assets after the hack.",
            ),
            NewsItem(
                title="Russia weighs new law for crypto mining and digital asset payments",
                source="NYT Business",
                published_at="2026-04-14T06:10:00Z",
                url="https://example.com/crypto-d",
                summary="Officials discussed a new legal framework for crypto activity.",
            ),
            NewsItem(
                title="Public company buys bitcoin for corporate treasury reserve",
                source="Axios",
                published_at="2026-04-14T05:50:00Z",
                url="https://example.com/crypto-e",
                summary="The firm said bitcoin is now part of its treasury strategy.",
            ),
        ]

        selected = select_crypto_focus_news(items)

        self.assertEqual(3, len(selected))
        self.assertEqual(1, sum("stablecoin bill" in item.title.lower() for item in selected))


def _rss_xml(items: list[tuple[str, str, str]]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{l}</link><pubDate>{d}</pubDate></item>"
        for t, l, d in items
    )
    return f"<rss><channel>{body}</channel></rss>".encode("utf-8")


class FetchRssNewsTests(unittest.TestCase):
    def test_fetch_rss_news_logs_failure_and_continues(self) -> None:
        now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
        good_xml = _rss_xml(
            [("CNBC item", "https://example.com/a", "Mon, 20 Apr 2026 09:00:00 +0000")]
        )

        def fake_get(url: str) -> bytes:
            if "broken" in url:
                raise ValueError("boom")
            return good_xml

        stderr = io.StringIO()
        with patch("digest_bot.fetchers._http_get", side_effect=fake_get), patch(
            "sys.stderr", stderr
        ):
            items = fetch_rss_news(
                [("Broken", "https://broken.example.com/rss"), ("Good", "https://good.example.com/rss")],
                now_utc=now,
                limit=5,
            )

        self.assertEqual(["CNBC item"], [item.title for item in items])
        self.assertIn("[rss] Broken", stderr.getvalue())
        self.assertIn("ValueError: boom", stderr.getvalue())

    def test_fetch_rss_news_respects_max_age_hours(self) -> None:
        now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
        xml = _rss_xml(
            [
                ("Fresh", "https://example.com/fresh", "Mon, 20 Apr 2026 09:00:00 +0000"),
                ("Stale", "https://example.com/stale", "Fri, 17 Apr 2026 09:00:00 +0000"),
            ]
        )

        with patch("digest_bot.fetchers._http_get", return_value=xml):
            tight = fetch_rss_news([("Src", "https://example.com")], now, limit=10, max_age_hours=24)
            wide = fetch_rss_news([("Src", "https://example.com")], now, limit=10, max_age_hours=96)

        self.assertEqual(["Fresh"], [item.title for item in tight])
        self.assertEqual({"Fresh", "Stale"}, {item.title for item in wide})

    def test_fetch_rss_news_with_fallback_expands_window_when_sparse(self) -> None:
        now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
        xml = _rss_xml(
            [
                ("Fresh 1", "https://example.com/1", "Mon, 20 Apr 2026 09:00:00 +0000"),
                ("Older 2d", "https://example.com/2", "Sat, 18 Apr 2026 08:00:00 +0000"),
                ("Older 3d", "https://example.com/3", "Fri, 17 Apr 2026 11:00:00 +0000"),
            ]
        )

        with patch("digest_bot.fetchers._http_get", return_value=xml):
            items = fetch_rss_news_with_fallback(
                [("Src", "https://example.com")],
                now_utc=now,
                limit=10,
                min_items=3,
                fallback_hours=(24, 48, 72),
            )

        self.assertEqual(
            {"Fresh 1", "Older 2d", "Older 3d"}, {item.title for item in items}
        )

    def test_fetch_rss_news_with_fallback_returns_best_effort_when_nothing_meets_min(
        self,
    ) -> None:
        now = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
        xml = _rss_xml(
            [("Only one", "https://example.com/only", "Mon, 20 Apr 2026 09:00:00 +0000")]
        )

        with patch("digest_bot.fetchers._http_get", return_value=xml):
            items = fetch_rss_news_with_fallback(
                [("Src", "https://example.com")],
                now_utc=now,
                limit=10,
                min_items=5,
                fallback_hours=(24, 48, 72),
            )

        self.assertEqual(["Only one"], [item.title for item in items])


if __name__ == "__main__":
    unittest.main()
