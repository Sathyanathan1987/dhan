"""
Terminal display renderer for the NIFTY 50 Open Tracker.
Uses carriage return (\\r) to overwrite the same line on each update.
No external display library required.
"""
import sys
from datetime import datetime
from typing import Optional

from nifty50_tracker.calculator import (
    MovementResult,
    format_movement_value,
    format_timestamp,
)
from nifty50_tracker.session_state import SessionState

# Track the length of the last printed line to ensure full overwrite
_last_line_len: int = 0


def _write_overwrite(line: str) -> None:
    """Write a line with carriage return prefix, padding to overwrite previous."""
    global _last_line_len
    # Pad with trailing spaces to fully overwrite any longer previous line
    padded = line.ljust(_last_line_len)
    sys.stdout.write(f"\r{padded}")
    sys.stdout.flush()
    _last_line_len = len(line)


def render_live(
    state: SessionState,
    result: MovementResult,
    now: datetime,
) -> None:
    """
    Display live movement data on a single overwritten line.
    Format: HH:MM:SS IST | Open: XXXXX.XX | LTP: XXXXX.XX | Chg: ±XXX.XX | %: ±X.XX% | Pts: ±XXX.XX pts
    """
    ts = format_timestamp(now)
    open_price = state.open_price if state.open_price is not None else 0.0
    ltp = state.ltp if state.ltp is not None else 0.0

    chg = format_movement_value(result.absolute_movement)
    pct = (
        f"{format_movement_value(result.percentage_movement)}%"
        if result.percentage_movement is not None
        else "N/A"
    )
    pts = f"{format_movement_value(result.points_moved)} pts"

    line = (
        f"{ts} | Open: {open_price:.2f} | LTP: {ltp:.2f} | "
        f"Chg: {chg} | %: {pct} | Pts: {pts}"
    )
    _write_overwrite(line)


def render_waiting(now: datetime) -> None:
    """
    Display a waiting message while market has not opened yet.
    Format: HH:MM:SS IST | Market opens at 09:15 IST. Waiting...
    Updates every second (caller is responsible for calling this each second).
    """
    ts = format_timestamp(now)
    line = f"{ts} | Market opens at 09:15 IST. Waiting..."
    _write_overwrite(line)


def render_pending_open(now: datetime, ltp: float) -> None:
    """
    Display when ticks are arriving but the open price hasn't been captured yet
    (e.g., ticks arriving right at 09:15 before the first qualifying tick).
    Format: HH:MM:SS IST | LTP: XXXXX.XX | Capturing open price...
    """
    ts = format_timestamp(now)
    line = f"{ts} | LTP: {ltp:.2f} | Capturing open price..."
    _write_overwrite(line)


def render_session_end() -> None:
    """
    Print a session-end message on a new line.
    Called when trading session ends at 15:30 IST.
    """
    sys.stdout.write("\n15:30:00 IST | Trading session ended. Closing feed.\n")
    sys.stdout.flush()


def reset_line_len() -> None:
    """Reset the internal line length counter. Used in tests only."""
    global _last_line_len
    _last_line_len = 0
