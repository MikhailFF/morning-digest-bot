from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime


def parse_rss_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def within_last_24h(dt: datetime | None, now_utc: datetime) -> bool:
    if dt is None:
        return False
    return dt >= now_utc - timedelta(hours=24)


def clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9а-яё]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def sha256_json(data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.\!\?\u2026])\s+(?=[A-ZА-ЯЁ0-9\"«])")


def truncate_to_sentences(text: str, max_sentences: int = 3, max_chars: int = 320) -> str:
    """Return at most `max_sentences` sentences, capped to `max_chars` characters.

    RSS summaries vary in length. We keep the leading 1-3 sentences so the
    reader sees the lede; longer bodies are cut on a sentence boundary when
    possible and otherwise hard-capped with an ellipsis.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    sentences = _SENTENCE_SPLIT_RE.split(cleaned)
    picked = " ".join(sentences[:max_sentences]).strip()
    if len(picked) > max_chars:
        picked = picked[: max_chars - 1].rstrip() + "\u2026"
    return picked
