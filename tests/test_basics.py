"""Run with:  pytest
These tests need no API keys or internet, so they're safe to run anywhere."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from newsbot.config import ConfigError, load_settings  # noqa: E402
from newsbot.market_data import _midpoint  # noqa: E402
from newsbot.news import Headline, merge_and_dedupe  # noqa: E402


def _h(title, hour, source="x"):
    return Headline(source, title, "", datetime(2026, 10, 12, hour, tzinfo=timezone.utc))


def test_dedupe_ignores_case_and_sorts_newest_first():
    out = merge_and_dedupe([_h("Fed holds rates", 9)], [_h("FED HOLDS RATES ", 10), _h("Oil jumps", 11)])
    assert [h.title for h in out] == ["Oil jumps", "Fed holds rates"]


def test_midpoint_handles_missing_side():
    assert _midpoint(100, 102) == 101
    assert _midpoint(0, 50) == 50


def test_missing_keys_raise(monkeypatch):
    monkeypatch.setattr("newsbot.config.load_dotenv", lambda: None)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        load_settings()


def test_live_trading_blocked_without_opt_in(monkeypatch):
    monkeypatch.setattr("newsbot.config.load_dotenv", lambda: None)
    monkeypatch.setenv("ALPACA_API_KEY", "abc")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "def")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "no")
    with pytest.raises(ConfigError):
        load_settings(want_live=True)
    assert load_settings().paper is True
