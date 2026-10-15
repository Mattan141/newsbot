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

    def latest_prices(self, symbols: list[str], strict: bool = False) -> dict[str, float]:
        """Return the midpoint of the latest bid/ask for each symbol.

        strict=True is for research data: a quote with a missing side or a wide
        bid/ask spread (common after the market closes) gives 0.0 = "no reliable
        price", instead of a misleading number.
        """
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

        pick = reliable_midpoint if strict else _midpoint
        return {sym: pick(q.bid_price, q.ask_price) for sym, q in quotes.items()}


def _midpoint(bid: float, ask: float) -> float:
    # Outside market hours one side of the quote can be 0, so fall back to the other.
    if bid and ask:
        return round((bid + ask) / 2, 4)
    return round(bid or ask or 0.0, 4)


# A spread wider than this means the quote is thin or stale (e.g. after hours).
MAX_SPREAD_PCT = 0.5


def reliable_midpoint(bid: float, ask: float, max_spread_pct: float = MAX_SPREAD_PCT) -> float:
    """Midpoint only if both sides exist and the spread is tight; otherwise 0.0."""
    if not bid or not ask or ask < bid:
        return 0.0
    mid = (bid + ask) / 2
    if 100 * (ask - bid) / mid > max_spread_pct:
        return 0.0
    return round(mid, 4)
