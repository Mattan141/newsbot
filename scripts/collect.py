"""Week 3: the news collector.

Fetches news, tags each headline with the assets it mentions, saves everything
to data/newsbot.db, and records prices at +0, +5, +30 and +60 minutes after
fresh headlines.

Usage:
    python scripts/collect.py           run once and exit
    python scripts/collect.py --loop    keep running (Ctrl + C to stop)

For the price checks to work, leave --loop running. If the laptop sleeps,
checks that come due while it's asleep are marked "missed", not faked.
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
from newsbot.storage import Store

NEWS_EVERY_SEC = 300   # fetch news every 5 minutes (polite to the websites)
# Only start tracking a US stock if all its checks (+60 min) finish before the close.
CLOSE_BUFFER = timedelta(minutes=65)
TICK_SEC = 30          # check for due price checks every 30 seconds

settings = load_settings()
store = Store()
market = MarketData(settings)
clock = TradingClient(settings.api_key, settings.secret_key, paper=True)


def collect_news() -> None:
    now = datetime.now(timezone.utc)
    clk = clock.get_clock()
    us_open = clk.is_open and clk.next_close - now >= CLOSE_BUFFER
    us_state = "open" if us_open else ("closing soon, not starting new US checks"
                                       if clk.is_open else "closed")
    batches = []
    try:
        batches.append(fetch_alpaca_news(settings))
    except Exception as exc:
        print(f"  [warn] Alpaca news failed: {exc}")
    batches.append(fetch_rss_news())
    r = process_headlines(store, batches, now, us_market_open=us_open)
    print(f"{datetime.now():%H:%M:%S}  news: {r.fetched} fetched, {r.new} new, "
          f"{r.tagged} tagged, {r.tracked} now being price-tracked "
          f"(US market {us_state})")


def check_prices() -> None:
    now = datetime.now(timezone.utc)
    us_open = clock.get_clock().is_open
    counts = run_price_checks(store, lambda syms: market.latest_prices(syms, strict=True),
                              now, us_market_open=us_open)
    if counts:
        print(f"{datetime.now():%H:%M:%S}  price checks: {counts}")


if "--loop" not in sys.argv:
    collect_news()
    check_prices()
    print("Done. Run with --loop to keep collecting and to fill in later price checks.")
    sys.exit()

RETRY_AFTER_SEC = 60   # after a failed news fetch, try again in a minute

print("Collector running. Press Ctrl + C to stop.\n")
last_news = 0.0
try:
    while True:
        # A dropped Wi-Fi connection or a website being down must never kill
        # the bot: log it, skip this round, and try again shortly.
        if time.time() - last_news >= NEWS_EVERY_SEC:
            try:
                collect_news()
                last_news = time.time()
            except Exception as exc:
                print(f"{datetime.now():%H:%M:%S}  [warn] news round failed, retrying in "
                      f"{RETRY_AFTER_SEC}s: {type(exc).__name__}")
                last_news = time.time() - NEWS_EVERY_SEC + RETRY_AFTER_SEC
        try:
            check_prices()
        except Exception as exc:
            print(f"{datetime.now():%H:%M:%S}  [warn] price checks failed: {type(exc).__name__}")
        time.sleep(TICK_SEC)
except KeyboardInterrupt:
    print("\nStopped. Everything collected so far is saved in data/newsbot.db")
