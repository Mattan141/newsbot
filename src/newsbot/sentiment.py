"""Scores how positive or negative a headline is for the asset it mentions.

Two interchangeable scorers, so the rest of the bot doesn't care which is used:

- KeywordScorer: a hand-made list of finance words ("beats", "downgrade",
  "lays off"...). Instant, no download, easy to explain, but crude.
- FinBertScorer: FinBERT, an AI model trained on financial news
  (ProsusAI/finbert). Much better at context, needs a ~1 GB one-off install:
      pip install -r requirements-ml.txt

get_scorer() picks FinBERT if it's installed, otherwise the keyword list.
Comparing the two on the same headlines is a nice result for the write-up.

Every score is in [-1, +1]: -1 very negative, 0 neutral, +1 very positive.
"""
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Sentiment:
    label: str    # "positive", "negative" or "neutral"
    score: float  # -1.0 .. +1.0
    model: str    # which scorer produced it


def _label(score: float, threshold: float = 0.2) -> str:
    if score >= threshold:
        return "positive"
    if score <= -threshold:
        return "negative"
    return "neutral"


# ---- 1. Keyword scorer ------------------------------------------------------
POSITIVE = [
    r"beats?", r"beat estimates", r"tops? estimates", r"record (?:high|profit|revenue|sales)",
    r"raises? (?:guidance|forecast|outlook|dividend)", r"raises? price target",
    r"upgrades?", r"upgraded", r"outperform", r"buy rating", r"initiates? .*buy",
    r"surges?", r"soars?", r"jumps?", r"rises?", r"higher", r"rall(?:y|ies)", r"climbs?", r"gains?", r"rebounds?",
    r"approval", r"approved", r"clearance", r"wins?", r"secures?", r"lands?",
    r"buyback", r"partnership", r"deal", r"expands?", r"strong demand", r"profit rises?",
    r"snaps back",
]
NEGATIVE = [
    r"miss(?:es|ed)?", r"falls? short", r"cuts? (?:guidance|forecast|outlook|dividend|jobs)",
    r"lowers? (?:guidance|forecast|outlook)", r"lowers? price target",
    r"downgrades?", r"downgraded", r"underperform", r"sell rating",
    r"plunges?", r"plummets?", r"tumbles?", r"slumps?", r"sinks?", r"sinking", r"falls?", r"drops?",
    r"slides?", r"slips?", r"lower", r"losing streak", r"lays? off", r"layoffs?", r"job cuts",
    r"lawsuit", r"sues", r"sued", r"probe", r"investigation", r"fine[ds]?", r"penalty",
    r"recalls?", r"warns?", r"warning", r"bankruptcy", r"insolven\w*", r"default",
    r"hack(?:ed)?", r"cyber-?attack", r"breach", r"fraud", r"suspends?", r"delays?",
    r"shortage", r"concerns?", r"rescue talks", r"oppose",
]
NEGATIONS = r"(?:not|no|fails? to|failed to|without)"


def _compile(words: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(words) + r")\b", re.IGNORECASE)


_POS, _NEG = _compile(POSITIVE), _compile(NEGATIVE)
_NEGATED = re.compile(NEGATIONS + r"\s+(?:\w+\s+)?$", re.IGNORECASE)


class KeywordScorer:
    name = "keywords-v1"

    def score(self, text: str) -> Sentiment:
        pos = neg = 0
        for pattern, sign in ((_POS, 1), (_NEG, -1)):
            for m in pattern.finditer(text):
                # "fails to beat" -> the positive word counts as negative
                negated = bool(_NEGATED.search(text[: m.start()]))
                if (sign > 0) != negated:
                    pos += 1
                else:
                    neg += 1
        if pos + neg == 0:
            return Sentiment("neutral", 0.0, self.name)
        s = round((pos - neg) / (pos + neg), 3)
        return Sentiment(_label(s), s, self.name)


# ---- 2. FinBERT scorer ------------------------------------------------------
class FinBertScorer:
    name = "finbert"
    MODEL = "ProsusAI/finbert"

    def __init__(self, pipeline=None):
        if pipeline is None:  # imported here so the bot runs without it installed
            from transformers import pipeline as hf_pipeline
            pipeline = hf_pipeline("text-classification", model=self.MODEL, top_k=None)
        self._pipe = pipeline

    def score(self, text: str) -> Sentiment:
        result = self._pipe(text[:512])
        # pipeline returns [[{label, score}, ...]] for one input with top_k=None
        probs = {d["label"].lower(): d["score"] for d in (result[0] if isinstance(result[0], list) else result)}
        s = round(probs.get("positive", 0.0) - probs.get("negative", 0.0), 3)
        return Sentiment(_label(s), s, self.name)


def finbert_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def get_scorer():
    """FinBERT if installed (and not switched off with SENTIMENT=keywords)."""
    if os.getenv("SENTIMENT", "").lower() != "keywords" and finbert_available():
        try:
            return FinBertScorer()
        except Exception as exc:  # e.g. no internet for the first model download
            print(f"  [warn] FinBERT failed to load ({type(exc).__name__}); using keywords")
    return KeywordScorer()
