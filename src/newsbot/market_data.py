"""Latest prices for stocks and crypto, using Alpaca's free market data."""
from alpaca.data.enums import DataFeed
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest, StockLatestQuoteRequest

from newsbot.config import Settings


class MarketData:
    def __init__(self, settings: Settings):
        self.stocks = StockHistoricalDataClient(settings.api_key, settings.secret_key)
        # Crypto data doesn't need keys, but passing them gives higher rate limits.
        self.crypto = CryptoHistoricalDataClient(settings.api_key, settings.secret_key)

    def latest_prices(self, symbols: list[str]) -> dict[str, float]:
        """Return the midpoint of the latest bid/ask for each symbol."""
        crypto = [s for s in symbols if "/" in s]
        stocks = [s for s in symbols if "/" not in s]
        quotes = {}

        if stocks:
            # IEX is the free data feed. It's fine for learning; real bots pay for SIP.
            req = StockLatestQuoteRequest(symbol_or_symbols=stocks, feed=DataFeed.IEX)
            quotes.update(self.stocks.get_stock_latest_quote(req))
        if crypto:
            req = CryptoLatestQuoteRequest(symbol_or_symbols=crypto)
            quotes.update(self.crypto.get_crypto_latest_quote(req))

        return {sym: _midpoint(q.bid_price, q.ask_price) for sym, q in quotes.items()}


def _midpoint(bid: float, ask: float) -> float:
    # Outside market hours one side of the quote can be 0, so fall back to the other.
    if bid and ask:
        return round((bid + ask) / 2, 4)
    return round(bid or ask or 0.0, 4)
