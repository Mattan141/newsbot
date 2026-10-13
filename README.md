# NewsBot: a news-driven trading assistant

A Python bot that reads market news (and later, posts on X), works out which stocks or crypto a story affects, and paper-trades on it, with security and risk controls built in from day one.

> **Status:** Week 1 of 10: broker connection, prices, paper orders and news ingestion.
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
| `news.py` | Alpaca news + RSS feeds, merged and de-duplicated |

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

## Run it
```bash
python scripts/check_account.py               # does my connection work?
python scripts/get_prices.py AAPL BTC/USD     # latest prices
python scripts/place_trade.py BTC/USD 50      # buy $50 of BTC (paper)
python scripts/fetch_news.py TSLA             # recent headlines
pytest                                        # run the tests
```

## Roadmap
- [x] Weeks 1–2: broker connection, prices, paper orders, news ingestion
- [ ] Weeks 3–4: match headlines to tickers, store news in a database
- [ ] Weeks 5–6: sentiment and event classification (FinBERT / LLM)
- [ ] Weeks 7–8: strategy and risk engine, autonomous paper trading
- [ ] Weeks 9–10: backtesting, results dashboard, security threat model
- [ ] Later: X/Twitter watchlist, spoofed-news detection
