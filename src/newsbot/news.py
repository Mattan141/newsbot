"""Collects headlines from two free sources and puts them in one common format.

1. Alpaca's news API: already tagged with ticker symbols.
2. RSS feeds: anything you like (BBC, CoinDesk, etc.). Not tagged, so the
   "which stock is this about?" step comes later in the project.

Everything becomes a `Headline`, so later stages don't care where it came from.
"""
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import feedparser
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest

from newsbot.config import Settings

DEFAULT_RSS_FEEDS = {
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
}


@dataclass
class Headline:
    source: str
    title: str
    url: str
    published: datetime
    symbols: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        """Stable ID used to drop duplicates (same story from two feeds)."""
        return hashlib.sha1(self.title.lower().strip().encode()).hexdigest()[:12]


def fetch_alpaca_news(settings: Settings, symbols: list[str] | None = None,
                      hours: int = 24, limit: int = 50) -> list[Headline]:
    client = NewsClient(settings.api_key, settings.secret_key)
    req = NewsRequest(
        symbols=",".join(symbols) if symbols else None,
        start=datetime.now(timezone.utc) - timedelta(hours=hours),
        limit=limit,
    )
    news_set = client.get_news(req)
    return [
        Headline(
            source=f"Alpaca/{n.source}",
            title=n.headline,
            url=n.url or "",
            published=n.created_at,
            symbols=list(n.symbols or []),
        )
        for n in news_set.data.get("news", [])
    ]


def fetch_rss_news(feeds: dict[str, str] = DEFAULT_RSS_FEEDS) -> list[Headline]:
    headlines = []
    for name, url in feeds.items():
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            headlines.append(
                Headline(
                    source=name,
                    title=entry.get("title", "").strip(),
                    url=entry.get("link", ""),
                    published=_parse_rss_time(entry),
                )
            )
    return headlines


def merge_and_dedupe(*batches: list[Headline]) -> list[Headline]:
    """Combine sources, drop duplicates and blank titles, newest first."""
    seen, out = set(), []
    for h in (h for batch in batches for h in batch):
        if h.title and h.uid not in seen:
            seen.add(h.uid)
            out.append(h)
    return sorted(out, key=lambda h: h.published, reverse=True)


def _parse_rss_time(entry) -> datetime:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)
