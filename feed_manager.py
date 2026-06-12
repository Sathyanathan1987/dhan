"""
WebSocket feed manager for the NIFTY 50 Open Tracker.
Wraps the dhanhq MarketFeed SDK (v2.0.x), adding reconnection and
health-check logic.
"""
import logging
import sys
import threading
import time as time_module
from datetime import datetime
from typing import Callable, Optional

from dhanhq import marketfeed

from nifty50_tracker.calculator import IST
from nifty50_tracker.config import AppConfig

logger = logging.getLogger(__name__)

# Exchange segment for NSE Indices (IDX_I = 0 in dhanhq 2.0.x)
_IDX_I: int = marketfeed.IDX  # 0


class FeedManager:
    """
    Manages the WebSocket connection to the Dhan Market Data API.

    Responsibilities:
    - Connect and subscribe to NIFTY 50 feed on startup
    - Reconnect with retries on connection failure
    - Run a periodic health check and re-subscribe if feed goes stale
    - Call the on_tick callback for every received tick
    - Close the connection gracefully on shutdown
    """

    def __init__(
        self,
        config: AppConfig,
        on_tick: Callable[[float, datetime], None],
    ) -> None:
        self._config = config
        self._on_tick = on_tick
        self._feed: Optional[marketfeed.DhanFeed] = None
        self._last_tick_time: Optional[datetime] = None
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Instruments list: list of (exchange_segment, security_id, sub_type)
        # security_id must be a str; subscription type 15 = Ticker
        self._instruments = [
            (_IDX_I, config.nifty_security_id, marketfeed.Ticker)
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Attempt connection up to config.max_retries times.
        Exits with sys.exit(1) if all attempts fail.
        When reconnect_enabled=False, a single attempt is made with no retries.
        """
        if not self._config.reconnect_enabled:
            if not self._connect_once():
                logger.error("Failed to connect to Dhan Market Data API. Exiting.")
                sys.exit(1)
            return

        for attempt in range(1, self._config.max_retries + 1):
            logger.info(
                "Connection attempt %d/%d...", attempt, self._config.max_retries
            )
            if self._connect_once():
                logger.info("Connected to Dhan Market Data API.")
                self._start_health_check()
                return
            if attempt < self._config.max_retries:
                logger.warning(
                    "Connection attempt %d failed. Retrying in %ds...",
                    attempt,
                    self._config.retry_interval_sec,
                )
                time_module.sleep(self._config.retry_interval_sec)

        logger.error(
            "All %d connection attempts failed. Exiting.", self._config.max_retries
        )
        sys.exit(1)

    def stop(self) -> None:
        """
        Gracefully close the WebSocket connection.
        Sets the stop event so the health-check thread exits, then closes the feed.
        """
        self._stop_event.set()
        if self._feed is not None:
            try:
                logger.info("Closing Dhan Market Data feed...")
                # dhanhq 2.0.x uses close_connection() which wraps the async disconnect
                self._feed.close_connection()
                logger.info("Feed closed.")
            except Exception as exc:
                logger.warning("Error during feed disconnect: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect_once(self) -> bool:
        """
        Create a DhanFeed instance, attach the tick callback, and start the feed.
        Returns True on success, False on any exception.
        """
        try:
            feed = marketfeed.DhanFeed(
                self._config.client_id,
                self._config.access_token,
                self._instruments,
                version="v2",
            )
            # Attach our callback before starting the loop
            feed.on_ticks = self._on_data_received
            self._feed = feed
            self._feed.run_forever()
            return True
        except Exception as exc:
            logger.error("Connection error: %s: %s", type(exc).__name__, exc)
            self._feed = None
            return False

    def _on_data_received(self, data: dict) -> None:
        """
        Callback invoked by DhanFeed for each tick.
        Extracts LTP (which the SDK returns as a formatted string) and calls
        the on_tick callback.
        """
        try:
            ltp = float(data.get("LTP", 0.0))
            if ltp <= 0:
                return  # Skip invalid / zero ticks
            now = datetime.now(tz=IST)
            self._last_tick_time = now
            self._on_tick(ltp, now)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to process tick data: %s — %s", data, exc)

    def _start_health_check(self) -> None:
        """Start the background health-check thread."""
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            name="health-check",
            daemon=True,
        )
        self._health_check_thread.start()

    def _health_check_loop(self) -> None:
        """
        Runs every health_check_interval_sec seconds.
        Re-subscribes if no tick was received within stale_feed_threshold_sec seconds.
        """
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._config.health_check_interval_sec)
            if self._stop_event.is_set():
                break

            if self._last_tick_time is not None:
                elapsed = (
                    datetime.now(tz=IST) - self._last_tick_time
                ).total_seconds()
                if elapsed > self._config.stale_feed_threshold_sec:
                    logger.warning(
                        "No tick received in %.0fs (threshold: %ds). Re-subscribing...",
                        elapsed,
                        self._config.stale_feed_threshold_sec,
                    )
                    self._resubscribe()

    def _resubscribe(self) -> None:
        """Re-subscribe to the NIFTY 50 feed to refresh a stale subscription."""
        if self._feed is not None:
            try:
                self._feed.subscribe_symbols(self._instruments)
                logger.info("Re-subscribed to NIFTY 50 feed.")
            except Exception as exc:
                logger.error("Failed to re-subscribe: %s", exc)
