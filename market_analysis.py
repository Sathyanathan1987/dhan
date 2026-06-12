"""
Post-market / off-market analysis module for NIFTY 50 and its constituents.

Fetches 1-minute OHLCV candles via the Dhan REST API and computes:
  - 7-period Simple Moving Average (SMA-7) on close prices
  - 7-period Exponential Moving Average (EMA-7) on close prices

Usage (on-demand, no automatic scheduling):
    from nifty50_tracker.market_analysis import run_analysis
    results = run_analysis(from_date="2026-06-10", to_date="2026-06-10")
    # results is a list of StockAnalysis dataclasses

This module has no side effects — it does not print, write files, or schedule
anything. The caller decides what to do with the returned data.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from dhanhq import dhanhq

from nifty50_tracker.nifty50_constituents import NIFTY50_CONSTITUENTS, NIFTY50_INDEX

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Candle:
    """A single 1-minute OHLCV candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class MAResult:
    """Moving average values for a single candle."""
    timestamp: datetime
    close: float
    sma7: Optional[float]   # None if fewer than 7 candles available
    ema7: Optional[float]   # None if fewer than 7 candles available


@dataclass
class StockAnalysis:
    """Analysis result for a single stock or index."""
    symbol: str
    security_id: str
    exchange_segment: str
    candles: List[Candle] = field(default_factory=list)
    ma_results: List[MAResult] = field(default_factory=list)
    error: Optional[str] = None  # Set if data fetch or calculation failed

    @property
    def latest_close(self) -> Optional[float]:
        """Most recent closing price."""
        return self.candles[-1].close if self.candles else None

    @property
    def latest_sma7(self) -> Optional[float]:
        """Most recent SMA-7 value."""
        for r in reversed(self.ma_results):
            if r.sma7 is not None:
                return r.sma7
        return None

    @property
    def latest_ema7(self) -> Optional[float]:
        """Most recent EMA-7 value."""
        for r in reversed(self.ma_results):
            if r.ema7 is not None:
                return r.ema7
        return None


# ---------------------------------------------------------------------------
# Moving average calculations (pure functions)
# ---------------------------------------------------------------------------

_EMA7_MULTIPLIER = 2 / (7 + 1)  # 0.25


