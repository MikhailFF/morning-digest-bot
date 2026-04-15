from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .models import AssetSpec, NewsItem, OpenClawRelease, QuoteSnapshot
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
                    summary=clean_html(summary)[:140],
                )
            )

    items.sort(key=lambda item: item.published_at, reverse=True)
    return items[:limit]


def _fetch_coingecko_quotes(instruments: list[str]) -> dict[str, dict]:
    if not instruments:
        return {}
    ids = ",".join(sorted(set(instruments)))
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
    try:
        return json.loads(_http_get(url).decode("utf-8"))
    except Exception:
        return {}


def _fetch_yahoo_quotes(instruments: list[str]) -> dict[str, dict]:
    if not instruments:
        return {}
    joined = ",".join(sorted(set(instruments)))
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={quote(joined, safe=',=^.-')}"
    try:
        payload = json.loads(_http_get(url).decode("utf-8"))
        rows = payload.get("quoteResponse", {}).get("result", [])
        return {str(row.get("symbol", "")).strip(): row for row in rows if row.get("symbol")}
    except Exception:
        return {}


def fetch_asset_quotes(assets: list[AssetSpec]) -> dict[str, QuoteSnapshot]:
    coingecko_ids = [asset.instrument for asset in assets if asset.provider == "coingecko"]
    yahoo_symbols = [asset.instrument for asset in assets if asset.provider == "yahoo"]
    coingecko_data = _fetch_coingecko_quotes(coingecko_ids)
    yahoo_data = _fetch_yahoo_quotes(yahoo_symbols)

    quotes: dict[str, QuoteSnapshot] = {}
    for asset in assets:
        price = None
        change_24h = None
        if asset.provider == "coingecko":
            row = coingecko_data.get(asset.instrument, {})
            price = row.get("usd")
            change_24h = row.get("usd_24h_change")
        elif asset.provider == "yahoo":
            row = yahoo_data.get(asset.instrument, {})
            price = row.get("regularMarketPrice")
            change_24h = row.get("regularMarketChangePercent")

        quotes[asset.key] = QuoteSnapshot(
            symbol=asset.key,
            label=asset.label,
            price=price,
            change_24h=change_24h,
            suffix=asset.suffix,
        )
    return quotes


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
        notes=clean_html(payload.get("body") or "")[:1800],
    )
