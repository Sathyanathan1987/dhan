"""
In-memory session state for the NIFTY 50 Open Tracker.
Holds the open price (immutable once set), current LTP, and last tick time.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from nifty50_tracker.calculator import MARKET_OPEN, IST

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """
    Shared mutable state for the trading session.
    
    Invariant: once open_price_locked is True, open_price is never changed.
    """
    open_price: Optional[float] = None
    ltp: Optional[float] = None
    last_tick_time: Optional[datetime] = None
    open_price_locked: bool = False

    def apply_tick(self, ltp: float, tick_time: datetime) -> None:
        """
        Update LTP and last tick time.
        If open price has not been captured yet and tick_time is at or after
        MARKET_OPEN (09:15 IST), capture the open price and lock it.
        """
        self.ltp = ltp
        self.last_tick_time = tick_time

        if not self.open_price_locked:
            tick_ist = tick_time.astimezone(IST)
            if tick_ist.time() >= MARKET_OPEN:
                self.open_price = ltp
                self.open_price_locked = True
                logger.info(
                    "Open price captured: %.2f at %s",
                    ltp,
                    tick_ist.strftime("%H:%M:%S IST"),
                )

    def is_open_price_captured(self) -> bool:
        """Return True if the open price has been captured and locked."""
        return self.open_price_locked

    def reset(self) -> None:
        """Reset all state. Used in tests only — not called in production."""
        self.open_price = None
        self.ltp = None
        self.last_tick_time = None
        self.open_price_locked = False
