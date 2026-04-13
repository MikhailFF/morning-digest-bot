from __future__ import annotations

from datetime import datetime, timezone
import unittest

from digest_bot.utils import normalize_title, within_last_24h


class UtilsTests(unittest.TestCase):
    def test_normalize_title_collapses_noise(self) -> None:
        self.assertEqual(normalize_title("Fed hikes rates!!!"), "fed hikes rates")

    def test_within_last_24h(self) -> None:
        now = datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc)
        self.assertTrue(within_last_24h(datetime(2026, 4, 13, 10, 0, tzinfo=timezone.utc), now))
        self.assertFalse(within_last_24h(datetime(2026, 4, 12, 8, 59, tzinfo=timezone.utc), now))


if __name__ == "__main__":
    unittest.main()
