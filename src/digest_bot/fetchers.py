from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .models import NewsItem, OpenClawRelease, QuoteSnapshot
from .utils import clean_html, normalize_title, parse_rss_datetime, within_last_24h

USER_AGENT = "morning-digest-bot/1.0"

FINANCE_RSS_SOURCES = [
    ("Reuters Markets", "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC Finance", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
]

AI_RSS_SOURCES = [
    ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("The Verge AI", "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
]


def _http_get(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/xml, text/xml, application/rss+xml, */*",
        },
    )
    with urlopen(request, timeout=20) as response:
        return response.read()


def fetch_rss_news(sources: Iterable[tuple[str, str]], now_utc: datetime, limit: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for source_name, url in sources:
        try:
            payload = _http_get(url)
            root = ET.fromstring(payload)
        except Exception:
            continue

        for node in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title = (node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            link = (
                node.findtext("link")
                or node.findtext("{http://www.w3.org/2005/Atom}link")
                or node.get("href")
                or ""
            ).strip()
            if not link:
                atom_link = node.find("{http://www.w3.org/2005/Atom}link")
                if atom_link is not None:
                    link = atom_link.attrib.get("href", "").strip()

            summary = (
                node.findtext("description")
                or node.findtext("summary")
                or node.findtext("{http://www.w3.org/2005/Atom}summary")
                or ""
            )
            published_raw = (
                node.findtext("pubDate")
                or node.findtext("published")
                or node.findtext("updated")
                or node.findtext("{http://www.w3.org/2005/Atom}published")
                or node.findtext("{http://www.w3.org/2005/Atom}updated")
                or ""
            )
            published = parse_rss_datetime(published_raw)

            if not title or not link or not within_last_24h(published, now_utc):
                continue

            normalized_title = normalize_title(title)
            if link in seen_urls or normalized_title in seen_titles:
                continue

            seen_urls.add(link)
            seen_titles.add(normalized_title)
            items.append(
                NewsItem(
                    title=title,
                    source=source_name,
                    published_at=published.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    url=link,
                    summary=clean_html(summary)[:240],
                )
            )

    items.sort(key=lambda item: item.published_at, reverse=True)
    return items[:limit]


def fetch_crypto_quotes() -> dict[str, QuoteSnapshot]:
    url = (
        "https://api.coingecko.com/api/v3/simple/price?"
        "ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"
    )
    try:
        payload = json.loads(_http_get(url).decode("utf-8"))
    except Exception:
        payload = {}

    mapping = {
        "BTC": ("bitcoin", "BTC"),
        "ETH": ("ethereum", "ETH"),
        "SOL": ("solana", "SOL"),
    }

    quotes: dict[str, QuoteSnapshot] = {}
    for symbol, (api_key, label) in mapping.items():
        data = payload.get(api_key, {})
        quotes[symbol] = QuoteSnapshot(
            symbol=symbol,
            label=label,
            price=data.get("usd"),
            change_24h=data.get("usd_24h_change"),
            suffix="USD",
        )
    return quotes


def fetch_sp500_quote() -> QuoteSnapshot:
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=2d"
    try:
        payload = json.loads(_http_get(url).decode("utf-8"))
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice")
        previous = meta.get("chartPreviousClose") or meta.get("previousClose")
        change = None if price is None or previous in (None, 0) else ((price - previous) / previous) * 100
    except Exception:
        price = None
        change = None

    return QuoteSnapshot(
        symbol="SPX",
        label="S&P 500",
        price=price,
        change_24h=change,
        suffix="USD",
    )


def select_quote_of_day(quotes_file: Path, day_key: str) -> str:
    lines = [line.strip() for line in quotes_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return "Stay focused on the signal, not the noise."
    idx = sum(ord(ch) for ch in day_key) % len(lines)
    return lines[idx]


def fetch_openclaw_release(repo: str) -> OpenClawRelease | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        payload = json.loads(_http_get(url).decode("utf-8"))
    except Exception:
        return None

    version = payload.get("tag_name") or payload.get("name")
    if not version:
        return None

    return OpenClawRelease(
        version=str(version),
        title=payload.get("name") or str(version),
        published_at=payload.get("published_at") or "",
        url=payload.get("html_url") or "",
        notes=clean_html(payload.get("body") or "")[:4000],
    )
