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
        tracked_keys = ["DIGEST_TIMEZONE", "STATE_DIR", "TELEGRAM_CHAT_ID"]
        saved = {key: os.environ.get(key) for key in tracked_keys}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / ".env").write_text(
                "DIGEST_TIMEZONE=UTC\nSTATE_DIR=./custom-state\nTELEGRAM_CHAT_ID=from-dotenv\n",
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

        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
