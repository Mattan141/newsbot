"""Step 4: pull recent headlines from Alpaca news and RSS feeds.

Usage:  python scripts/fetch_news.py               (all recent market news)
        python scripts/fetch_news.py TSLA NVDA     (Alpaca news for these tickers)
"""
import sys

import _setup_path  # noqa: F401
from newsbot.config import load_settings
from newsbot.news import fetch_alpaca_news, fetch_rss_news, merge_and_dedupe

symbols = [s.upper() for s in sys.argv[1:]] or None
settings = load_settings()

alpaca = fetch_alpaca_news(settings, symbols=symbols)
rss = fetch_rss_news()
headlines = merge_and_dedupe(alpaca, rss)

print(f"{len(alpaca)} from Alpaca, {len(rss)} from RSS -> {len(headlines)} unique\n")
for h in headlines[:25]:
    tickers = f" [{', '.join(h.symbols)}]" if h.symbols else ""
    print(f"{h.published:%d %b %H:%M}  {h.source:<22} {h.title[:90]}{tickers}")
