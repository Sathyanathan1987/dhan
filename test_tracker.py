"""
Tests for tracker.py — session orchestrator.
Uses unittest.mock to avoid live network calls.
"""
import signal
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, r"d:\kiro_algo\ALGO DHAN")

from nifty50_tracker.config import AppConfig
from nifty50_tracker.tracker import Tracker

IST = ZoneInfo("Asia/Kolkata")


def _make_config() -> AppConfig:
    return AppConfig(
        client_id="test_client",
        access_token="test_token",
        nifty_security_id="13",
        reconnect_enabled=False,
        max_retries=1,
        retry_interval_sec=0,
        health_check_interval_sec=30,
        stale_feed_threshold_sec=30,
    )


def test_shutdown_sets_event_and_stops_feed():
    """shutdown() sets the shutdown event and calls feed.stop()."""
    config = _make_config()
    tracker = Tracker(config)
    tracker.feed = MagicMock()

    tracker.shutdown()

    assert tracker._shutdown_event.is_set()
    tracker.feed.stop.assert_called_once()


def test_shutdown_is_idempotent():
    """Calling shutdown() twice does not raise or call stop() twice."""
    config = _make_config()
    tracker = Tracker(config)
    tracker.feed = MagicMock()

    tracker.shutdown()
    tracker.shutdown()

    # feed.stop() called only once (second shutdown is no-op)
    tracker.feed.stop.assert_called_once()


def test_sigint_triggers_shutdown():
    """SIGINT handler calls tracker.shutdown()."""
    config = _make_config()
    tracker = Tracker(config)
    tracker.feed = MagicMock()

    # Simulate the SIGINT handler as registered in main.py
    def _sigint_handler(sig, frame):
        tracker.shutdown()

    _sigint_handler(signal.SIGINT, None)

    assert tracker._shutdown_event.is_set()
    tracker.feed.stop.assert_called_once()


def test_session_end_triggers_shutdown(monkeypatch):
    """When time is past MARKET_CLOSE, run() exits via sys.exit(0)."""
    config = _make_config()
    tracker = Tracker(config)
    tracker.feed = MagicMock()

    # Patch datetime.now to return a time after 15:30 IST
    after_close = datetime(2024, 1, 15, 15, 30, 1, tzinfo=IST)

    with patch("nifty50_tracker.tracker.datetime") as mock_dt:
        mock_dt.now.return_value = after_close
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        with patch("nifty50_tracker.tracker.render_session_end"):
            with pytest.raises(SystemExit) as exc_info:
                tracker.run()

    assert exc_info.value.code == 0


def test_unhandled_exception_in_run_exits_nonzero():
    """An unhandled exception in run() calls shutdown() and exits with code 1."""
    config = _make_config()
    tracker = Tracker(config)
    mock_feed = MagicMock()
    tracker.feed = mock_feed

    # Make feed.start() raise an exception
    mock_feed.start.side_effect = RuntimeError("Simulated feed error")

    with pytest.raises(SystemExit) as exc_info:
        tracker.run()

    assert exc_info.value.code == 1


def test_handle_tick_updates_state():
    """_handle_tick applies the tick to session state."""
    config = _make_config()
    tracker = Tracker(config)

    tick_time = datetime(2024, 1, 15, 9, 15, 0, tzinfo=IST)
    tracker._handle_tick(23000.0, tick_time)

    assert tracker.state.ltp == 23000.0
    assert tracker.state.open_price == 23000.0  # First tick at market open


def test_handle_tick_renders_live_when_open_captured():
    """_handle_tick calls render_live after open price is captured."""
    config = _make_config()
    tracker = Tracker(config)

    tick_time = datetime(2024, 1, 15, 9, 15, 0, tzinfo=IST)

    with patch("nifty50_tracker.tracker.render_live") as mock_render:
        tracker._handle_tick(23000.0, tick_time)

    mock_render.assert_called_once()
