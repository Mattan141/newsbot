"""Step 3: place one small PAPER trade, to prove orders work.

Usage:  python scripts/place_trade.py BTC/USD 50        (buy $50 of Bitcoin)
        python scripts/place_trade.py AAPL 100 sell     (sell $100 of Apple)

Crypto trades 24/7. Stock orders placed outside US market hours
(14:30-21:00 UK time, weekdays) wait in the queue until the market opens.
"""
import sys

import _setup_path  # noqa: F401
from newsbot.broker import Broker
from newsbot.config import load_settings

if len(sys.argv) < 3:
    sys.exit(__doc__)

symbol, amount = sys.argv[1].upper(), float(sys.argv[2])
side = sys.argv[3] if len(sys.argv) > 3 else "buy"

broker = Broker(load_settings())
assert broker.paper, "This script only runs in paper mode."

order = broker.place_market_order(symbol, amount, side)
print(f"Submitted {side.upper()} ${amount:,.2f} of {symbol}")
print(f"Order ID: {order.id}")
print(f"Status:   {order.status}")
