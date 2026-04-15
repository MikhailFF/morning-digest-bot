from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest

from digest_bot.config import load_config
from digest_bot.utils import normalize_title, within_last_24h


class UtilsTests(unittest.TestCase):
    def test_normalize_title_collapses_noise(self) -> None:
        self.assertEqual(normalize_title("Fed hikes rates!!!"), "fed hikes rates")

    def test_within_last_24h(self) -> None:
        now = datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc)
        self.assertTrue(within_last_24h(datetime(2026, 4, 13, 10, 0, tzinfo=timezone.utc), now))
        self.assertFalse(within_last_24h(datetime(2026, 4, 12, 8, 59, tzinfo=timezone.utc), now))

    def test_load_config_reads_local_dotenv_without_overriding_existing_env(self) -> None:
        original_cwd = Path.cwd()
        tracked_keys = ["DIGEST_TIMEZONE", "STATE_DIR", "TELEGRAM_CHAT_ID", "OPENAI_MAX_OUTPUT_TOKENS", "QUOTE_ASSETS"]
        saved = {key: os.environ.get(key) for key in tracked_keys}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".env").write_text(
                "DIGEST_TIMEZONE=UTC\n"
                "STATE_DIR=./custom-state\n"
                "TELEGRAM_CHAT_ID=from-dotenv\n"
                "OPENAI_MAX_OUTPUT_TOKENS=111\n"
                "QUOTE_ASSETS=BTC|coingecko|bitcoin|BTC|USD;XAU|yahoo|GC=F|Gold|USD\n",
                encoding="utf-8",
            )
            os.environ["TELEGRAM_CHAT_ID"] = "from-env"
            os.chdir(tmp_path)
            try:
                config = load_config()
            finally:
                os.chdir(original_cwd)

        self.assertEqual(config.timezone, "UTC")
        self.assertEqual(config.telegram_chat_id, "from-env")
        self.assertTrue(str(config.state_dir).endswith("custom-state"))
        self.assertEqual(config.openai_max_output_tokens, 111)
        self.assertEqual([asset.key for asset in config.quote_assets], ["BTC", "XAU"])

        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_load_config_falls_back_to_default_assets_on_invalid_input(self) -> None:
        original_cwd = Path.cwd()
        tracked_keys = ["QUOTE_ASSETS"]
        saved = {key: os.environ.get(key) for key in tracked_keys}
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".env").write_text("QUOTE_ASSETS=broken-value\n", encoding="utf-8")
            os.chdir(tmp_path)
            try:
                config = load_config()
            finally:
                os.chdir(original_cwd)
        self.assertGreaterEqual(len(config.quote_assets), 4)
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
