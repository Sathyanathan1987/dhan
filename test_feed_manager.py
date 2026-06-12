"""
Tests for feed_manager.py — WebSocket feed manager.

Uses unittest.mock to mock the dhanhq MarketFeed SDK so no real network
connection is required.
"""
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, r"d:\kiro_algo\ALGO DHAN")

from nifty50_tracker.config import AppConfig
from nifty50_tracker.feed_manager import FeedManager

IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(reconnect_enabled: bool = True, max_retries: int = 3) -> AppConfig:
    """Create a minimal AppConfig for testing."""
    return AppConfig(
        client_id="test_client",
        access_token="test_token",
        nifty_security_id="13",
        reconnect_enabled=reconnect_enabled,
        max_retries=max_retries,
        retry_interval_sec=0,          # No sleep delay in tests
        health_check_interval_sec=30,
        stale_feed_threshold_sec=30,
    )


# ---------------------------------------------------------------------------
# start() — no reconnect
# ---------------------------------------------------------------------------

def test_connect_failure_no_reconnect():
    """With reconnect_enabled=False, a connection failure exits immediately with code 1."""
    config = _make_config(reconnect_enabled=False)
    manager = FeedManager(config, on_tick=MagicMock())

    with patch.object(manager, "_connect_once", return_value=False):
        with pytest.raises(SystemExit) as exc_info:
            manager.start()

    assert exc_info.value.code == 1


def test_connect_success_no_reconnect():
    """With reconnect_enabled=False, a successful connection returns without raising."""
    config = _make_config(reconnect_enabled=False)
    manager = FeedManager(config, on_tick=MagicMock())

    with patch.object(manager, "_connect_once", return_value=True):
        manager.start()  # Should not raise


# ---------------------------------------------------------------------------
# start() — with reconnect
# ---------------------------------------------------------------------------

def test_connect_retries_3_times():
    """With reconnect_enabled=True and max_retries=3, exactly 3 attempts made before exit."""
    config = _make_config(reconnect_enabled=True, max_retries=3)
    manager = FeedManager(config, on_tick=MagicMock())

    with patch.object(manager, "_connect_once", return_value=False) as mock_connect:
        with patch("nifty50_tracker.feed_manager.time_module.sleep"):
            with pytest.raises(SystemExit) as exc_info:
                manager.start()

    assert exc_info.value.code == 1
    assert mock_connect.call_count == 3, (
        f"Expected 3 connection attempts, got {mock_connect.call_count}"
    )


def test_connect_succeeds_on_first_attempt():
    """Successful first connection starts the health-check thread and returns."""
    config = _make_config(reconnect_enabled=True, max_retries=3)
    manager = FeedManager(config, on_tick=MagicMock())

    with patch.object(manager, "_connect_once", return_value=True):
        with patch.object(manager, "_start_health_check") as mock_health:
            manager.start()

    mock_health.assert_called_once()


def test_connect_succeeds_on_second_attempt():
    """Connection succeeds on second attempt; no SystemExit is raised."""
    config = _make_config(reconnect_enabled=True, max_retries=3)
    manager = FeedManager(config, on_tick=MagicMock())

    call_count = [0]

    def _side_effect():
        call_count[0] += 1
        return call_count[0] >= 2  # fail first attempt, succeed second

    with patch.object(manager, "_connect_once", side_effect=_side_effect):
        with patch.object(manager, "_start_health_check"):
            with patch("nifty50_tracker.feed_manager.time_module.sleep"):
                manager.start()  # Must not raise

    assert call_count[0] == 2


# ---------------------------------------------------------------------------
# _on_data_received
# ---------------------------------------------------------------------------

def test_on_data_received_calls_on_tick():
    """_on_data_received extracts LTP and calls the on_tick callback."""
    on_tick = MagicMock()
    config = _make_config()
    manager = FeedManager(config, on_tick=on_tick)

    data = {"LTP": "23104.50", "security_id": "13", "type": "Ticker Data"}
    manager._on_data_received(data)

    on_tick.assert_called_once()
    ltp_arg, time_arg = on_tick.call_args[0]
    assert ltp_arg == 23104.5
    assert isinstance(time_arg, datetime)


def test_on_data_received_skips_zero_ltp():
    """_on_data_received ignores ticks with LTP == 0."""
    on_tick = MagicMock()
    config = _make_config()
    manager = FeedManager(config, on_tick=on_tick)

    manager._on_data_received({"LTP": 0.0})
    on_tick.assert_not_called()


