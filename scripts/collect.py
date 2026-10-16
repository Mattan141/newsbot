"""The news collector.

Fetches news, tags each headline with the assets it mentions, scores its
sentiment, saves everything to data/newsbot.db, and records prices at
+0, +5, +30 and +60 minutes after fresh headlines (plus the market benchmark).

News arrives two ways:
- live stream: Alpaca pushes headlines within seconds of publication
- polling: RSS feeds (BBC, Guardian...) every 2 minutes, plus Alpaca's
  news API every 5 minutes as a backup in case the stream drops

Usage:
    python scripts/collect.py              run once and exit
    python scripts/collect.py --loop       keep running with live news (Ctrl + C to stop)
    python scripts/collect.py --loop --no-stream    polling only

If the laptop sleeps, checks that come due while it's asleep are marked
"missed", not faked.
"""
import sys
import time
from datetime import datetime, timedelta, timezone  # store in UTC, print UK time

import _setup_path  # noqa: F401
from alpaca.trading.client import TradingClient

from newsbot.collector import process_headlines, run_price_checks
from newsbot.config import load_settings
from newsbot.market_data import MarketData
from newsbot.news import fetch_alpaca_news, fetch_rss_news
from newsbot.sentiment import get_scorer
from newsbot.storage import Store

RSS_EVERY_SEC = 120         # RSS feeds only update every few minutes anyway
ALPACA_POLL_EVERY_SEC = 300  # backup for the live stream
PRICES_EVERY_SEC = 30       # check for due price checks
TICK_SEC = 2                # how often the loop wakes up (to pick up live news fast)
RETRY_AFTER_SEC = 60        # after a failed fetch, try again in a minute
# Only start tracking a US stock if all its checks (+60 min) finish before the close.
CLOSE_BUFFER = timedelta(minutes=65)

settings = load_settings()
store = Store()
market = MarketData(settings)
clock = TradingClient(settings.api_key, settings.secret_key, paper=True)
scorer = get_scorer()

_clock_cache = {"at": 0.0, "value": None}


def market_clock():
    """Alpaca's market clock, cached for a minute to avoid needless requests."""
    if time.time() - _clock_cache["at"] > 60 or _clock_cache["value"] is None:
        _clock_cache["value"] = clock.get_clock()
        _clock_cache["at"] = time.time()
    return _clock_cache["value"]


def us_tracking_state() -> tuple[bool, str]:
    clk = market_clock()
    now = datetime.now(timezone.utc)
    ok = clk.is_open and clk.next_close - now >= CLOSE_BUFFER
    if ok:
        return True, "open"
    return False, "closing soon, no new US checks" if clk.is_open else "closed"


def ingest(batches, label: str) -> None:
    now = datetime.now(timezone.utc)
    us_ok, us_state = us_tracking_state()
    r = process_headlines(store, batches, now, us_market_open=us_ok, scorer=scorer)
    if r.new or label != "live":
        print(f"{datetime.now():%H:%M:%S}  {label}: {r.fetched} fetched, {r.new} new, "
              f"{r.tagged} tagged (+{r.positive}/-{r.negative}), "
              f"{r.tracked} now price-tracked (US market {us_state})")


def poll_rss() -> None:
    ingest([fetch_rss_news()], "rss")


def poll_alpaca() -> None:
    ingest([fetch_alpaca_news(settings)], "alpaca")


def check_prices() -> None:
    now = datetime.now(timezone.utc)
    counts = run_price_checks(store, lambda syms: market.latest_prices(syms, strict=True),
                              now, us_market_open=market_clock().is_open)
    if counts:
        print(f"{datetime.now():%H:%M:%S}  price checks: {counts}")


print(f"Sentiment model: {scorer.name}")

if "--loop" not in sys.argv:
    poll_alpaca()
    poll_rss()
    check_prices()
    print("Done. Run with --loop to keep collecting and to fill in later price checks.")
    sys.exit()

live = None
if "--no-stream" not in sys.argv:
    from newsbot.news_stream import LiveNews
    live = LiveNews(settings)
    live.start()
    print("Live news stream: on")

print("Collector running. Press Ctrl + C to stop.\n")
jobs = [  # [function, every_sec, next_run]
    [poll_alpaca, ALPACA_POLL_EVERY_SEC, 0.0],
    [poll_rss, RSS_EVERY_SEC, 0.0],
    [check_prices, PRICES_EVERY_SEC, 0.0],
]
try:
    while True:
        # A dropped Wi-Fi connection or a website being down must never kill
        # the bot: log it, skip this round, and try again shortly.
        if live:
            arrived = live.drain()
            if arrived:
                try:
                    ingest([arrived], "live")
                except Exception as exc:
                    print(f"{datetime.now():%H:%M:%S}  [warn] live ingest failed: {type(exc).__name__}")
        for job in jobs:
            fn, every, next_run = job
            if time.time() >= next_run:
                try:
                    fn()
                    job[2] = time.time() + every
                except Exception as exc:
                    print(f"{datetime.now():%H:%M:%S}  [warn] {fn.__name__} failed, retrying in "
                          f"{RETRY_AFTER_SEC}s: {type(exc).__name__}")
                    job[2] = time.time() + RETRY_AFTER_SEC
        time.sleep(TICK_SEC)
except KeyboardInterrupt:
    print("\nStopped. Everything collected so far is saved in data/newsbot.db")
