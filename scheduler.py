"""
Daily strategy scheduler for NIFTY 50 and MCX strategies.

Schedule
--------
  09:00 AM IST (Mon–Fri)  →  Start both strategies simultaneously:
    • NIFTY 50 Bull Put / Bear Call Spread  (strategy_runner.py)
    • MCX EMA-7 Long — CRUDEOILM, NATGSMIN, GOLDPETAL, SILVER100  (mcx_runner.py)

MCX entry gate: no trade before 09:15 IST (enforced inside mcx_strategy.py).

Each strategy runs in its own daemon thread. The scheduler keeps running
and restarts the strategies at 09:00 AM every weekday.

Usage
-----
    # Run forever (restarts each trading day automatically)
    python -m nifty50_tracker.scheduler

    # Dry-run: print next scheduled time and exit
    python -m nifty50_tracker.scheduler --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

IST       = ZoneInfo("Asia/Kolkata")
START_H   = 9     # 09:00 IST — both strategies start
START_M   = 0
WEEKDAYS  = {0, 1, 2, 3, 4}   # Mon=0 … Fri=4 (skip Sat/Sun)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _next_start_time() -> datetime:
    """Return the next 09:00 IST on a weekday (today if not yet reached)."""
    now = datetime.now(tz=IST)
    candidate = now.replace(hour=START_H, minute=START_M, second=0, microsecond=0)

    if candidate <= now or now.weekday() not in WEEKDAYS:
        # Move to the next day and keep advancing until a weekday
        candidate += timedelta(days=1)
        while candidate.weekday() not in WEEKDAYS:
            candidate += timedelta(days=1)

    return candidate


def _wait_until(target: datetime) -> None:
    """Sleep in short intervals until target time, logging a countdown."""
    while True:
        now  = datetime.now(tz=IST)
        secs = (target - now).total_seconds()
        if secs <= 0:
            break
        if secs > 3600:
            logger.info("Next start: %s IST  (%.0f min remaining)",
                        target.strftime("%Y-%m-%d %H:%M"), secs / 60)
            time_module.sleep(300)   # check every 5 min when far away
        elif secs > 60:
            logger.info("Starting in %.0f minutes...", secs / 60)
            time_module.sleep(30)    # check every 30 s within 1 hour
        else:
            logger.info("Starting in %.0f seconds...", secs)
            time_module.sleep(5)     # check every 5 s in final minute


# ─────────────────────────────────────────────────────────────────────────────
# Strategy launchers (each runs in its own thread)
# ─────────────────────────────────────────────────────────────────────────────

def _run_nifty_strategy() -> None:
    """Run the NIFTY 50 Bull Put / Bear Call Spread strategy."""
    try:
        logger.info("[NIFTY] Starting NIFTY 50 spread strategy...")
        # Import here to avoid circular import issues
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from nifty50_tracker.strategy.strategy_runner import StrategyRunner
        runner = StrategyRunner()
        runner.run()
    except SystemExit as e:
        logger.info("[NIFTY] Strategy exited with code %s.", e.code)
    except Exception as exc:
        logger.exception("[NIFTY] Unexpected error: %s", exc)


def _run_mcx_strategy() -> None:
    """Run the MCX EMA-7 Long strategy (entry gated to 09:15 IST)."""
    try:
        logger.info("[MCX] Starting MCX EMA-7 strategy (entry from 09:15 IST)...")
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from nifty50_tracker.strategy.mcx_runner import McxRunner
        runner = McxRunner()
        runner.run()
    except SystemExit as e:
        logger.info("[MCX] Strategy exited with code %s.", e.code)
    except Exception as exc:
        logger.exception("[MCX] Unexpected error: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────────────────────────────────────

class DailyScheduler:
    """Launches both strategies at 09:00 IST every weekday."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        signal.signal(signal.SIGINT,  self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info("Scheduler started. Strategies will launch at %02d:%02d IST "
                    "on weekdays (Mon–Fri).", START_H, START_M)
        logger.info("MCX entry gate: 09:15 IST | NIFTY entry window: 09:45–13:00 IST")

        while not self._stop.is_set():
            next_start = _next_start_time()
            logger.info("Next launch: %s IST", next_start.strftime("%Y-%m-%d %H:%M"))
            _wait_until(next_start)

            if self._stop.is_set():
                break

            self._launch_strategies()

            # Wait past start time so we don't re-trigger in the same minute
            time_module.sleep(120)

        logger.info("Scheduler stopped.")

    def _launch_strategies(self) -> None:
        """Start NIFTY and MCX strategies concurrently in daemon threads."""
        logger.info("=" * 60)
        logger.info("LAUNCHING STRATEGIES — %s IST",
                    datetime.now(tz=IST).strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 60)

        nifty_thread = threading.Thread(
            target=_run_nifty_strategy,
            name="nifty-strategy",
            daemon=True,
        )
        mcx_thread = threading.Thread(
            target=_run_mcx_strategy,
            name="mcx-strategy",
            daemon=True,
        )

        self._threads = [nifty_thread, mcx_thread]
        nifty_thread.start()
        mcx_thread.start()

        logger.info("[SCHEDULER] Both strategies launched. Waiting for completion...")

        # Wait for both to finish (they exit at session end or on error)
        nifty_thread.join()
        mcx_thread.join()

        logger.info("[SCHEDULER] Both strategies have exited for today.")

    def _handle_signal(self, sig, frame) -> None:
        logger.info("Shutdown signal received — stopping scheduler.")
        self._stop.set()
        sys.exit(0)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily scheduler for NIFTY 50 and MCX trading strategies"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the next scheduled start time and exit without starting",
    )
    args = parser.parse_args()

    if args.dry_run:
        nxt = _next_start_time()
        now = datetime.now(tz=IST)
        diff_min = int((nxt - now).total_seconds() / 60)
        print(f"\nNext scheduled launch : {nxt.strftime('%Y-%m-%d %H:%M:%S IST')}")
        print(f"Current time          : {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
        print(f"Time until launch     : {diff_min} minutes\n")
        return

    scheduler = DailyScheduler()
    scheduler.start()


if __name__ == "__main__":
    main()