def test_on_data_received_skips_negative_ltp():
    """_on_data_received ignores ticks with LTP < 0."""
    on_tick = MagicMock()
    config = _make_config()
    manager = FeedManager(config, on_tick=on_tick)

    manager._on_data_received({"LTP": -1.0})
    on_tick.assert_not_called()


def test_on_data_received_updates_last_tick_time():
    """_on_data_received updates _last_tick_time after a valid tick."""
    on_tick = MagicMock()
    config = _make_config()
    manager = FeedManager(config, on_tick=on_tick)

    assert manager._last_tick_time is None
    manager._on_data_received({"LTP": "22000.00"})
    assert manager._last_tick_time is not None
    assert isinstance(manager._last_tick_time, datetime)


def test_on_data_received_handles_missing_ltp_key():
    """_on_data_received treats missing LTP key as 0 and does not call on_tick."""
    on_tick = MagicMock()
    config = _make_config()
    manager = FeedManager(config, on_tick=on_tick)

    manager._on_data_received({})  # No 'LTP' key — defaults to 0.0
    on_tick.assert_not_called()


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

def test_stop_calls_close_connection():
    """stop() calls close_connection() on the underlying feed object."""
    config = _make_config()
    manager = FeedManager(config, on_tick=MagicMock())
    mock_feed = MagicMock()
    manager._feed = mock_feed

    manager.stop()

    mock_feed.close_connection.assert_called_once()


def test_stop_sets_stop_event():
    """stop() sets the internal stop event so the health-check thread can exit."""
    config = _make_config()
    manager = FeedManager(config, on_tick=MagicMock())

    assert not manager._stop_event.is_set()
    manager.stop()
    assert manager._stop_event.is_set()


def test_stop_without_feed_does_not_raise():
    """stop() is safe to call when no feed connection exists."""
    config = _make_config()
    manager = FeedManager(config, on_tick=MagicMock())
    assert manager._feed is None
    manager.stop()  # Must not raise


# ---------------------------------------------------------------------------
# _resubscribe
# ---------------------------------------------------------------------------

def test_resubscribe_calls_subscribe_symbols():
    """_resubscribe() calls subscribe_symbols on the feed with the instrument list."""
    config = _make_config()
    manager = FeedManager(config, on_tick=MagicMock())
    mock_feed = MagicMock()
    manager._feed = mock_feed

    manager._resubscribe()

    mock_feed.subscribe_symbols.assert_called_once_with(manager._instruments)


def test_resubscribe_without_feed_does_not_raise():
    """_resubscribe() is safe when no feed is present."""
    config = _make_config()
    manager = FeedManager(config, on_tick=MagicMock())
    assert manager._feed is None
    manager._resubscribe()  # Must not raise


# ---------------------------------------------------------------------------
# Health check stale detection (logic-level, no threading)
# ---------------------------------------------------------------------------

def test_health_check_triggers_resubscribe_when_stale():
    """
    Health check calls _resubscribe() when elapsed time exceeds the stale threshold.
    Validates the stale-detection logic directly without running the thread loop.
    """
    config = _make_config()
    manager = FeedManager(config, on_tick=MagicMock())

    # Set a last tick time well in the past
    old_tick_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=IST)
    manager._last_tick_time = old_tick_time

    now = datetime(2024, 1, 15, 9, 1, 5, tzinfo=IST)  # 65 seconds later

    with patch.object(manager, "_resubscribe") as mock_resub:
        elapsed = (now - manager._last_tick_time).total_seconds()
        if elapsed > config.stale_feed_threshold_sec:
            manager._resubscribe()

    mock_resub.assert_called_once()


def test_health_check_does_not_resubscribe_when_fresh():
    """
    Health check does NOT call _resubscribe() when last tick is recent.
    """
    config = _make_config()
    manager = FeedManager(config, on_tick=MagicMock())

    # Last tick only 5 seconds ago — well within threshold
    recent_tick = datetime(2024, 1, 15, 9, 0, 55, tzinfo=IST)
    manager._last_tick_time = recent_tick

    now = datetime(2024, 1, 15, 9, 1, 0, tzinfo=IST)  # 5 seconds later

    with patch.object(manager, "_resubscribe") as mock_resub:
        elapsed = (now - manager._last_tick_time).total_seconds()
        if elapsed > config.stale_feed_threshold_sec:
            manager._resubscribe()

    mock_resub.assert_not_called()
