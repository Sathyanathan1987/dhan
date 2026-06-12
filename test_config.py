"""
Tests for config.py — configuration loader and credential validation.

Includes:
- Property test: whitespace credentials are always rejected (Property 1)
- Unit tests: valid config, missing fields, defaults
"""
import string
import sys
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure the package is importable
sys.path.insert(0, r"d:\kiro_algo\ALGO DHAN")

from nifty50_tracker.config import AppConfig, ConfigError, load_config


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------

# Feature: nifty50-open-tracker, Property 1: Whitespace credentials are always rejected
@given(st.text(alphabet=string.whitespace, min_size=0))
@settings(max_examples=200)
def test_whitespace_client_id_rejected(whitespace_str):
    """Any whitespace-only (or empty) client_id must trigger sys.exit(1)."""
    env = {
        "DHAN_CLIENT_ID": whitespace_str,
        "DHAN_ACCESS_TOKEN": "valid_token",
    }
    with patch.dict("os.environ", env, clear=True):
        with patch("nifty50_tracker.config.load_dotenv"):
            with pytest.raises(SystemExit) as exc_info:
                load_config()
    assert exc_info.value.code == 1


# Feature: nifty50-open-tracker, Property 1: Whitespace credentials are always rejected
@given(st.text(alphabet=string.whitespace, min_size=0))
@settings(max_examples=200)
def test_whitespace_access_token_rejected(whitespace_str):
    """Any whitespace-only (or empty) access_token must trigger sys.exit(1)."""
    env = {
        "DHAN_CLIENT_ID": "valid_client",
        "DHAN_ACCESS_TOKEN": whitespace_str,
    }
    with patch.dict("os.environ", env, clear=True):
        with patch("nifty50_tracker.config.load_dotenv"):
            with pytest.raises(SystemExit) as exc_info:
                load_config()
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_load_config_valid():
    """Valid credentials produce an AppConfig with correct values."""
    env = {
        "DHAN_CLIENT_ID": "1000012345",
        "DHAN_ACCESS_TOKEN": "eyJhbGciOiJIUzI1NiJ9.test",
    }
    with patch.dict("os.environ", env, clear=True):
        with patch("nifty50_tracker.config.load_dotenv"):
            cfg = load_config()
    assert cfg.client_id == "1000012345"
    assert cfg.access_token == "eyJhbGciOiJIUzI1NiJ9.test"


def test_load_config_missing_client_id():
    """Missing DHAN_CLIENT_ID exits with code 1."""
    env = {"DHAN_ACCESS_TOKEN": "valid_token"}
    with patch.dict("os.environ", env, clear=True):
        with patch("nifty50_tracker.config.load_dotenv"):
            with pytest.raises(SystemExit) as exc_info:
                load_config()
    assert exc_info.value.code == 1


def test_load_config_missing_access_token():
    """Missing DHAN_ACCESS_TOKEN exits with code 1."""
    env = {"DHAN_CLIENT_ID": "valid_client"}
    with patch.dict("os.environ", env, clear=True):
        with patch("nifty50_tracker.config.load_dotenv"):
            with pytest.raises(SystemExit) as exc_info:
                load_config()
    assert exc_info.value.code == 1


def test_load_config_defaults():
    """Optional fields fall back to designed defaults when not set."""
    env = {
        "DHAN_CLIENT_ID": "client",
        "DHAN_ACCESS_TOKEN": "token",
    }
    with patch.dict("os.environ", env, clear=True):
        with patch("nifty50_tracker.config.load_dotenv"):
            cfg = load_config()
    assert cfg.nifty_security_id == "13"
    assert cfg.reconnect_enabled is True
    assert cfg.max_retries == 3
    assert cfg.retry_interval_sec == 5
    assert cfg.health_check_interval_sec == 30
    assert cfg.stale_feed_threshold_sec == 30


def test_load_config_custom_values():
    """Custom env var values override defaults."""
    env = {
        "DHAN_CLIENT_ID": "client",
        "DHAN_ACCESS_TOKEN": "token",
        "MAX_RETRIES": "5",
        "RECONNECT_ENABLED": "false",
        "RETRY_INTERVAL_SEC": "10",
    }
    with patch.dict("os.environ", env, clear=True):
        with patch("nifty50_tracker.config.load_dotenv"):
            cfg = load_config()
    assert cfg.max_retries == 5
    assert cfg.reconnect_enabled is False
    assert cfg.retry_interval_sec == 10
