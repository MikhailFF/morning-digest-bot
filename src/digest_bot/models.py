from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: str
    url: str
    summary: str


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    label: str
    price: float | None
    change_24h: float | None
    suffix: str = ""


@dataclass(frozen=True)
class OpenClawRelease:
    version: str
    title: str
    published_at: str
    url: str
    notes: str
