"""Step 2: latest prices for a mix of stocks and crypto.

Usage:  python scripts/get_prices.py AAPL TSLA BTC/USD ETH/USD
"""
import sys

import _setup_path  # noqa: F401
from newsbot.config import load_settings
from newsbot.market_data import MarketData

symbols = sys.argv[1:] or ["AAPL", "TSLA", "NVDA", "BTC/USD", "ETH/USD"]
prices = MarketData(load_settings()).latest_prices(symbols)

for sym in symbols:
    price = prices.get(sym)
    print(f"{sym:<10} {'$' + format(price, ',.2f') if price else 'no quote'}")
