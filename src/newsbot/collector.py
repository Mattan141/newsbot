"""The collection pipeline: fetch -> tag -> store -> schedule price checks.

Kept separate from the scripts so it can be unit-tested without the internet.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from newsbot.news import Headline, merge_and_dedupe
from newsbot.storage import Store
from newsbot.tagger import tag_headline
from newsbot.watchlist import BY_SYMBOL

# Only track prices for stories the bot saw within this long of publication.
# Tracking a 6-hour-old story tells us nothing about the news's effect.
FRESH_WINDOW = timedelta(minutes=30)
# Round-up articles ("10 Tech Stocks Whale Activity Today") tag lots of tickers
# but aren't really news about any of them, so they're stored but not tracked.
MAX_SYMBOLS_TO_TRACK = 3

# What "the market" means for each asset type. Comparing against this tells us
# whether a move was caused by the news or by everything moving together.
BENCHMARKS = {"US": "SPY", "CRYPTO": "BTC/USD"}


def benchmark_for(symbol: str) -> str | None:
    asset = BY_SYMBOL.get(symbol)
    bench = BENCHMARKS.get(asset.market) if asset else None
    return None if bench == symbol else bench  # Bitcoin isn't compared to itself


@dataclass
class CollectResult:
    fetched: int = 0
    new: int = 0
    tagged: int = 0
    tracked: int = 0


def trackable_symbols(symbols: list[str], us_market_open: bool) -> list[str]:
    """Watchlist symbols we can price right now (crypto always; US only when open)."""
    out = []
    for s in symbols:
        asset = BY_SYMBOL.get(s)
        if not asset or not asset.tradable:
            continue
        if asset.market == "US" and not us_market_open:
            continue
        out.append(s)
    return out


def process_headlines(store: Store, batches: list[list[Headline]], now: datetime,
                      us_market_open: bool) -> CollectResult:
    headlines = merge_and_dedupe(*batches)
    result = CollectResult(fetched=len(headlines))
    for h in headlines:
        symbols = tag_headline(h)
        if not store.add_headline(h, symbols, seen_at=now):
            continue  # already stored on an earlier run
        result.new += 1
        if symbols:
            result.tagged += 1
        if now - h.published <= FRESH_WINDOW and len(symbols) <= MAX_SYMBOLS_TO_TRACK:
            to_track = trackable_symbols(symbols, us_market_open)
            if to_track:
                store.schedule_checks(h.uid, to_track, seen_at=now,
                                      benchmarks={s: benchmark_for(s) for s in to_track})
                result.tracked += 1
    return result


def is_us_stock(symbol: str) -> bool:
    return "/" not in symbol and not symbol.endswith(".L")


def run_price_checks(store: Store, get_prices, now: datetime,
                     us_market_open: bool = True) -> dict[str, int]:
    """Fill in every price check that's due. `get_prices(symbols) -> {symbol: price}`.

    US stock checks that fall due while the US market is closed are marked
    missed: after-hours quotes are too unreliable to measure news effects with.
    """
    due = store.due_checks(now)
    if not due:
        return {}
    if not us_market_open:
        counts: dict[str, int] = {}
        for row in [r for r in due if is_us_stock(r["symbol"])]:
            status = store.record_price(row, None, now)
            counts[status] = counts.get(status, 0) + 1
        due = [r for r in due if not is_us_stock(r["symbol"])]
        if not due:
            return counts
    else:
        counts = {}
    symbols = sorted({row["symbol"] for row in due})
    try:
        prices = get_prices(symbols)
    except Exception as exc:
        print(f"  [warn] price fetch failed: {exc}")
        prices = {}
    for row in due:
        price = prices.get(row["symbol"]) or None  # treat 0.0 as "no price"
        status = store.record_price(row, price, now)
        counts[status] = counts.get(status, 0) + 1
    return counts


def retag_all(store: Store) -> dict[str, int]:
    """Re-run the current tagging rules over every stored headline.

    Use after improving the tagger. Wrong tags are fixed, and price checks that
    the new rules wouldn't have created (wrong asset, round-up article) are removed.
    """
    counts = {"retagged": 0, "checks_removed": 0}
    rows = store.conn.execute("SELECT uid, source, title, url, published_at, symbols FROM headlines")
    for row in rows.fetchall():
        old = [s for s in row["symbols"].split(",") if s]
        h = Headline(row["source"], row["title"], row["url"] or "",
                     datetime.fromisoformat(row["published_at"]), old)
        new = tag_headline(h)
        if new == sorted(old):
            continue
        counts["retagged"] += 1
        store.update_symbols(row["uid"], new)
        to_remove = set(old) - set(new)
        if len(new) > MAX_SYMBOLS_TO_TRACK:
            to_remove |= set(new)  # round-up article: stop tracking all of it
        counts["checks_removed"] += store.delete_checks(row["uid"], sorted(to_remove))
    # Round-ups whose tags didn't change but are now over the limit
    for row in store.conn.execute("SELECT uid, symbols FROM headlines").fetchall():
        symbols = [s for s in row["symbols"].split(",") if s]
        if len(symbols) > MAX_SYMBOLS_TO_TRACK:
            counts["checks_removed"] += store.delete_checks(row["uid"], symbols)
    store.conn.commit()
    return counts


def invalidate_outside_session(store: Store, sessions: dict) -> int:
    """Mark US stock checks taken outside regular trading hours as missed.

    `sessions` maps a date to (open_utc, close_utc). Used to clean data collected
    before the after-hours protection existed.
    """
    fixed = 0
    rows = store.conn.execute(
        "SELECT * FROM price_checks WHERE status='done' AND taken_at IS NOT NULL").fetchall()
    for row in rows:
        if not is_us_stock(row["symbol"]):
            continue
        taken = datetime.fromisoformat(row["taken_at"])
        session = sessions.get(taken.date())
        if session is None or not (session[0] <= taken <= session[1]):
            store.conn.execute(
                "UPDATE price_checks SET status='missed', price=NULL "
                "WHERE uid=? AND symbol=? AND horizon_min=?",
                (row["uid"], row["symbol"], row["horizon_min"]))
            fixed += 1
    store.conn.commit()
    return fixed
