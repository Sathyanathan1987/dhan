"""
Tests for renderer.py — terminal display functions.

Includes:
- Property 8: Live display contains all required fields
- Unit tests: waiting message content, overwrite format
"""
import re
import sys
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, r"d:\kiro_algo\ALGO DHAN")

from nifty50_tracker.calculator import IST, MovementResult, calculate_movement
from nifty50_tracker.renderer import (
    render_live,
    render_pending_open,
    render_session_end,
    render_waiting,
    reset_line_len,
)
from nifty50_tracker.session_state import SessionState


def _make_state(open_price: float, ltp: float) -> SessionState:
    """Create a SessionState with a captured open price and given LTP."""
    state = SessionState()
    tick_time = datetime(2024, 1, 15, 9, 15, 0, tzinfo=IST)
    state.apply_tick(open_price, tick_time)
    # Now update LTP to the desired value
    state.ltp = ltp
    return state


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------

# **Validates: Requirements 1.2**
# Feature: nifty50-open-tracker, Property 8: Live display contains all required fields
@given(
    open_price=st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    ltp=st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_live_display_contains_all_required_fields(open_price, ltp):
    """
    For any SessionState with captured open price and any MovementResult,
    render_live output SHALL contain:
    - timestamp matching HH:MM:SS IST
    - open price value
    - LTP value
    - absolute movement with sign prefix
    - percentage with % suffix
    - points with 'pts' suffix
    """
    reset_line_len()
    state = _make_state(open_price, ltp)
    result = calculate_movement(ltp, open_price)
    now = datetime(2024, 1, 15, 9, 30, 0, tzinfo=IST)

    captured = StringIO()
    sys.stdout = captured
    try:
        render_live(state, result, now)
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()

    # Timestamp pattern HH:MM:SS IST
    assert re.search(r"\d{2}:\d{2}:\d{2} IST", output), "Missing IST timestamp"
    # Open price present
    assert "Open:" in output, "Missing 'Open:' field"
    # LTP present
    assert "LTP:" in output, "Missing 'LTP:' field"
    # Absolute movement with sign prefix (+ or − or ±)
    assert "Chg:" in output, "Missing 'Chg:' field"
    # Percentage with % suffix
    if result.percentage_movement is not None:
        assert "%" in output, "Missing '%' suffix"
    else:
        assert "N/A" in output, "Missing N/A for zero open price"
    # Points with 'pts' suffix
    assert "pts" in output, "Missing 'pts' suffix"


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_render_live_overwrites_line(capsys):
    """render_live output starts with carriage return (\\r)."""
    reset_line_len()
    state = _make_state(23000.0, 23100.0)
    result = calculate_movement(23100.0, 23000.0)
    now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=IST)

    captured = StringIO()
    sys.stdout = captured
    try:
        render_live(state, result, now)
    finally:
        sys.stdout = sys.__stdout__

    assert captured.getvalue().startswith("\r"), "render_live should start with \\r"


def test_waiting_display_content():
    """Waiting message contains current time and '09:15 IST'."""
    reset_line_len()
    now = datetime(2024, 1, 15, 9, 0, 0, tzinfo=IST)

    captured = StringIO()
    sys.stdout = captured
    try:
        render_waiting(now)
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert "09:15 IST" in output, "Waiting message should mention 09:15 IST"
    assert re.search(r"\d{2}:\d{2}:\d{2} IST", output), "Missing IST timestamp in waiting message"


def test_render_waiting_overwrites_line():
    """render_waiting output starts with \\r."""
    reset_line_len()
    now = datetime(2024, 1, 15, 9, 0, 0, tzinfo=IST)

    captured = StringIO()
    sys.stdout = captured
    try:
        render_waiting(now)
    finally:
        sys.stdout = sys.__stdout__

    assert captured.getvalue().startswith("\r")


def test_render_session_end_on_new_line():
    """render_session_end starts with newline."""
    captured = StringIO()
    sys.stdout = captured
    try:
        render_session_end()
    finally:
        sys.stdout = sys.__stdout__

    output = captured.getvalue()
    assert output.startswith("\n"), "Session end message should start with newline"
    assert "session ended" in output.lower()
