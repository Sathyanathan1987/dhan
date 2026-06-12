"""
Configuration loader for the NIFTY 50 Open Tracker.
Reads credentials and settings from .env file or environment variables.
"""
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    client_id: str
    access_token: str
    nifty_security_id: str = "13"
    exchange_segment: int = 0   # Will be set to MarketFeed.IDX_I at runtime
    reconnect_enabled: bool = True
    max_retries: int = 3
    retry_interval_sec: int = 5
    health_check_interval_sec: int = 30
    stale_feed_threshold_sec: int = 30


def load_config() -> AppConfig:
    """
    Load application configuration from .env file and environment variables.
    
    Raises ConfigError (and exits with code 1) if required credentials are
    missing or blank/whitespace-only.
    """
    # Search for .env in: this file's directory, then its parent (project root)
    _this_dir = Path(__file__).parent
    _env_file = _this_dir / ".env"
    if not _env_file.exists():
        _env_file = _this_dir.parent / ".env"
    load_dotenv(dotenv_path=_env_file, override=False)

    client_id = os.environ.get("DHAN_CLIENT_ID", "").strip()
    access_token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()

    if not client_id:
        msg = "DHAN_CLIENT_ID is missing or blank. Set it in your .env file or environment."
        logger.error(msg)
        sys.exit(1)

    if not access_token:
        msg = "DHAN_ACCESS_TOKEN is missing or blank. Set it in your .env file or environment."
        logger.error(msg)
        sys.exit(1)

    def _bool(key: str, default: bool) -> bool:
        val = os.environ.get(key, "").strip().lower()
        if val in ("true", "1", "yes"):
            return True
        if val in ("false", "0", "no"):
            return False
        return default

    def _int(key: str, default: int) -> int:
        val = os.environ.get(key, "").strip()
        try:
            return int(val) if val else default
        except ValueError:
            return default

    return AppConfig(
        client_id=client_id,
        access_token=access_token,
        nifty_security_id=os.environ.get("NIFTY_SECURITY_ID", "13").strip() or "13",
        reconnect_enabled=_bool("RECONNECT_ENABLED", True),
        max_retries=_int("MAX_RETRIES", 3),
        retry_interval_sec=_int("RETRY_INTERVAL_SEC", 5),
        health_check_interval_sec=_int("HEALTH_CHECK_INTERVAL_SEC", 30),
        stale_feed_threshold_sec=_int("STALE_FEED_THRESHOLD_SEC", 30),
    )
