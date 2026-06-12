"""
Entry point for the NIFTY 50 Open Tracker.
Sets up logging, registers SIGINT handler, and starts the Tracker.
"""
import logging
import signal
import sys

from nifty50_tracker.config import load_config
from nifty50_tracker.tracker import Tracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Application entry point."""
    config = load_config()  # Exits with code 1 on bad credentials

    tracker = Tracker(config)

    # Register SIGINT (Ctrl+C) handler for graceful shutdown
    def _sigint_handler(sig, frame):
        logger.info("Received interrupt signal. Shutting down...")
        tracker.shutdown()

    signal.signal(signal.SIGINT, _sigint_handler)

    try:
        tracker.run()
    except Exception as exc:
        logger.exception("Unhandled exception in main: %s", exc)
        tracker.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
