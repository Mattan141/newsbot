"""Thin wrapper around Alpaca's trading API: account info, positions and orders.

Every order goes through `place_market_order`, which runs basic safety checks first.
Later we'll replace those checks with a proper risk module.
"""
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from newsbot.config import Settings

# Hard limit for now: no single order bigger than this many dollars (notional).
MAX_ORDER_USD = 1_000


class Broker:
    def __init__(self, settings: Settings):
        self.paper = settings.paper
        self.client = TradingClient(settings.api_key, settings.secret_key, paper=settings.paper)

    def account_summary(self) -> dict:
        acc = self.client.get_account()
        return {
            "status": str(acc.status),
            "mode": "PAPER" if self.paper else "LIVE",
            "cash": float(acc.cash),
            "equity": float(acc.equity),
            "buying_power": float(acc.buying_power),
        }

    def positions(self) -> list[dict]:
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
            }
            for p in self.client.get_all_positions()
        ]

    def place_market_order(self, symbol: str, usd_amount: float, side: str = "buy"):
        """Buy or sell `usd_amount` dollars' worth of `symbol` at market price.

        Crypto symbols look like "BTC/USD"; stocks look like "AAPL".
        """
        if usd_amount <= 0:
            raise ValueError("Order amount must be positive.")
        if usd_amount > MAX_ORDER_USD:
            raise ValueError(f"Order of ${usd_amount} is above the ${MAX_ORDER_USD} safety limit.")

        is_crypto = "/" in symbol
        request = MarketOrderRequest(
            symbol=symbol,
            notional=round(usd_amount, 2),
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            # Crypto trades 24/7 and needs GTC; fractional stock orders need DAY.
            time_in_force=TimeInForce.GTC if is_crypto else TimeInForce.DAY,
        )
        return self.client.submit_order(request)
