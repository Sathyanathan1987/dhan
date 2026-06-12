"""
Tests for calculator.py — pure movement calculation and formatting functions.

Includes:
- Property 5: Movement calculation correctness
- Property 6: Sign prefix correctness
- Property 7: Timestamp format consistency
- Unit tests: boundary conditions, N/A for zero open price
"""
import re
import sys
from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, r"d:\kiro_algo\ALGO DHAN")

from nifty50_tracker.calculator import (
    IST,
    MARKET_CLOSE,
    MARKET_OPEN,
    MovementResult,
    calculate_movement,
    format_movement_value,
    format_timestamp,
    is_market_open,
)

# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

# Feature: nifty50-open-tracker, Property 5: Movement calculation correctness
@given(
    open_price=st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    ltp=st.floats(min_value=0.01, max_value=100_000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_movement_calculation_correctness(open_price, ltp):
    """
    For any (open_price, ltp) pair with open_price > 0:
    - absolute_movement == round(ltp - open_price, 2)
    - percentage_movement == round((ltp - open_price) / open_price * 100, 2)
    - points_moved == absolute_movement
    All values rounded to exactly 2 decimal places.

    **Validates: Requirements 1.2**
    """
    result = calculate_movement(ltp, open_price)
    expected_abs = round(ltp - open_price, 2)
    expected_pct = round((ltp - open_price) / open_price * 100, 2)

    assert result.absolute_movement == expected_abs
    assert result.percentage_movement == expected_pct
    assert result.points_moved == result.absolute_movement


# Feature: nifty50-open-tracker, Property 6: Sign prefix correctness
@given(
    st.floats(
        min_value=-100_000.0,
        max_value=100_000.0,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_sign_prefix_correctness(value):
    """
    Positive → '+', Negative → '−' (Unicode minus U+2212), Zero → '±' (U+00B1).

    **Validates: Requirements 1.2**
    """
    formatted = format_movement_value(value)
    if value > 0:
        assert formatted.startswith("+"), f"Expected '+' prefix for {value}, got '{formatted}'"
    elif value < 0:
        assert formatted.startswith("\u2212"), f"Expected '−' prefix for {value}, got '{formatted}'"
    else:
        assert formatted.startswith("\u00b1"), f"Expected '±' prefix for {value}, got '{formatted}'"


# Feature: nifty50-open-tracker, Property 7: Timestamp format consistency
@given(st.datetimes(timezones=st.just(ZoneInfo("Asia/Kolkata"))))
def test_timestamp_format_consistency(dt):
    """
    For any IST-aware datetime, format_timestamp returns a string
    matching ``^\\d{2}:\\d{2}:\\d{2} IST$``.

    **Validates: Requirements 1.2**
    """
    result = format_timestamp(dt)
    assert re.match(r"^\d{2}:\d{2}:\d{2} IST$", result), (
        f"Timestamp '{result}' does not match HH:MM:SS IST format"
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_open_price_zero_pct_na():
    """percentage_movement is None when open_price == 0."""
    result = calculate_movement(ltp=23000.0, open_price=0.0)
    assert result.percentage_movement is None
    assert result.absolute_movement == 23000.0
    assert result.points_moved == 23000.0


def test_points_moved_equals_absolute_movement():
    """points_moved is always identical to absolute_movement."""
    result = calculate_movement(ltp=24000.0, open_price=23000.0)
    assert result.points_moved == result.absolute_movement


def test_is_market_open_boundary_open():
    """Returns True at exactly 09:15:00 IST."""
    market_open_dt = datetime(2024, 1, 15, 9, 15, 0, tzinfo=IST)
    assert is_market_open(market_open_dt) is True


def test_is_market_open_boundary_close():
    """Returns False at exactly 15:30:00 IST."""
    market_close_dt = datetime(2024, 1, 15, 15, 30, 0, tzinfo=IST)
    assert is_market_open(market_close_dt) is False


def test_is_market_open_before_open():
    """Returns False before 09:15 IST."""
    before_open = datetime(2024, 1, 15, 9, 14, 59, tzinfo=IST)
    assert is_market_open(before_open) is False


def test_is_market_open_during_session():
    """Returns True during trading session."""
    during = datetime(2024, 1, 15, 12, 0, 0, tzinfo=IST)
    assert is_market_open(during) is True


def test_format_timestamp_correct_format():
    """format_timestamp returns HH:MM:SS IST format."""
    dt = datetime(2024, 1, 15, 9, 15, 32, tzinfo=IST)
    result = format_timestamp(dt)
    assert result == "09:15:32 IST"


def test_format_movement_positive():
    """Positive value gets + prefix."""
    assert format_movement_value(111.35).startswith("+")


def test_format_movement_negative():
    """Negative value gets Unicode minus prefix."""
    assert format_movement_value(-50.0).startswith("\u2212")


def test_format_movement_zero():
    """Zero value gets ± prefix."""
    assert format_movement_value(0.0).startswith("\u00b1")
