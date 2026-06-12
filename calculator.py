"""
Pure movement calculation and formatting functions for the NIFTY 50 Open Tracker.
No I/O. All functions are stateless and side-effect-free.
"""
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = time(9, 15, 0)   # 09:15 IST
MARKET_CLOSE = time(15, 30, 0)  # 15:30 IST

# Unicode sign characters
_PLUS = "+"
_MINUS = "\u2212"   # Unicode minus sign (−), distinct from hyphen-minus
_PLUSMINUS = "\u00b1"  # ± sign


@dataclass(frozen=True)
class MovementResult:
    """Result of a single movement calculation."""
    absolute_movement: float
    percentage_movement: float | None  # None when open_price == 0
    points_moved: float  # Always equal to absolute_movement (intentional)


def calculate_movement(ltp: float, open_price: float) -> MovementResult:
    """
    Calculate absolute, percentage, and points movement from open price.
    
    All values rounded to 2 decimal places.
    percentage_movement is None when open_price == 0 (division by zero guard).
    points_moved is always equal to absolute_movement.
    """
    abs_move = round(ltp - open_price, 2)
    pct_move = (
        round((ltp - open_price) / open_price * 100, 2)
        if open_price != 0
        else None
    )
    pts_move = abs_move  # Intentionally identical to absolute_movement per spec
    return MovementResult(
        absolute_movement=abs_move,
        percentage_movement=pct_move,
        points_moved=pts_move,
    )


def is_market_open(now: datetime) -> bool:
    """Return True if current time is within the trading session (09:15 to 15:30 IST)."""
    now_ist = now.astimezone(IST)
    t = now_ist.time()
    return MARKET_OPEN <= t < MARKET_CLOSE


def format_timestamp(dt: datetime) -> str:
    """Format a datetime as 'HH:MM:SS IST'."""
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%H:%M:%S") + " IST"


def format_movement_value(value: float) -> str:
    """
    Format a movement value with appropriate sign prefix.
    Positive: '+', Negative: '−' (Unicode minus), Zero: '±'
    """
    if value > 0:
        return f"{_PLUS}{value:.2f}"
    elif value < 0:
        return f"{_MINUS}{abs(value):.2f}"
    else:
        return f"{_PLUSMINUS}{value:.2f}"
