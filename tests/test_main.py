from __future__ import annotations

import unittest

from digest_bot.main import _validate_daily_message


class MainTests(unittest.TestCase):
    def test_validate_daily_message_accepts_expected_structure(self) -> None:
        ok, error = _validate_daily_message(
            "\n".join(
                [
                    "1) Финансы и экономика",
                    "1. Новость (Reuters)",
                    "2. Новость (CNBC)",
                    "2) ИИ",
                    "1. Новость (The Verge AI)",
                    "3) Котировки",
                    "- BTC: 80000 USD (+1.00%)",
                    "4) Цитата дня",
                    "Stay focused.",
                ]
            )
        )

        self.assertTrue(ok)
        self.assertEqual("", error)

    def test_validate_daily_message_rejects_suspicious_phrase(self) -> None:
        ok, error = _validate_daily_message(
            "\n".join(
                [
                    "1) Финансы и экономика",
                    "not financial advice",
                    "2) ИИ",
                    "3) Котировки",
                    "4) Цитата дня",
                    "Stay focused.",
                    "Extra line 1",
                    "Extra line 2",
                ]
            )
        )

        self.assertFalse(ok)
        self.assertIn("suspicious phrase", error)


if __name__ == "__main__":
    unittest.main()
