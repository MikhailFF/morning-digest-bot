from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from digest_bot.config import AppConfig
from digest_bot.llm import OPENROUTER_API_BASE, render_with_llm


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _config(**overrides: object) -> AppConfig:
    payload = {
        "timezone": "Europe/Moscow",
        "openai_enabled": True,
        "openai_api_key": "",
        "openai_api_base": "https://api.openai.com/v1",
        "openai_model": "gpt-4.1-mini",
        "openrouter_api_key": "",
        "openrouter_model": "openai/gpt-4.1-mini",
        "openrouter_site_url": "https://example.com/app",
        "openrouter_app_name": "morning-digest-bot",
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "state_dir": ".",
        "openclaw_repo": "openclaw/openclaw",
        "quotes_file": ".",
    }
    payload.update(overrides)
    return AppConfig(**payload)


class LlmTests(unittest.TestCase):
    def test_render_with_openai_uses_responses_api(self) -> None:
        config = _config(openai_api_key="sk-test")
        seen_request = {}

        def fake_urlopen(request, timeout=0):
            seen_request["url"] = request.full_url
            seen_request["data"] = json.loads(request.data.decode("utf-8"))
            seen_request["headers"] = dict(request.header_items())
            return _FakeResponse({"output_text": "translated"})

        with patch("digest_bot.llm.urlopen", side_effect=fake_urlopen):
            result = render_with_llm(config, "translate this")

        self.assertEqual("translated", result)
        self.assertEqual("https://api.openai.com/v1/responses", seen_request["url"])
        self.assertEqual("gpt-4.1-mini", seen_request["data"]["model"])
        self.assertEqual("translate this", seen_request["data"]["input"])
        self.assertIn("Authorization", seen_request["headers"])

    def test_render_with_openrouter_uses_chat_completions(self) -> None:
        config = _config(
            openai_api_key="sk-openai-unused",
            openrouter_api_key="or-test",
            openrouter_model="openai/gpt-4.1-mini",
        )
        seen_request = {}

        def fake_urlopen(request, timeout=0):
            seen_request["url"] = request.full_url
            seen_request["data"] = json.loads(request.data.decode("utf-8"))
            seen_request["headers"] = dict(request.header_items())
            return _FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"finance_titles":["Перевод"],"stock_focus_titles":[],"crypto_titles":[],"ai_titles":[],"quote_of_day":"Цитата"}'
                            }
                        }
                    ]
                }
            )

        with patch("digest_bot.llm.urlopen", side_effect=fake_urlopen):
            result = render_with_llm(config, "translate this")

        self.assertEqual('{"finance_titles":["Перевод"],"stock_focus_titles":[],"crypto_titles":[],"ai_titles":[],"quote_of_day":"Цитата"}', result)
        self.assertEqual(f"{OPENROUTER_API_BASE}/chat/completions", seen_request["url"])
        self.assertEqual("openai/gpt-4.1-mini", seen_request["data"]["model"])
        self.assertEqual("translate this", seen_request["data"]["messages"][0]["content"])
        self.assertEqual("https://example.com/app", seen_request["headers"]["Http-referer"])
        self.assertEqual("morning-digest-bot", seen_request["headers"]["X-title"])


if __name__ == "__main__":
    unittest.main()
