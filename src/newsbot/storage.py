"""SQLite storage: every headline the bot sees, plus price checks after it.

Two tables:
- headlines:    one row per unique story (when it was published, when we saw it, tickers)
- price_checks: for fresh headlines, the price of each tradable ticker at
                +0, +5, +30 and +60 minutes after the bot saw the story,
                plus the same checks on a *benchmark* (SPY for US stocks,
                Bitcoin for other crypto) so we can separate the news effect
                from the whole market moving.

    abnormal move = asset's move - benchmark's move

That's the raw material for the big question later on:
"does this kind of news actually move the price, and by how much?"

SQLite is a single file (data/newsbot.db), built into Python, no server needed.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from newsbot.news import Headline

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "newsbot.db"
HORIZONS_MIN = (0, 5, 30, 60)
# If a check is this late (e.g. the laptop was asleep), the price is meaningless.
LATE_TOLERANCE = timedelta(minutes=3)

SCHEMA = """
CREATE TABLE IF NOT EXISTS headlines (
    uid          TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT,
    published_at TEXT NOT NULL,
    seen_at      TEXT NOT NULL,
    symbols      TEXT NOT NULL DEFAULT '',
    sentiment       TEXT,      -- positive / negative / neutral
    sentiment_score REAL,      -- -1 .. +1
    sentiment_model TEXT       -- which scorer produced it
);
CREATE TABLE IF NOT EXISTS price_checks (
    uid         TEXT NOT NULL REFERENCES headlines(uid),
    symbol      TEXT NOT NULL,
    horizon_min INTEGER NOT NULL,
    due_at      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending / done / missed
    price       REAL,
    taken_at    TEXT,
    role        TEXT NOT NULL DEFAULT 'asset',    -- asset / benchmark
    benchmark   TEXT,                              -- e.g. 'SPY' for a US stock
    PRIMARY KEY (uid, symbol, horizon_min)
);
CREATE INDEX IF NOT EXISTS idx_checks_due ON price_checks(status, due_at);
"""

# Columns added after the first version. Databases created by the older code
# get them added automatically (a tiny "schema migration").
MIGRATIONS = {
    ("price_checks", "role"): "ALTER TABLE price_checks ADD COLUMN role TEXT NOT NULL DEFAULT 'asset'",
    ("price_checks", "benchmark"): "ALTER TABLE price_checks ADD COLUMN benchmark TEXT",
    ("headlines", "sentiment"): "ALTER TABLE headlines ADD COLUMN sentiment TEXT",
    ("headlines", "sentiment_score"): "ALTER TABLE headlines ADD COLUMN sentiment_score REAL",
    ("headlines", "sentiment_model"): "ALTER TABLE headlines ADD COLUMN sentiment_model TEXT",
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()
        self.conn.executescript(SCHEMA)

    def _migrate(self) -> None:
        for (table, col), sql in MIGRATIONS.items():
            exists = self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists:
                continue  # brand-new database: SCHEMA creates everything
            cols = {r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                self.conn.execute(sql)
        self.conn.commit()

    # ---- headlines -------------------------------------------------------
    def add_headline(self, h: Headline, symbols: list[str], seen_at: datetime,
                     sentiment=None) -> bool:
        """Insert a headline. Returns False if we've already stored it."""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO headlines (uid, source, title, url, published_at, seen_at, "
            "symbols, sentiment, sentiment_score, sentiment_model) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (h.uid, h.source, h.title, h.url, _iso(h.published), _iso(seen_at), ",".join(symbols),
             *((sentiment.label, sentiment.score, sentiment.model) if sentiment else (None,) * 3)),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def set_sentiment(self, uid: str, sentiment) -> None:
        self.conn.execute(
            "UPDATE headlines SET sentiment=?, sentiment_score=?, sentiment_model=? WHERE uid=?",
            (sentiment.label, sentiment.score, sentiment.model, uid))

    # ---- price checks ----------------------------------------------------
    def schedule_checks(self, uid: str, symbols: list[str], seen_at: datetime,
                        benchmarks: dict[str, str | None] | None = None) -> None:
        """Schedule checks for each asset, plus its benchmark (if it has one)."""
        benchmarks = benchmarks or {}
        rows = []
        for s in symbols:
            bench = benchmarks.get(s)
            for h in HORIZONS_MIN:
                due = _iso(seen_at + timedelta(minutes=h))
                rows.append((uid, s, h, due, "asset", bench))
                if bench:
                    rows.append((uid, bench, h, due, "benchmark", None))
        self.conn.executemany(
            "INSERT OR IGNORE INTO price_checks "
            "(uid, symbol, horizon_min, due_at, role, benchmark) VALUES (?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()

    def update_symbols(self, uid: str, symbols: list[str]) -> None:
        self.conn.execute("UPDATE headlines SET symbols=? WHERE uid=?", (",".join(symbols), uid))

    def delete_checks(self, uid: str, symbols: list[str]) -> int:
        """Remove an asset's checks (and benchmark checks nothing else needs)."""
        removed = 0
        for s in symbols:
            removed += self.conn.execute(
                "DELETE FROM price_checks WHERE uid=? AND symbol=? AND role='asset'", (uid, s)
            ).rowcount
        # benchmark rows whose asset rows are all gone
        self.conn.execute(
            """DELETE FROM price_checks WHERE uid=? AND role='benchmark' AND symbol NOT IN
               (SELECT benchmark FROM price_checks WHERE uid=? AND role='asset' AND benchmark IS NOT NULL)""",
            (uid, uid),
        )
        return removed

    def due_checks(self, now: datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM price_checks WHERE status='pending' AND due_at <= ? ORDER BY due_at",
            (_iso(now),),
        ).fetchall()

    def record_price(self, row: sqlite3.Row, price: float | None, now: datetime) -> str:
        """Fill in a due check. Marks it 'missed' if we're too late or had no price."""
        due = datetime.fromisoformat(row["due_at"])
        if price is None or now - due > LATE_TOLERANCE:
            status, price = "missed", None
        else:
            status = "done"
        self.conn.execute(
            "UPDATE price_checks SET status=?, price=?, taken_at=? "
            "WHERE uid=? AND symbol=? AND horizon_min=?",
            (status, price, _iso(now), row["uid"], row["symbol"], row["horizon_min"]),
        )
        self.conn.commit()
        return status

    # ---- reporting -------------------------------------------------------
    def stats(self) -> dict:
        q = lambda sql: self.conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "headlines": q("SELECT COUNT(*) FROM headlines"),
            "tagged": q("SELECT COUNT(*) FROM headlines WHERE symbols != ''"),
            "checks_done": q("SELECT COUNT(*) FROM price_checks WHERE status='done'"),
            "checks_pending": q("SELECT COUNT(*) FROM price_checks WHERE status='pending'"),
            "checks_missed": q("SELECT COUNT(*) FROM price_checks WHERE status='missed'"),
        }

    def recent_tagged(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM headlines WHERE symbols != '' ORDER BY published_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def moves(self, limit: int = 20) -> list[sqlite3.Row]:
        """Raw % move from +0 to each later horizon, its benchmark's move, and the
        difference (the 'abnormal' move that might actually be due to the news)."""
        return self.conn.execute(
            """
            WITH pct AS (
                SELECT base.uid, base.symbol, base.role, base.benchmark, later.horizon_min,
                       100.0 * (later.price - base.price) / base.price AS pct
                FROM price_checks base
                JOIN price_checks later
                  ON later.uid = base.uid AND later.symbol = base.symbol
                 AND later.horizon_min > 0 AND later.status = 'done'
                WHERE base.horizon_min = 0 AND base.status = 'done'
            )
            SELECT h.title, h.source, h.sentiment, h.sentiment_score,
                   a.symbol, a.horizon_min, a.benchmark,
                   ROUND(a.pct, 3)          AS pct,
                   ROUND(b.pct, 3)          AS bench_pct,
                   ROUND(a.pct - b.pct, 3)  AS abnormal_pct
            FROM pct a
            JOIN headlines h ON h.uid = a.uid
            LEFT JOIN pct b
              ON b.uid = a.uid AND b.symbol = a.benchmark AND b.horizon_min = a.horizon_min
            WHERE a.role = 'asset'
            ORDER BY h.seen_at DESC, a.symbol, a.horizon_min
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def average_moves(self) -> list[sqlite3.Row]:
        """Average size of raw vs abnormal moves per horizon (needs benchmark data)."""
        return self.conn.execute(
            """
            WITH pct AS (
                SELECT base.uid, base.symbol, base.role, base.benchmark, later.horizon_min,
                       100.0 * (later.price - base.price) / base.price AS pct
                FROM price_checks base
                JOIN price_checks later
                  ON later.uid = base.uid AND later.symbol = base.symbol
                 AND later.horizon_min > 0 AND later.status = 'done'
                WHERE base.horizon_min = 0 AND base.status = 'done'
            )
            SELECT a.horizon_min, COUNT(*) AS n,
                   ROUND(AVG(ABS(a.pct)), 3)          AS avg_raw,
                   ROUND(AVG(ABS(a.pct - b.pct)), 3)  AS avg_abnormal
            FROM pct a JOIN pct b
              ON b.uid = a.uid AND b.symbol = a.benchmark AND b.horizon_min = a.horizon_min
            WHERE a.role = 'asset'
            GROUP BY a.horizon_min ORDER BY a.horizon_min
            """
        ).fetchall()

    def moves_by_sentiment(self) -> list[sqlite3.Row]:
        """The key research table: after positive / negative / neutral news,
        what was the average abnormal move? If sentiment is useful, positive
        news should show a positive average and negative news a negative one."""
        return self.conn.execute(
            """
            WITH pct AS (
                SELECT base.uid, base.symbol, base.role, base.benchmark, later.horizon_min,
                       100.0 * (later.price - base.price) / base.price AS pct
                FROM price_checks base
                JOIN price_checks later
                  ON later.uid = base.uid AND later.symbol = base.symbol
                 AND later.horizon_min > 0 AND later.status = 'done'
                WHERE base.horizon_min = 0 AND base.status = 'done'
            )
            SELECT h.sentiment, a.horizon_min, COUNT(*) AS n,
                   ROUND(AVG(a.pct - b.pct), 3) AS avg_abnormal
            FROM pct a
            JOIN pct b ON b.uid = a.uid AND b.symbol = a.benchmark AND b.horizon_min = a.horizon_min
            JOIN headlines h ON h.uid = a.uid
            WHERE a.role = 'asset' AND h.sentiment IS NOT NULL
            GROUP BY h.sentiment, a.horizon_min
            ORDER BY h.sentiment, a.horizon_min
            """
        ).fetchall()

    def ticker_counts(self, limit: int = 10) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for (symbols,) in self.conn.execute("SELECT symbols FROM headlines WHERE symbols != ''"):
            for s in symbols.split(","):
                counts[s] = counts.get(s, 0) + 1
        return sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
