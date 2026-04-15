from __future__ import annotations

import json
from urllib.request import Request, urlopen

from .config import AppConfig


def render_with_llm(config: AppConfig, prompt: str) -> str | None:
    if not config.openai_enabled or not config.openai_api_key:
        return None

    body = {
        "model": config.openai_model,
        "input": prompt,
        "max_output_tokens": config.openai_max_output_tokens,
    }
    request = Request(
        f"{config.openai_api_base}/responses",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.openai_api_key}",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None