def calculate_sma(closes: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate Simple Moving Average for a list of closing prices.
    Returns a list of the same length; first (period-1) values are None.
    """
    result: List[Optional[float]] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            window = closes[i - period + 1 : i + 1]
            result.append(round(sum(window) / period, 4))
    return result


def calculate_ema(closes: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate Exponential Moving Average for a list of closing prices.
    Uses SMA of the first `period` candles as the seed EMA.
    Returns a list of the same length; first (period-1) values are None.
    """
    if not closes:
        return []

    multiplier = 2 / (period + 1)
    result: List[Optional[float]] = [None] * (period - 1)

    if len(closes) < period:
        return result + [None] * (len(closes) - (period - 1))

    # Seed: SMA of first `period` values
    seed = sum(closes[:period]) / period
    result.append(round(seed, 4))

    for i in range(period, len(closes)):
        prev_ema = result[-1]
        ema = round(closes[i] * multiplier + prev_ema * (1 - multiplier), 4)
        result.append(ema)

    return result


def compute_ma_results(candles: List[Candle], period: int = 7) -> List[MAResult]:
    """
    Compute SMA and EMA for a list of candles and return MAResult per candle.
    """
    closes = [c.close for c in candles]
    sma_values = calculate_sma(closes, period)
    ema_values = calculate_ema(closes, period)

    return [
        MAResult(
            timestamp=candle.timestamp,
            close=candle.close,
            sma7=sma_values[i],
            ema7=ema_values[i],
        )
        for i, candle in enumerate(candles)
    ]


# ---------------------------------------------------------------------------
# Dhan API helpers
# ---------------------------------------------------------------------------

def _parse_candles(raw: dict) -> List[Candle]:
    """
    Parse the raw dict returned by dhanhq.intraday_minute_data() into Candle objects.

    The SDK returns a dict with key 'data' containing a dict with lists:
    {
        'data': {
            'timestamp': [...],
            'open': [...],
            'high': [...],
            'low': [...],
            'close': [...],
            'volume': [...]
        }
    }
    """
    if not raw or raw.get("status") == "failure":
        return []

    data = raw.get("data", {})
    if isinstance(data, str):
        # Error string returned
        return []

    timestamps = data.get("timestamp", [])
    opens      = data.get("open", [])
    highs      = data.get("high", [])
    lows       = data.get("low", [])
    closes     = data.get("close", [])
    volumes    = data.get("volume", [])

    candles = []
    for i, ts in enumerate(timestamps):
        try:
            # Dhan returns epoch seconds or ISO string depending on version
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
            else:
                dt = datetime.fromisoformat(str(ts))

            candles.append(Candle(
                timestamp=dt,
                open=float(opens[i])   if i < len(opens)   else 0.0,
                high=float(highs[i])   if i < len(highs)   else 0.0,
                low=float(lows[i])     if i < len(lows)    else 0.0,
                close=float(closes[i]) if i < len(closes)  else 0.0,
                volume=int(volumes[i]) if i < len(volumes) else 0,
            ))
        except Exception as exc:
            logger.warning("Skipping malformed candle at index %d: %s", i, exc)

    return candles


def _fetch_intraday(
    client: dhanhq,
    security_id: str,
    exchange_segment: str,
    instrument_type: str,
    from_date: str,
    to_date: str,
    interval: int = 1,
) -> List[Candle]:
    """
    Fetch 1-minute candles for a single instrument.
    Returns an empty list on any error.
    """
    try:
        raw = client.intraday_minute_data(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_date,
            to_date=to_date,
            interval=interval,
        )
        return _parse_candles(raw)
    except Exception as exc:
        logger.error(
            "Failed to fetch data for security_id=%s: %s", security_id, exc
        )
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_analysis(
    from_date: str,
    to_date: str,
    include_index: bool = True,
    ma_period: int = 7,
    candle_interval: int = 1,
    rate_limit_delay: float = 0.3,
) -> List[StockAnalysis]:
    """
    Fetch 1-minute OHLCV data and compute moving averages for NIFTY 50
    and all 50 constituent stocks.

    Parameters
    ----------
    from_date : str
        Start date in 'YYYY-MM-DD' format.
    to_date : str
        End date in 'YYYY-MM-DD' format.
    include_index : bool
        If True, also fetch NIFTY 50 index data (default True).
    ma_period : int
        Period for SMA and EMA calculation (default 7).
    candle_interval : int
        Candle size in minutes (default 1).
    rate_limit_delay : float
        Seconds to wait between API calls to avoid rate limiting (default 0.3s).

    Returns
    -------
    List[StockAnalysis]
        One entry per instrument. Check `.error` field for fetch failures.
    """
    # Load credentials from the same .env the main app uses
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    _env = Path(__file__).parent / ".env"
    if not _env.exists():
        _env = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=_env, override=False)

    client_id    = os.environ.get("DHAN_CLIENT_ID", "").strip()
    access_token = os.environ.get("DHAN_ACCESS_TOKEN", "").strip()

    if not client_id or not access_token:
        raise ValueError(
            "DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN must be set in the .env file."
        )

    client = dhanhq(client_id, access_token)

    instruments = []
    if include_index:
        instruments.append(NIFTY50_INDEX)
    instruments.extend(NIFTY50_CONSTITUENTS)

    results: List[StockAnalysis] = []

    total = len(instruments)
    for idx, (symbol, security_id, exchange_segment, instrument_type) in enumerate(instruments, 1):
        logger.info("[%d/%d] Fetching %s (%s)...", idx, total, symbol, security_id)

        candles = _fetch_intraday(
            client=client,
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            from_date=from_date,
            to_date=to_date,
            interval=candle_interval,
        )

        analysis = StockAnalysis(
            symbol=symbol,
            security_id=security_id,
            exchange_segment=exchange_segment,
        )

        if not candles:
            analysis.error = f"No data returned for {symbol}"
            logger.warning("No data for %s", symbol)
        else:
            analysis.candles = candles
            analysis.ma_results = compute_ma_results(candles, period=ma_period)
            logger.info(
                "  %s: %d candles, latest close=%.2f, SMA7=%.4f, EMA7=%.4f",
                symbol,
                len(candles),
                analysis.latest_close or 0,
                analysis.latest_sma7 or 0,
                analysis.latest_ema7 or 0,
            )

        results.append(analysis)

        # Respect rate limits
        if idx < total:
            time.sleep(rate_limit_delay)

    logger.info("Analysis complete. %d instruments processed.", len(results))
    return results
