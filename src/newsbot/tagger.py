"""Works out which assets a headline is about.

Two signals are combined:
1. Tags the source already supplied (Alpaca news comes pre-tagged).
2. Our own matching of watchlist names and $CASHTAGS in the headline text.

This is deliberately simple keyword matching. In weeks 5-6 we add an NLP model
on top, and comparing the two is a nice thing to show in the write-up.
"""
import re

from newsbot.news import Headline
from newsbot.watchlist import ALPACA_ALIASES, BY_SYMBOL, WATCHLIST

# One compiled regex per asset: any of its names as a whole word.
_PATTERNS = [
    (asset.symbol, re.compile(r"(?<![\w&])(?:" + "|".join(re.escape(n) for n in asset.names) + r")(?![\w&])"))
    for asset in WATCHLIST
]
_CASHTAG = re.compile(r"\$([A-Za-z]{1,5})\b")


def match_text(text: str) -> set[str]:
    """Return watchlist symbols mentioned in a piece of text."""
    found = {symbol for symbol, pattern in _PATTERNS if pattern.search(text)}
    for tag in _CASHTAG.findall(text):
        tag = tag.upper()
        if tag in BY_SYMBOL:
            found.add(tag)
        elif f"{tag}/USD" in BY_SYMBOL:  # $BTC -> BTC/USD
            found.add(f"{tag}/USD")
    return found


def normalise_source_tags(symbols: list[str]) -> set[str]:
    """Convert a source's own tags into our format (e.g. Alpaca 'BTCUSD' -> 'BTC/USD')."""
    return {ALPACA_ALIASES.get(s, s) for s in symbols}


# Analyst headlines name two companies: the bank doing the rating and the company
# being rated. "JP Morgan Maintains Overweight on Moody's" is news about Moody's,
# not JPMorgan, so the firm in front of the verb must not be tagged.
_ANALYST_ACTION = re.compile(
    r"^(?P<firm>.+?)\s+(?:Maintains|Reiterates|Upgrades|Downgrades|Initiates|Assumes|"
    r"Resumes|Reinstates|Raises|Lowers|Cuts|Boosts)\b.*?\s(?:on|to)\s+(?P<subject>.+)$"
)


def analyst_firm_symbols(title: str) -> set[str]:
    """Symbols that only appear as the *rating firm* in an analyst headline."""
    m = _ANALYST_ACTION.match(title)
    if not m:
        return set()
    return match_text(m.group("firm")) - match_text(m.group("subject"))


def tag_headline(h: Headline) -> list[str]:
    """Final, sorted list of symbols for a headline (source tags + our matches)."""
    symbols = normalise_source_tags(h.symbols) | match_text(h.title)
    return sorted(symbols - analyst_firm_symbols(h.title))
