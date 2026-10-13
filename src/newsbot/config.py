"""Loads settings from the .env file and keeps the bot in paper mode by default.

Security notes (worth mentioning in interviews):
- Keys live in environment variables, never in code, so they can't leak via GitHub.
- Live trading needs an explicit opt-in. A mistake can't silently spend real money.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when the settings are missing or unsafe."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    secret_key: str
    paper: bool


def load_settings(want_live: bool = False) -> Settings:
    load_dotenv()

    api_key = os.getenv("ALPACA_API_KEY", "").strip()
    secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()

    if not api_key or not secret_key or "your_" in api_key:
        raise ConfigError(
            "Alpaca keys not found. Copy .env.example to .env and paste your PAPER keys in."
        )

    if want_live and os.getenv("ALLOW_LIVE_TRADING", "no").lower() != "yes":
        raise ConfigError(
            "Live trading requested but ALLOW_LIVE_TRADING is not 'yes'. Refusing."
        )

    return Settings(api_key=api_key, secret_key=secret_key, paper=not want_live)
