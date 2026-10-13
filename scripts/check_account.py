"""Step 1: prove your keys work. Prints your paper account balance and positions."""
import _setup_path  # noqa: F401
from newsbot.broker import Broker
from newsbot.config import load_settings

broker = Broker(load_settings())
summary = broker.account_summary()

print(f"Mode:          {summary['mode']}")
print(f"Status:        {summary['status']}")
print(f"Cash:          ${summary['cash']:,.2f}")
print(f"Equity:        ${summary['equity']:,.2f}")
print(f"Buying power:  ${summary['buying_power']:,.2f}")

positions = broker.positions()
print(f"\nOpen positions: {len(positions)}")
for p in positions:
    print(f"  {p['symbol']:<10} qty={p['qty']:<10g} value=${p['market_value']:,.2f}  P/L=${p['unrealized_pl']:,.2f}")
