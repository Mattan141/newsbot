"""Add sentiment scores to headlines already in the database.

Usage:
    python scripts/score_news.py            score headlines that don't have one yet
    python scripts/score_news.py --all      re-score everything (e.g. after installing FinBERT)
    python scripts/score_news.py --try "Apple beats estimates"   test one headline
"""
import sys
import time

import _setup_path  # noqa: F401
from newsbot.collector import score_existing
from newsbot.sentiment import get_scorer
from newsbot.storage import Store

scorer = get_scorer()
print(f"Sentiment model: {scorer.name}")

if "--try" in sys.argv:
    text = " ".join(sys.argv[sys.argv.index("--try") + 1:])
    s = scorer.score(text)
    print(f"{s.label:>8}  {s.score:+.2f}   {text}")
    sys.exit()

start = time.time()
n = score_existing(Store(), scorer, rescore="--all" in sys.argv)
print(f"Scored {n} headlines in {time.time() - start:.1f}s")
