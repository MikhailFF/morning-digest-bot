from __future__ import annotations

import json
from urllib.request import Request, urlopen

from .config import AppConfig

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


def _extract_text_from_payload(payload: dict) -> str | None:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

    for choice in payload.get("choices", []):
        message = choice.get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text_parts = [
                part.get("text", "").strip()
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str) and part.get("text", "").strip()
            ]
            if text_parts:
                return "\n".join(text_parts)

    return None


def _openai_request(config: AppConfig, prompt: str) -> Request:
    body = {
        "model": config.openai_model,
        "input": prompt,
    }
    return Request(
        f"{config.openai_api_base}/responses",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.openai_api_key}",
        },
    )


def _openrouter_request(config: AppConfig, prompt: str) -> Request:
    body = {
        "model": config.openrouter_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.openrouter_api_key}",
    }
    if config.openrouter_site_url:
        headers["HTTP-Referer"] = config.openrouter_site_url
    if config.openrouter_app_name:
        headers["X-Title"] = config.openrouter_app_name

    return Request(
        f"{OPENROUTER_API_BASE}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=headers,
    )


def render_with_llm(config: AppConfig, prompt: str) -> str | None:
    if not config.openai_enabled:
        return None
    if config.openrouter_api_key:
        request = _openrouter_request(config, prompt)
    elif config.openai_api_key:
        request = _openai_request(config, prompt)
    else:
        return None

    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    return _extract_text_from_payload(payload)


def translate_daily_content(config: AppConfig, prompt: str) -> dict[str, object] | None:
    response_text = render_with_llm(config, prompt)
    if not response_text:
        return None

    candidate = response_text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    return payload
