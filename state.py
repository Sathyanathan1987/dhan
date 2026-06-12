"""Thread-safe shared state for the dashboard."""
from __future__ import annotations
import copy, threading
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

IST   = ZoneInfo("Asia/Kolkata")
_lock = threading.Lock()


def _inst() -> Dict[str, Any]:
    return dict(status="stopped", ltp=None, ema7=None, signal=None,
                candles=[], trades=[], active_trade=None, pnl=0.0, updated="")


_S: Dict[str, Any] = dict(
    started="",
    nifty=dict(status="stopped", ltp=None, ema7=None, signal=None,
               candles=[], trades=[], active_trade=None, pnl=0.0, updated=""),
    mcx=dict(CRUDEOILM=_inst(), NATGSMIN=_inst(), GOLDPETAL=_inst(), SILVER100=_inst()),
    log=[],
)


def _ts() -> str:
    return datetime.now(tz=IST).strftime("%H:%M:%S")


def nifty_tick(ltp: float, ema7: float | None) -> None:
    with _lock:
        _S["nifty"]["ltp"]     = round(ltp, 2)
        _S["nifty"]["ema7"]    = round(ema7, 4) if ema7 else None
        _S["nifty"]["updated"] = _ts()
        _S["nifty"]["status"]  = "running"


def nifty_candle(t: str, close: float, ema7: float | None) -> None:
    with _lock:
        c = dict(time=t, close=close, ema7=ema7)
        _S["nifty"]["candles"].append(c)
        _S["nifty"]["candles"] = _S["nifty"]["candles"][-60:]


def nifty_signal(signal: str | None) -> None:
    with _lock:
        _S["nifty"]["signal"] = signal


def nifty_trade(trade: dict) -> None:
    with _lock:
        _S["nifty"]["trades"].append(trade)
        _S["nifty"]["active_trade"] = trade if not trade.get("exit_time") else None
        total = sum(t.get("pnl", 0) or 0 for t in _S["nifty"]["trades"])
        _S["nifty"]["pnl"] = round(total, 2)


def mcx_tick(symbol: str, ltp: float, ema7: float | None) -> None:
    with _lock:
        if symbol not in _S["mcx"]:
            return
        _S["mcx"][symbol]["ltp"]     = round(ltp, 2)
        _S["mcx"][symbol]["ema7"]    = round(ema7, 4) if ema7 else None
        _S["mcx"][symbol]["updated"] = _ts()
        _S["mcx"][symbol]["status"]  = "running"


def mcx_candle(symbol: str, t: str, close: float, ema7: float | None) -> None:
    with _lock:
        if symbol not in _S["mcx"]:
            return
        c = dict(time=t, close=close, ema7=ema7)
        _S["mcx"][symbol]["candles"].append(c)
        _S["mcx"][symbol]["candles"] = _S["mcx"][symbol]["candles"][-60:]


def mcx_signal(symbol: str, signal: str | None) -> None:
    with _lock:
        if symbol in _S["mcx"]:
            _S["mcx"][symbol]["signal"] = signal


def mcx_trade(symbol: str, trade: dict) -> None:
    with _lock:
        if symbol not in _S["mcx"]:
            return
        _S["mcx"][symbol]["trades"].append(trade)
        _S["mcx"][symbol]["active_trade"] = trade if not trade.get("exit_time") else None
        total = sum(t.get("pnl", 0) or 0 for t in _S["mcx"][symbol]["trades"])
        _S["mcx"][symbol]["pnl"] = round(total, 2)


def log(msg: str) -> None:
    with _lock:
        _S["log"].append(f"[{_ts()}] {msg}")
        _S["log"] = _S["log"][-200:]


def mark_started() -> None:
    with _lock:
        _S["started"] = datetime.now(tz=IST).strftime("%Y-%m-%d %H:%M:%S IST")


def get() -> Dict[str, Any]:
    with _lock:
        return copy.deepcopy(_S)
