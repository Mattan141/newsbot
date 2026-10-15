"""The assets the bot cares about, and the names that identify them in headlines.

Edit this list freely: add a company by adding one line.

- market "US" and "CRYPTO" can be priced and traded through Alpaca.
- market "UK" (London Stock Exchange) is tagged and stored for now. Pricing and
  trading UK shares comes later via a second broker (Trading 212 demo).

Names are matched case-sensitively as whole words, because headlines capitalise
company names. That stops "Apple" matching "pineapple" and "Shell" matching
"a shell company"... mostly. Ambiguous names are left out on purpose.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Asset:
    symbol: str
    market: str  # "US", "CRYPTO" or "UK"
    names: tuple[str, ...]

    @property
    def tradable(self) -> bool:
        return self.market in ("US", "CRYPTO")


WATCHLIST: list[Asset] = [
    # --- US stocks ---
    Asset("AAPL", "US", ("Apple", "iPhone", "Tim Cook")),
    Asset("MSFT", "US", ("Microsoft", "Satya Nadella")),
    Asset("NVDA", "US", ("Nvidia", "NVIDIA", "Jensen Huang")),
    Asset("TSLA", "US", ("Tesla", "Elon Musk", "Musk")),
    Asset("AMZN", "US", ("Amazon", "AWS", "Andy Jassy")),
    Asset("GOOGL", "US", ("Google", "Alphabet", "Sundar Pichai")),
    Asset("META", "US", ("Meta", "Facebook", "Instagram", "Zuckerberg")),
    Asset("NFLX", "US", ("Netflix",)),
    Asset("AMD", "US", ("AMD",)),
    Asset("JPM", "US", ("JPMorgan", "JP Morgan", "Jamie Dimon")),
    Asset("COIN", "US", ("Coinbase",)),
    # --- Crypto ---
    Asset("BTC/USD", "CRYPTO", ("Bitcoin", "bitcoin", "BTC")),
    Asset("ETH/USD", "CRYPTO", ("Ethereum", "ethereum", "Ether", "ether", "ETH")),
    Asset("SOL/USD", "CRYPTO", ("Solana", "solana")),
    Asset("XRP/USD", "CRYPTO", ("XRP", "Ripple")),
    Asset("DOGE/USD", "CRYPTO", ("Dogecoin", "dogecoin")),
    # --- UK (London Stock Exchange) ---
    Asset("BARC.L", "UK", ("Barclays",)),
    Asset("HSBA.L", "UK", ("HSBC",)),
    Asset("LLOY.L", "UK", ("Lloyds Banking", "Lloyds Bank", "Lloyds")),
    Asset("NWG.L", "UK", ("NatWest",)),
    Asset("BP.L", "UK", ("BP",)),
    Asset("SHEL.L", "UK", ("Shell plc", "Royal Dutch Shell")),
    Asset("AZN.L", "UK", ("AstraZeneca",)),
    Asset("GSK.L", "UK", ("GSK", "GlaxoSmithKline")),
    Asset("ULVR.L", "UK", ("Unilever",)),
    Asset("TSCO.L", "UK", ("Tesco",)),
    Asset("SBRY.L", "UK", ("Sainsbury's", "Sainsbury")),
    Asset("RR.L", "UK", ("Rolls-Royce",)),
    Asset("BA.L", "UK", ("BAE Systems",)),
    Asset("VOD.L", "UK", ("Vodafone",)),
    Asset("BT-A.L", "UK", ("BT Group", "BT")),
    Asset("RIO.L", "UK", ("Rio Tinto",)),
    Asset("IAG.L", "UK", ("British Airways", "IAG")),
    Asset("MKS.L", "UK", ("Marks & Spencer", "Marks and Spencer", "M&S")),
    Asset("JD.L", "UK", ("JD Sports",)),
]

BY_SYMBOL: dict[str, Asset] = {a.symbol: a for a in WATCHLIST}

# Alpaca's news API writes crypto as "BTCUSD"; we use "BTC/USD" everywhere else.
ALPACA_ALIASES: dict[str, str] = {
    a.symbol.replace("/", ""): a.symbol for a in WATCHLIST if a.market == "CRYPTO"
}
