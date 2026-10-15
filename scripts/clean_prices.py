"""One-off clean-up: discard US stock prices recorded outside market hours.

Older versions of the collector could take a "price" after the US market had
closed, when quotes are thin and unreliable (e.g. a fake -6% Microsoft move).
This checks every recorded US price against Alpaca's market calendar and marks
any taken outside the regular session as missed.

Usage:  python scripts/clean_prices.py
"""
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import _setup_path  # noqa: F401
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetCalendarRequest

from newsbot.collector import invalidate_outside_session
from newsbot.config import load_settings
from newsbot.storage import Store

NEW_YORK = ZoneInfo("America/New_York")
store = Store()
first, last = store.conn.execute(
    "SELECT MIN(taken_at), MAX(taken_at) FROM price_checks WHERE taken_at IS NOT NULL").fetchone()
if not first:
    raise SystemExit("No price checks yet, nothing to clean.")

settings = load_settings()
client = TradingClient(settings.api_key, settings.secret_key, paper=True)
days = client.get_calendar(GetCalendarRequest(
    start=date.fromisoformat(first[:10]) - timedelta(days=1),
    end=date.fromisoformat(last[:10]) + timedelta(days=1),
))
# Calendar times are New York local; convert each session to UTC.
sessions = {}
for d in days:
    open_utc = d.open.replace(tzinfo=NEW_YORK).astimezone(ZoneInfo("UTC"))
    close_utc = d.close.replace(tzinfo=NEW_YORK).astimezone(ZoneInfo("UTC"))
    sessions[open_utc.date()] = (open_utc, close_utc)

fixed = invalidate_outside_session(store, sessions)
print(f"US price checks taken outside market hours, now marked missed: {fixed}")
