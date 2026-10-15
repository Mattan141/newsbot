"""Tests for tagging, storage and the collection pipeline. No internet or keys needed."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from newsbot.collector import process_headlines, run_price_checks  # noqa: E402
from newsbot.news import Headline  # noqa: E402
from newsbot.storage import Store  # noqa: E402
from newsbot.tagger import match_text, tag_headline  # noqa: E402

NOW = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc)


def _h(title, minutes_ago=1, symbols=None, source="test"):
    return Headline(source, title, "", NOW - timedelta(minutes=minutes_ago), symbols or [])


# ---- tagger -------------------------------------------------------------
def test_matches_company_names():
    assert match_text("Apple unveils new iPhone") == {"AAPL"}
    assert match_text("Barclays and HSBC shares fall") == {"BARC.L", "HSBA.L"}
    assert match_text("Bitcoin slips as South Korea blocks exchanges") == {"BTC/USD"}


def test_no_false_matches_inside_words():
    assert match_text("Pineapple prices soar") == set()
    assert match_text("BTC miners") == {"BTC/USD"}       # BTC is Bitcoin...
    assert "BT-A.L" not in match_text("BTC miners")       # ...not BT Group


def test_cashtags():
    assert match_text("Big day for $tsla and $ETH") == {"TSLA", "ETH/USD"}


def test_alpaca_tags_are_normalised_and_merged():
    h = _h("Tesla up 10%", symbols=["TSLA", "BTCUSD"])
    assert tag_headline(h) == ["BTC/USD", "TSLA"]


def test_analyst_firm_is_not_tagged_but_subject_is():
    # Real headlines from the first collection run
    assert tag_headline(_h("JP Morgan Maintains Overweight on Moodys, Lowers Price Target to $555",
                           symbols=["JPM", "MCO"])) == ["MCO"]
    assert tag_headline(_h("Truist Securities Maintains Hold on JPMorgan Chase, Raises Price Target to $361",
                           symbols=["JPM"])) == ["JPM"]
    # Normal headlines are unaffected
    assert tag_headline(_h("JPMorgan profits beat forecasts")) == ["JPM"]


def test_roundup_articles_are_stored_but_not_tracked():
    store = Store(":memory:")
    roundup = _h("10 Information Technology Stocks Whale Activity In Today's Session",
                 symbols=["NVDA", "INTC", "SMCI", "IONQ", "CRWV"])
    r = process_headlines(store, [[roundup]], NOW, us_market_open=True)
    assert (r.new, r.tagged, r.tracked) == (1, 1, 0)


# ---- storage + pipeline --------------------------------------------------
def test_duplicates_are_stored_once():
    store = Store(":memory:")
    batch = [_h("Nvidia hits record high")]
    first = process_headlines(store, [batch], NOW, us_market_open=True)
    second = process_headlines(store, [batch], NOW, us_market_open=True)
    assert (first.new, second.new) == (1, 0)


def test_only_fresh_tradable_headlines_are_tracked():
    store = Store(":memory:")
    batch = [
        _h("Nvidia hits record high", minutes_ago=5),       # fresh, US  -> tracked
        _h("Microsoft cuts jobs", minutes_ago=300),         # too old    -> not tracked
        _h("Barclays profits jump", minutes_ago=5),         # UK         -> not tracked (yet)
        _h("Poundland in rescue talks", minutes_ago=5),     # no asset   -> not tracked
    ]
    r = process_headlines(store, [batch], NOW, us_market_open=True)
    assert (r.new, r.tagged, r.tracked) == (4, 3, 1)


def test_us_stocks_not_tracked_when_market_closed_but_crypto_is():
    store = Store(":memory:")
    batch = [_h("Tesla recalls cars"), _h("Ethereum upgrade goes live")]
    r = process_headlines(store, [batch], NOW, us_market_open=False)
    assert r.tracked == 1


def test_price_checks_fill_in_and_late_ones_are_missed():
    store = Store(":memory:")
    process_headlines(store, [[_h("Bitcoin jumps")]], NOW, us_market_open=False)

    # +0 check, right away
    assert run_price_checks(store, lambda syms: {"BTC/USD": 100.0}, NOW) == {"done": 1}
    # +5 check, on time
    assert run_price_checks(store, lambda syms: {"BTC/USD": 101.0},
                            NOW + timedelta(minutes=5, seconds=20)) == {"done": 1}
    # laptop asleep for an hour: +30 and +60 are both too late
    assert run_price_checks(store, lambda syms: {"BTC/USD": 999.0},
                            NOW + timedelta(minutes=90)) == {"missed": 2}

    moves = store.moves()
    assert len(moves) == 1 and moves[0]["pct"] == 1.0


def test_price_fetch_failure_does_not_crash():
    store = Store(":memory:")
    process_headlines(store, [[_h("Solana outage")]], NOW, us_market_open=False)

    def broken(_):
        raise ConnectionError("no internet")

    # Solana and its Bitcoin benchmark are both marked missed, nothing crashes
    assert run_price_checks(store, broken, NOW) == {"missed": 2}


# ---- market benchmark + retag -------------------------------------------
def test_us_stock_checks_include_spy_benchmark():
    store = Store(":memory:")
    process_headlines(store, [[_h("Netflix to lay off 1,000 staff")]], NOW, us_market_open=True)
    rows = store.conn.execute("SELECT symbol, role, benchmark FROM price_checks WHERE horizon_min=0").fetchall()
    assert sorted(tuple(r) for r in rows) == [("NFLX", "asset", "SPY"), ("SPY", "benchmark", None)]


def test_bitcoin_has_no_benchmark_but_altcoins_use_bitcoin():
    store = Store(":memory:")
    process_headlines(store, [[_h("Bitcoin jumps"), _h("Solana outage")]], NOW, us_market_open=False)
    rows = store.conn.execute(
        "SELECT symbol, benchmark FROM price_checks WHERE role='asset' AND horizon_min=0").fetchall()
    assert dict((r[0], r[1]) for r in rows) == {"BTC/USD": None, "SOL/USD": "BTC/USD"}


def test_abnormal_move_removes_market_move():
    store = Store(":memory:")
    process_headlines(store, [[_h("Netflix to lay off 1,000 staff")]], NOW, us_market_open=True)
    run_price_checks(store, lambda s: {"NFLX": 100.0, "SPY": 500.0}, NOW)
    # Netflix -1.0%, but the whole market fell -0.6% -> abnormal only -0.4%
    run_price_checks(store, lambda s: {"NFLX": 99.0, "SPY": 497.0}, NOW + timedelta(minutes=5))
    m = store.moves()[0]
    assert (m["pct"], m["bench_pct"], m["abnormal_pct"]) == (-1.0, -0.6, -0.4)
    assert store.average_moves()[0]["avg_abnormal"] == 0.4


def test_old_database_is_migrated(tmp_path):
    import sqlite3
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.executescript("""
        CREATE TABLE headlines (uid TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
            url TEXT, published_at TEXT NOT NULL, seen_at TEXT NOT NULL, symbols TEXT NOT NULL DEFAULT '');
        CREATE TABLE price_checks (uid TEXT NOT NULL, symbol TEXT NOT NULL, horizon_min INTEGER NOT NULL,
            due_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', price REAL, taken_at TEXT,
            PRIMARY KEY (uid, symbol, horizon_min));
        INSERT INTO price_checks (uid, symbol, horizon_min, due_at) VALUES ('x', 'AAPL', 0, '2026');
    """)
    old.commit(); old.close()
    store = Store(db)
    row = store.conn.execute("SELECT role, benchmark FROM price_checks").fetchone()
    assert (row["role"], row["benchmark"]) == ("asset", None)


def test_retag_fixes_old_wrong_tags_and_removes_their_checks():
    from newsbot.collector import retag_all
    store = Store(":memory:")
    bad = _h("JP Morgan Maintains Overweight on Moodys, Lowers Price Target to $555")
    # simulate the old buggy tagger: stored as JPM and tracked
    store.add_headline(bad, ["JPM", "MCO"], seen_at=NOW)
    store.schedule_checks(bad.uid, ["JPM"], seen_at=NOW)
    counts = retag_all(store)
    assert counts == {"retagged": 1, "checks_removed": 4}
    assert store.recent_tagged()[0]["symbols"] == "MCO"


# ---- after-hours data quality -------------------------------------------
def test_wide_or_one_sided_quotes_are_rejected_in_strict_mode():
    from newsbot.market_data import reliable_midpoint
    assert reliable_midpoint(100.0, 100.2) == 100.1     # tight spread: fine
    assert reliable_midpoint(480.0, 540.0) == 0.0       # 12% spread: after-hours junk
    assert reliable_midpoint(0.0, 540.0) == 0.0         # one side missing


def test_us_checks_due_after_close_are_missed_but_crypto_continues():
    store = Store(":memory:")
    process_headlines(store, [[_h("Microsoft cuts jobs"), _h("Solana outage")]], NOW, us_market_open=True)
    counts = run_price_checks(store, lambda s: {"SOL/USD": 150.0, "BTC/USD": 80000.0},
                              NOW, us_market_open=False)
    # MSFT + its SPY benchmark missed; SOL + its BTC benchmark recorded
    assert counts == {"missed": 2, "done": 2}


def test_cleanup_marks_prices_outside_session_as_missed():
    from newsbot.collector import invalidate_outside_session
    store = Store(":memory:")
    process_headlines(store, [[_h("Microsoft cuts jobs")]], NOW, us_market_open=True)
    run_price_checks(store, lambda s: {"MSFT": 540.0, "SPY": 772.0}, NOW)              # 15:00 UTC: in session
    run_price_checks(store, lambda s: {"MSFT": 506.0, "SPY": 772.0},
                     NOW + timedelta(minutes=5))                                       # pretend after close
    session = {NOW.date(): (NOW - timedelta(hours=2), NOW + timedelta(minutes=2))}   # closes at 15:02
    assert invalidate_outside_session(store, session) == 2   # the +5 MSFT and SPY prices
    assert store.moves() == []
