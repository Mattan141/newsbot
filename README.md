# NewsBot: a news-driven trading assistant

A Python bot that reads market news (and later, posts on X), works out which stocks or crypto a story affects, and paper-trades on it, with security and risk controls built in from day one.

> **Status:** Week 4 of 10: live news streaming and sentiment scoring (keywords, or FinBERT) measured against market-adjusted price moves.
> Paper trading only. Not financial advice.

## Why this project
Most hobby trading bots skip the hard parts. This one focuses on:
- **Honest evaluation:** every signal is backtested and measured after costs, including when it doesn't work.
- **Security first:** keys are never in code, live trading needs an explicit opt-in, and the bot is designed to resist spoofed or manipulative news.
- **Clean engineering:** small modules, tests, and a clear pipeline.

## Architecture
```
news / X  ──► ingest ──► understand (NLP) ──► decide ──► risk checks ──► broker (Alpaca)
                                                                 │
                                                         logs + backtests + dashboard
```

| Module | Does |
|---|---|
| `config.py` | Loads keys from `.env`, blocks live trading unless explicitly allowed |
| `broker.py` | Account, positions, orders (with a per-order dollar limit) |
| `market_data.py` | Latest stock and crypto prices |
| `news.py` | Alpaca news + UK/crypto RSS feeds, merged and de-duplicated |
| `watchlist.py` | The US, UK and crypto assets tracked, and the names that identify them |
| `tagger.py` | Matches each headline to assets (source tags + names + $cashtags) |
| `storage.py` | SQLite database of headlines and post-news price checks |
| `collector.py` | Pipeline: fetch → tag → score → store → schedule price checks at +0/5/30/60 min (+ SPY/BTC benchmark) |
| `sentiment.py` | Pluggable sentiment: keyword lexicon, or FinBERT if installed |
| `news_stream.py` | Live Alpaca news over a websocket, in a background thread |

## Setup
1. Make a free account at [alpaca.markets](https://alpaca.markets), switch to **Paper Trading**, and generate API keys.
2. In VS Code, open this folder, then in the terminal:
   ```bash
   python -m venv .venv
   # Windows:      .venv\Scripts\activate
   # Mac / Linux:  source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and paste your paper keys in.
4. Optional, better sentiment (~1–1.5 GB): `pip install -r requirements-ml.txt`

## Run it
```bash
python scripts/check_account.py               # does my connection work?
python scripts/get_prices.py AAPL BTC/USD     # latest prices
python scripts/place_trade.py BTC/USD 50      # buy $50 of BTC (paper)
python scripts/fetch_news.py TSLA             # recent headlines
python scripts/collect.py --loop              # live news + sentiment + price tracking (Ctrl+C to stop)
python scripts/score_news.py --try "Apple beats estimates"   # test the sentiment model
python scripts/show_db.py                     # what's been collected so far
pytest                                        # run the tests
```

## Roadmap
- [x] Weeks 1–2: broker connection, prices, paper orders, news ingestion
- [x] Week 3: match headlines to tickers (US, UK, crypto), SQLite storage, post-news price tracking
- [x] Week 3.5: market benchmark (abnormal returns), data-quality checks (after-hours quotes, wide spreads)
- [x] Week 4: live news streaming, sentiment scoring (keywords / FinBERT)
- [ ] Week 5: strategy and risk engine, autonomous paper trading
- [ ] Week 6: Trading 212 demo as a UK broker, LSE RNS announcements
- [ ] Weeks 9–10: backtesting, results dashboard, security threat model
- [ ] Later: X/Twitter watchlist, spoofed-news detection
