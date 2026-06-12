"""
Session orchestrator for the NIFTY 50 Open Tracker.
Coordinates the FeedManager, SessionState, Calculator, and Renderer.
"""
import logging
import sys
import threading
import time as time_module
from datetime import datetime

from nifty50_tracker.calculator import IST, MARKET_CLOSE, MARKET_OPEN, calculate_movement
from nifty50_tracker.config import AppConfig
from nifty50_tracker.feed_manager import FeedManager
from nifty50_tracker.renderer import (
    render_live,
    render_pending_open,
    render_session_end,
    render_waiting,
)
from nifty50_tracker.session_state import SessionState

logger = logging.getLogger(__name__)


class Tracker:
    """
    Drives the main event loop for the trading session.

    Responsibilities:
    - Start the FeedManager
    - Route each tick to SessionState
    - Render the display on each tick and each second while waiting
    - Detect session end and trigger shutdown
    - Handle SIGINT gracefully (called externally from main.py)
    """

    def __init__(self, config: AppConfig) -> None:
        self.state = SessionState()
        self.feed = FeedManager(config, on_tick=self._handle_tick)
        self._shutdown_event = threading.Event()
        self._warned_open_price: bool = False  # One-shot 60s warning flag

    def run(self) -> None:
        """
        Main loop:
        1. Start the feed (blocks until connected or exits on failure)
        2. Loop until shutdown_event is set or session ends at 15:30 IST
        3. Stop the feed and exit cleanly
        """
        logger.info("Starting NIFTY 50 Open Tracker...")

        try:
            self.feed.start()

            while not self._shutdown_event.is_set():
                now = datetime.now(tz=IST)

                # Check for session end
                if now.time() >= MARKET_CLOSE:
                    render_session_end()
                    logger.info("Trading session ended at 15:30 IST.")
                    break

                # Render display based on current state
                if self.state.is_open_price_captured():
                    # Normal live display
                    if self.state.ltp is not None and self.state.open_price is not None:
                        result = calculate_movement(self.state.ltp, self.state.open_price)
                        render_live(self.state, result, now)
                elif now.time() >= MARKET_OPEN:
                    # Market is open but open price not yet captured
                    if self.state.ltp is not None:
                        render_pending_open(now, self.state.ltp)
                    else:
                        render_waiting(now)
                    # 60-second warning (one-shot)
                    if not self._warned_open_price:
                        from datetime import time as dtime
                        market_open_dt = now.replace(
                            hour=MARKET_OPEN.hour,
                            minute=MARKET_OPEN.minute,
                            second=MARKET_OPEN.second,
                            microsecond=0,
                        )
                        elapsed = (now - market_open_dt).total_seconds()
                        if elapsed >= 60:
                            logger.warning(
                                "Open price not yet captured 60 seconds after market open."
                            )
                            self._warned_open_price = True
                else:
                    # Before market open — show waiting message
                    render_waiting(now)

                time_module.sleep(1)

        except Exception as exc:
            logger.exception("Unhandled exception in tracker run loop: %s", exc)
            self.shutdown()
            sys.exit(1)

        finally:
            self.feed.stop()

        sys.exit(0)

    def _handle_tick(self, ltp: float, tick_time: datetime) -> None:
        """
        Called by FeedManager on each tick.
        Updates session state and refreshes the display immediately.
        """
        self.state.apply_tick(ltp, tick_time)
        # Refresh display immediately on tick (not waiting for the 1s loop)
        now = tick_time
        if self.state.is_open_price_captured() and self.state.open_price is not None:
            result = calculate_movement(ltp, self.state.open_price)
            render_live(self.state, result, now)

    def shutdown(self) -> None:
        """
        Gracefully stop the tracker.
        Idempotent: safe to call multiple times.
        """
        if not self._shutdown_event.is_set():
            logger.info("Shutdown requested.")
            self._shutdown_event.set()
            self.feed.stop()
