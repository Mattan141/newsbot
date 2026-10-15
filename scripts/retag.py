"""Re-apply the latest tagging rules to everything already in the database.

Run this after the tagger is improved, so old headlines get fixed too.

Usage:  python scripts/retag.py
"""
import _setup_path  # noqa: F401
from newsbot.collector import retag_all
from newsbot.storage import Store

counts = retag_all(Store())
print(f"Headlines re-tagged:   {counts['retagged']}")
print(f"Price checks removed:  {counts['checks_removed']}  (wrong asset or round-up article)")
