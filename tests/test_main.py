from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from digest_bot.config import AppConfig
from digest_bot.main import _validate_daily_message, build_parser, run_daily
from digest_bot.telegram import TelegramSendResult


class MainTests(unittest.TestCase):
    def test_build_parser_supports_force_flag(self) -> None:
        args = build_parser().parse_args(["daily", "--force"])

        self.assertTrue(args.force)
        self.assertEqual("daily", args.command)

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

    def test_validate_daily_message_accepts_structure_with_stock_focus_section(self) -> None:
        ok, error = _validate_daily_message(
            "\n".join(
                [
                    "1) Финансы и экономика",
                    "1. Новость (Reuters)",
                    "2) Акции в фокусе",
                    "1. Новость (+5.00% за сутки) (Yahoo Finance)",
                    "3) ИИ",
                    "1. Новость (The Verge AI)",
                    "4) Котировки",
                    "- BTC: 80000 USD (+1.00%)",
                    "5) Цитата дня",
                    "Stay focused.",
                ]
            )
        )

        self.assertTrue(ok)
        self.assertEqual("", error)

    def test_validate_daily_message_accepts_structure_with_stock_and_crypto_sections(self) -> None:
        ok, error = _validate_daily_message(
            "\n".join(
                [
                    "1) Финансы и экономика",
                    "1. Новость (Reuters)",
                    "2) Акции в фокусе",
                    "1. Новость (+5.00% за сутки) (Yahoo Finance)",
                    "3) Крипто в фокусе",
                    "1. Новость (Axios)",
                    "4) ИИ",
                    "1. Новость (The Verge AI)",
                    "5) Котировки",
                    "- BTC: 80000 USD (+1.00%)",
                    "6) Цитата дня",
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

    def test_run_daily_force_bypasses_duplicate_protection(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            fixture_path = tmp_path / "fixture.json"
            fixture_path.write_text(
                """
{
  "finance_items": [],
  "single_stock_items": [],
  "crypto_items": [],
  "ai_items": [],
  "quotes": {},
  "quote_of_day": "Stay focused."
}
""".strip(),
                encoding="utf-8",
            )
            config = AppConfig(
                timezone="Europe/Moscow",
                openai_enabled=False,
                openai_api_key="",
                openai_api_base="https://api.openai.com/v1",
                openai_model="gpt-4.1-mini",
                openrouter_api_key="",
                openrouter_model="openai/gpt-4.1-mini",
                openrouter_site_url="https://example.com/app",
                openrouter_app_name="morning-digest-bot",
                telegram_enabled=True,
                telegram_bot_token="token",
                telegram_chat_id="chat",
                state_dir=tmp_path / "state",
                openclaw_repo="openclaw/openclaw",
                quotes_file=tmp_path / "quotes.txt",
            )
            today = "2026-04-20"

            with (
                patch("digest_bot.main.load_config", return_value=config),
                patch("digest_bot.main.datetime") as mocked_datetime,
                patch("digest_bot.main.read_json", return_value={"last_date": today}),
                patch("digest_bot.main.translate_daily_content", return_value=None),
                patch("digest_bot.main.send_telegram_message", return_value=TelegramSendResult(ok=True)) as mocked_send,
                patch("digest_bot.main.write_json") as mocked_write,
            ):
                mocked_now = mocked_datetime.now.return_value
                mocked_now.astimezone.return_value.strftime.return_value = today
                mocked_now.astimezone.return_value = mocked_now.astimezone.return_value
                mocked_now.isoformat.return_value = "2026-04-20T00:00:00+00:00"

                exit_code = run_daily(dry_run=False, fixture_path=str(fixture_path), force_send=True)

            self.assertEqual(0, exit_code)
            mocked_send.assert_called_once()
            mocked_write.assert_called_once()


if __name__ == "__main__":
    unittest.main()
