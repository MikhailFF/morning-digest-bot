from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .models import NewsItem, OpenClawRelease, QuoteSnapshot
from .utils import clean_html, normalize_title, parse_rss_datetime

USER_AGENT = "morning-digest-bot/1.0"

# Feeds verified live on 2026-04-20. Dead sources removed:
# - Reuters Markets (feeds.reuters.com) - DNS gone.
# - The Verge AI (www.theverge.com/ai-.../rss/index.xml) - HTTP 404.
# - a16z general feed - HTTP 404.
FINANCE_RSS_SOURCES = [
    ("CNBC Finance", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("MarketWatch", "https://www.marketwatch.com/rss/topstories"),
    ("FT Markets", "https://www.ft.com/markets?format=rss"),
]

AI_RSS_SOURCES = [
    ("MIT Technology Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    ("Ars Technica AI", "https://arstechnica.com/ai/feed/"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
]

CRYPTO_RSS_SOURCES = [
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Axios", "https://www.axios.com/feeds/feed.rss"),
    ("NYT Business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
]

STOCK_FOCUS_LIMIT = 3
CRYPTO_FOCUS_LIMIT = 3

_EXPLICIT_TICKER_RE = re.compile(r"\((?:[A-Z]+:)?([A-Z][A-Z0-9.\-]{0,5})\)")
_SINGLE_STOCK_PATTERNS = (
    re.compile(r"^[A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3}\s+stock\b"),
    re.compile(r"^[A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3}\s+shares\b"),
    re.compile(r"^[A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3}'s\s"),
    re.compile(
        r"^[A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3}\s+"
        r"(?:surges|soars|jumps|rallies|plunges|slumps|slides|tumbles|pops|sinks)\b"
    ),
)
_SINGLE_STOCK_KEYWORDS = (
    " stock ",
    " shares ",
    " share price",
    " price target",
    " upgraded ",
    " downgraded ",
    " buy rating",
    " sell rating",
    " meme stock",
    " short squeeze",
    " surges",
    " soars",
    " jumps",
    " rallies",
    " plunges",
    " slumps",
    " tumbles",
    " slides",
    " pops",
    " sinks",
)
_MACRO_DISQUALIFIERS = (
    " inflation",
    " cpi",
    " ppi",
    " jobs ",
    " payroll",
    " unemployment",
    " fed ",
    " federal reserve",
    " central bank",
    " treasury yields",
    " treasury ",
    " bond ",
    " bonds ",
    " oil ",
    " opec",
    " brent",
    " crude",
    " dollar ",
    " euro ",
    " fx ",
    " forex",
    " economy",
    " economic",
    " gdp",
    " tariff",
    " tariffs",
    " trade war",
    " sanctions",
    " index",
    " indices",
    " s&p 500",
    " dow ",
    " nasdaq composite",
    " market ",
    " markets ",
    " sector",
    " sectors",
    " industry",
    " industries",
    " banks",
    " companies",
)
_MULTI_COMPANY_HINTS = (
    " stocks ",
    " companies ",
    " chipmakers",
    " banks ",
    " airlines ",
    " automakers",
    " retailers",
    " megacap",
    " sector",
    " sectors",
    " industry",
    " industries",
    " magnificent seven",
)
_TICKER_BLACKLIST = {
    "AI",
    "CEO",
    "CPI",
    "EPS",
    "ETF",
    "EV",
    "IPO",
    "SEC",
    "USA",
    "USD",
}
_COMPANY_TICKER_HINTS = {
    "advanced micro devices": ("AMD", "Advanced Micro Devices"),
    "allbirds": ("BIRD", "Allbirds"),
    "alphabet": ("GOOGL", "Alphabet"),
    "amazon": ("AMZN", "Amazon"),
    "apple": ("AAPL", "Apple"),
    "blackberry": ("BB", "BlackBerry"),
    "coinbase": ("COIN", "Coinbase"),
    "constellation energy": ("CEG", "Constellation Energy"),
    "gamestop": ("GME", "GameStop"),
    "intel": ("INTC", "Intel"),
    "meta": ("META", "Meta"),
    "meta platforms": ("META", "Meta Platforms"),
    "microsoft": ("MSFT", "Microsoft"),
    "netflix": ("NFLX", "Netflix"),
    "nvidia": ("NVDA", "Nvidia"),
    "palantir": ("PLTR", "Palantir"),
    "robinhood": ("HOOD", "Robinhood"),
    "shopify": ("SHOP", "Shopify"),
    "strategy": ("MSTR", "Strategy"),
    "tesla": ("TSLA", "Tesla"),
}
_CRYPTO_CONTEXT_TERMS = (
    " bitcoin",
    " btc",
    " ethereum",
    " ether",
    " solana",
    " xrp",
    " crypto",
    " cryptocurrency",
    " stablecoin",
    " digital asset",
    " digital-assets",
    " blockchain",
    " tokenized",
    " tokenisation",
    " tokenization",
    " defi",
    " web3",
    " tether",
    " usdt",
    " usdc",
    " binance",
    " coinbase",
    " kraken",
    " bybit",
    " etf",
    " token ",
    " tokens ",
)
_CRYPTO_POLICY_TERMS = (
    " law ",
    " laws ",
    " legal",
    " legislation",
    " bill ",
    " bills ",
    " regulation",
    " regulatory",
    " regulator",
    " regulators",
    " sec ",
    " securities and exchange commission",
    " cftc",
    " fed ",
    " federal reserve",
    " u.s. treasury",
    " us treasury",
    " treasury department",
    " doj",
    " department of justice",
    " senate",
    " house ",
    " ministry",
    " central bank",
    " bank of russia",
    " russian",
    " russia",
    " putin",
    " kremlin",
    " trump",
    " president",
    " white house",
)
_CRYPTO_RISK_TERMS = (
    " hack",
    " hacked",
    " exploit",
    " exploited",
    " theft",
    " stolen",
    " stole",
    " heist",
    " breach",
    " drain",
    " drained",
    " shutdown",
    " shuts down",
    " wind down",
    " insolvency",
    " insolvent",
    " bankruptcy",
    " charged",
    " charge ",
    " arrested",
    " arrest ",
    " criminal",
    " indictment",
    " indicted",
    " fraud",
    " laundering",
    " probe",
    " investigation",
    " influencer",
    " promoter",
)
_CRYPTO_ADOPTION_TERMS = (
    " buys bitcoin",
    " bought bitcoin",
    " bitcoin purchase",
    " bitcoin treasury",
    " crypto treasury",
    " reserve asset",
    " tokenized stock",
    " tokenized stocks",
    " tokenized security",
    " tokenized securities",
    " tokenized equity",
    " crypto etf",
    " bitcoin etf",
    " ether etf",
    " spot bitcoin",
    " spot ether",
    " etf approval",
    " etf launch",
    " etf filing",
    " etf debut",
    " launches",
    " launch ",
    " approval",
    " approved",
    " files for",
    " filing",
    " treasury strategy",
)
_CRYPTO_LOW_SIGNAL_TERMS = (
    " price prediction",
    " market wrap",
    " technical analysis",
    " meme coin",
    " altcoin season",
    " airdrop",
    " token unlock",
    " funding round",
    " seed round",
    " series a",
    " series b",
    " trading recap",
)
_CRYPTO_PRICE_CHATTER_TERMS = (
    " price ",
    " prices ",
    " rally",
    " rallies",
    " rise ",
    " rises ",
    " rises as",
    " falls ",
    " drops ",
    " jumps ",
    " surges ",
    " gains ",
    " market cap",
)
_CRYPTO_DUPLICATE_STOPWORDS = {
    "after",
    "amid",
    "and",
    "crypto",
    "over",
    "says",
    "the",
    "with",
}


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


def fetch_rss_news(
    sources: Iterable[tuple[str, str]],
    now_utc: datetime,
    limit: int,
    *,
    max_age_hours: int = 24,
) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    earliest = now_utc - timedelta(hours=max_age_hours)

    for source_name, url in sources:
        try:
            payload = _http_get(url)
            root = ET.fromstring(payload)
        except Exception as exc:
            # Visibility: dead or temporarily broken feeds were previously
            # silently skipped, so empty sections looked mysterious.
            print(f"[rss] {source_name} ({url}): {type(exc).__name__}: {exc}", file=sys.stderr)
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

            if not title or not link or published is None or published < earliest:
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


def fetch_rss_news_with_fallback(
    sources: Iterable[tuple[str, str]],
    now_utc: datetime,
    *,
    limit: int,
    min_items: int,
    fallback_hours: tuple[int, ...] = (24, 48, 72),
) -> list[NewsItem]:
    """Fetch RSS with progressively wider windows until we have enough items.

    Real-world feeds (MIT TR, Hugging Face Blog, specialist sites) can publish
    less than once per 24h. When the primary window is too sparse we relax the
    freshness requirement instead of showing an empty section.
    """
    sources = list(sources)
    best: list[NewsItem] = []
    for hours in fallback_hours:
        candidates = fetch_rss_news(sources, now_utc, limit=limit, max_age_hours=hours)
        if len(candidates) >= len(best):
            best = candidates
        if len(candidates) >= min_items:
            return candidates
    return best


def _contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(term in haystack for term in terms)


def _looks_like_single_stock_story(title: str, summary: str) -> bool:
    title = title.strip()
    haystack = f" {title.casefold()} {summary.casefold()} "

    if any(term in haystack for term in _MULTI_COMPANY_HINTS):
        return False

    has_explicit_ticker = _EXPLICIT_TICKER_RE.search(title) is not None
    has_stock_keyword = any(term in haystack for term in _SINGLE_STOCK_KEYWORDS)
    matches_title_pattern = any(pattern.search(title) for pattern in _SINGLE_STOCK_PATTERNS)

    if not (has_explicit_ticker or has_stock_keyword or matches_title_pattern):
        return False

    if not has_explicit_ticker and any(term in haystack for term in _MACRO_DISQUALIFIERS):
        return False

    return True


def split_finance_news(items: list[NewsItem]) -> tuple[list[NewsItem], list[NewsItem]]:
    macro_items: list[NewsItem] = []
    single_stock_items: list[NewsItem] = []

    for item in items:
        if _looks_like_single_stock_story(item.title, item.summary):
            if len(single_stock_items) < STOCK_FOCUS_LIMIT:
                single_stock_items.append(item)
            continue
        macro_items.append(item)

    return macro_items, single_stock_items


def _resolve_equity_ticker(item: NewsItem) -> tuple[str | None, str | None]:
    explicit_match = _EXPLICIT_TICKER_RE.search(item.title)
    if explicit_match:
        ticker = explicit_match.group(1).upper()
        if ticker not in _TICKER_BLACKLIST:
            return ticker, None

    normalized = normalize_title(item.title)
    for company_key, (ticker, company_name) in sorted(_COMPANY_TICKER_HINTS.items(), key=lambda entry: len(entry[0]), reverse=True):
        if company_key in normalized:
            return ticker, company_name

    return None, None


def fetch_equity_quote(ticker: str) -> QuoteSnapshot:
    return _fetch_yahoo_chart_quote(ticker, ticker, ticker, "USD")


def enrich_single_stock_news(items: list[NewsItem]) -> list[NewsItem]:
    quote_cache: dict[str, QuoteSnapshot] = {}
    enriched: list[NewsItem] = []

    for item in items:
        ticker, company_name = _resolve_equity_ticker(item)
        change_24h = None
        if ticker:
            if ticker not in quote_cache:
                quote_cache[ticker] = fetch_equity_quote(ticker)
            change_24h = quote_cache[ticker].change_24h

        enriched.append(
            NewsItem(
                title=item.title,
                source=item.source,
                published_at=item.published_at,
                url=item.url,
                summary=item.summary,
                company_name=company_name,
                ticker=ticker,
                price_change_24h=change_24h,
            )
        )

    return enriched


def _crypto_signal_score(item: NewsItem) -> int | None:
    haystack = f" {item.title.casefold()} {item.summary.casefold()} {item.source.casefold()} "

    if not _contains_any(haystack, _CRYPTO_CONTEXT_TERMS):
        return None

    has_policy = _contains_any(haystack, _CRYPTO_POLICY_TERMS)
    has_risk = _contains_any(haystack, _CRYPTO_RISK_TERMS)
    has_adoption = _contains_any(haystack, _CRYPTO_ADOPTION_TERMS)
    has_price_chatter = _contains_any(haystack, _CRYPTO_PRICE_CHATTER_TERMS)

    score = 0
    if has_policy:
        score += 3
    if has_risk:
        score += 3
    if has_adoption:
        score += 2

    if _contains_any(haystack, _CRYPTO_LOW_SIGNAL_TERMS):
        score -= 2

    # Reject generic price chatter unless it accompanies a concrete adoption or risk event.
    if has_price_chatter and not (has_risk or has_adoption):
        return None

    if score < 2:
        return None

    return score


def _crypto_title_tokens(title: str) -> set[str]:
    return {
        token
        for token in normalize_title(title).split()
        if len(token) > 2 and token not in _CRYPTO_DUPLICATE_STOPWORDS
    }


def _is_near_duplicate_crypto_story(candidate: NewsItem, selected: list[NewsItem]) -> bool:
    candidate_tokens = _crypto_title_tokens(candidate.title)
    if not candidate_tokens:
        return False

    for existing in selected:
        existing_tokens = _crypto_title_tokens(existing.title)
        overlap = candidate_tokens & existing_tokens
        if len(overlap) >= 4 and len(overlap) / min(len(candidate_tokens), len(existing_tokens)) >= 0.6:
            return True

    return False


def select_crypto_focus_news(items: list[NewsItem]) -> list[NewsItem]:
    scored_items: list[tuple[int, NewsItem]] = []
    for item in items:
        score = _crypto_signal_score(item)
        if score is not None:
            scored_items.append((score, item))

    scored_items.sort(key=lambda entry: (entry[0], entry[1].published_at), reverse=True)

    selected: list[NewsItem] = []
    for _score, item in scored_items:
        if _is_near_duplicate_crypto_story(item, selected):
            continue
        selected.append(item)
        if len(selected) == CRYPTO_FOCUS_LIMIT:
            break

    return selected


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


def _fetch_yahoo_chart_quote(ticker: str, symbol: str, label: str, suffix: str) -> QuoteSnapshot:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}?interval=1d&range=2d"
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
        symbol=symbol,
        label=label,
        price=price,
        change_24h=change,
        suffix=suffix,
    )


def fetch_sp500_quote() -> QuoteSnapshot:
    return _fetch_yahoo_chart_quote("^GSPC", "SPX", "S&P 500", "USD")


def fetch_brent_quote() -> QuoteSnapshot:
    return _fetch_yahoo_chart_quote("BZ=F", "BRENT", "Brent", "USD")


def fetch_usd_rub_quote() -> QuoteSnapshot:
    return _fetch_yahoo_chart_quote("USDRUB=X", "USDRUB", "USD/RUB", "RUB")


def fetch_eur_rub_quote() -> QuoteSnapshot:
    return _fetch_yahoo_chart_quote("EURRUB=X", "EURRUB", "EUR/RUB", "RUB")


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
