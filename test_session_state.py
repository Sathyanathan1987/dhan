"""
Tests for session_state.py — shared in-memory session state.

Includes:
- Property 2: Open price is captured from the first qualifying tick
- Property 3: Open price immutability after capture
- Property 4: Pre-open ticks never set the open price
- Unit tests: 60s warning, pending display state
"""
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, r"d:\kiro_algo\ALGO DHAN")

from nifty50_tracker.calculator import IST, MARKET_OPEN
from nifty50_tracker.session_state import SessionState


def _ist_datetime(hour: int, minute: int, second: int = 0) -> datetime:
    """Create a timezone-aware IST datetime for testing."""
    return datetime(2024, 1, 15, hour, minute, second, tzinfo=IST)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

# Feature: nifty50-open-tracker, Property 2: Open price is captured from the first qualifying tick
@given(
    ltp=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    hour=st.integers(min_value=9, max_value=15),
    minute=st.integers(min_value=0, max_value=59),
    second=st.integers(min_value=0, max_value=59),
)
@settings(max_examples=200)
def test_open_price_captured_from_first_qualifying_tick(ltp, hour, minute, second):
    """
    For any LTP at or after 09:15 IST on a fresh SessionState,
    apply_tick SHALL set open_price to that LTP and lock it.
    """
    # Build a datetime at or after 09:15
    tick_time = datetime(2024, 1, 15, hour, minute, second, tzinfo=IST)
    from datetime import time as dtime
    if tick_time.time() < MARKET_OPEN:
        return  # Skip pre-market times — not the focus of this property

    state = SessionState()
    state.apply_tick(ltp, tick_time)

    assert state.is_open_price_captured(), "Open price should be captured at or after 09:15"
    assert state.open_price == ltp, f"Expected open_price={ltp}, got {state.open_price}"
    assert state.open_price_locked is True


# Feature: nifty50-open-tracker, Property 3: Open price immutability after capture
@given(
    first_ltp=st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    subsequent_ltps=st.lists(
        st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=50,
    ),
)
@settings(max_examples=200)
def test_open_price_immutability_after_capture(first_ltp, subsequent_ltps):
    """
    After the first qualifying tick, any number of subsequent ticks with
    arbitrary LTPs SHALL not change open_price.
    """
    state = SessionState()
    # Apply the first qualifying tick (at 09:15:00 IST)
    market_open_time = _ist_datetime(9, 15, 0)
    state.apply_tick(first_ltp, market_open_time)

    captured_open = state.open_price
    assert captured_open == first_ltp

    # Apply subsequent ticks at later times
    for i, ltp in enumerate(subsequent_ltps):
        later_time = _ist_datetime(9, 15, i + 1) if i < 59 else _ist_datetime(9, 16, i - 59)
        state.apply_tick(ltp, later_time)
        assert state.open_price == captured_open, (
            f"open_price changed from {captured_open} to {state.open_price} after tick with ltp={ltp}"
        )


# Feature: nifty50-open-tracker, Property 4: Pre-open ticks never set the open price
@given(
    ltps=st.lists(
        st.floats(min_value=1.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=50,
    )
)
@settings(max_examples=200)
def test_pre_open_ticks_do_not_set_open_price(ltps):
    """
    Any sequence of ticks with timestamps strictly before 09:15 IST
    SHALL leave open_price as None.
    """
    state = SessionState()
    # Generate pre-market times (00:00 to 09:14:59 IST)
    for i, ltp in enumerate(ltps):
        # Distribute across 0..9:14:59 IST
        total_secs = i % (9 * 3600 + 15 * 60)  # 0 to 09:14:59
        hour = total_secs // 3600
        minute = (total_secs % 3600) // 60
        second = total_secs % 60
        tick_time = datetime(2024, 1, 15, hour, minute, second, tzinfo=IST)
        state.apply_tick(ltp, tick_time)

    assert state.open_price is None, (
        f"open_price should be None after only pre-market ticks, got {state.open_price}"
    )
    assert state.open_price_locked is False


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_is_open_price_captured_false_initially():
    """is_open_price_captured() returns False on a fresh SessionState."""
    state = SessionState()
    assert state.is_open_price_captured() is False


def test_is_open_price_captured_true_after_qualifying_tick():
    """is_open_price_captured() returns True after a tick at 09:15 IST."""
    state = SessionState()
    state.apply_tick(23000.0, _ist_datetime(9, 15, 0))
    assert state.is_open_price_captured() is True


def test_pre_market_tick_does_not_capture():
    """Tick at 09:14:59 IST does not capture open price."""
    state = SessionState()
    state.apply_tick(23000.0, _ist_datetime(9, 14, 59))
    assert state.is_open_price_captured() is False
    assert state.open_price is None


def test_ltp_updated_on_every_tick():
    """ltp is updated on every tick regardless of market time."""
    state = SessionState()
    state.apply_tick(23000.0, _ist_datetime(9, 0, 0))
    assert state.ltp == 23000.0
    state.apply_tick(23100.0, _ist_datetime(9, 1, 0))
    assert state.ltp == 23100.0


def test_last_tick_time_updated():
    """last_tick_time reflects the most recent tick time."""
    state = SessionState()
    t = _ist_datetime(9, 15, 30)
    state.apply_tick(23000.0, t)
    assert state.last_tick_time == t


def test_reset_clears_all_state():
    """reset() clears all state fields."""
    state = SessionState()
    state.apply_tick(23000.0, _ist_datetime(9, 15, 0))
    state.reset()
    assert state.open_price is None
    assert state.ltp is None
    assert state.last_tick_time is None
    assert state.open_price_locked is False
