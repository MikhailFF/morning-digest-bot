from __future__ import annotations

import unittest
from unittest.mock import patch

from digest_bot.fetchers import enrich_single_stock_news, select_crypto_focus_news, split_finance_news
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


if __name__ == "__main__":
    unittest.main()
