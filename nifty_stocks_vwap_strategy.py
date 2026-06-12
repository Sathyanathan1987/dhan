"""
Nifty 50 Stocks VWAP Strategy
=============================
Buy ATM Call options when stock price is above VWAP on 5-min intervals.
Exit when stock price closes below VWAP.

Instruments: RELIANCE, HDFC, ICICIBANK
Strategy: Buy Call ATM when price > VWAP → Exit when price < VWAP

Requires:
  - dhanhq (broker integration)
  - pandas, numpy (data processing)
  - Environment: DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from dhanhq import marketfeed, orderapi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Candle:
    """Represents a 5-minute candlestick."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float = 0.0

    @property
    def mid_price(self) -> float:
        """Mid-price of the candle (high + low) / 2."""
        return (self.high + self.low) / 2.0


@dataclass
class StockData:
    """Stores real-time and aggregated data for a single stock."""
    symbol: str
    security_id: str
    exchange: int = 1  # NSE
    candles: List[Candle] = field(default_factory=list)
    current_ltp: float = 0.0
    current_volume: float = 0.0
    last_tick_time: Optional[datetime] = None

    def add_tick(self, ltp: float, volume: float, timestamp: datetime) -> None:
        """Record a tick and aggregate into 5-min candles."""
        self.current_ltp = ltp
        self.current_volume = volume
        self.last_tick_time = timestamp

    def get_current_vwap(self) -> float:
        """Return VWAP of the last completed candle, or 0 if no candles."""
        if not self.candles:
            return 0.0
        return self.candles[-1].vwap

    def get_current_candle_price(self) -> float:
        """Get the high/low/close of the current candle being built."""
        if not self.candles:
            return self.current_ltp
        return self.candles[-1].close or self.current_ltp


@dataclass
class Trade:
    """Represents an open or closed trade."""
    trade_id: str
    symbol: str
    trade_type: str  # "CALL_BUY"
    entry_time: datetime
    entry_price: float
    entry_qty: int
    strike_price: float
    expiry: str  # "YYYY-MM-DD" or "26JUN2026"
    
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    dhan_order_id: Optional[str] = None
    
    @property
    def is_open(self) -> bool:
        return self.exit_time is None

    @property
    def pnl(self) -> float:
        if not self.exit_price:
            return 0.0
        return (self.exit_price - self.entry_price) * self.entry_qty

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return ((self.exit_price or self.entry_price) - self.entry_price) / self.entry_price * 100


# ============================================================================
# VWAP Calculation
# ============================================================================

def calculate_vwap(candles: List[Candle]) -> float:
    """
    Calculate Volume-Weighted Average Price (VWAP).
    VWAP = Sum(High*Low*Close*Volume) / Sum(Volume)
    
    A simple TP = (High + Low + Close) / 3
    VWAP = Sum(TP * Volume) / Sum(Volume)
    """
    if not candles:
        return 0.0
    
    cumulative_tp_vol = 0.0
    cumulative_vol = 0.0
    
    for candle in candles:
        typical_price = (candle.high + candle.low + candle.close) / 3.0
        cumulative_tp_vol += typical_price * candle.volume
        cumulative_vol += candle.volume
    
    if cumulative_vol == 0:
        return 0.0
    
    return cumulative_tp_vol / cumulative_vol


# ============================================================================
# Strategy Core
# ============================================================================

class NiftyStocksVWAPStrategy:
    """
    VWAP-based call buying strategy for Nifty 50 stocks.
    
    Rules:
    1. Monitor RELIANCE, HDFC, ICICIBANK on 5-min intervals
    2. When price > VWAP: Buy ATM Call (SL at VWAP)
    3. When price closes < VWAP: Exit the position
    """
    
    def __init__(
        self,
        client_id: str,
        access_token: str,
        symbols: Optional[List[str]] = None,
    ):
        self.client_id = client_id
        self.access_token = access_token
        self.symbols = symbols or ["RELIANCE", "HDFC", "ICICIBANK"]
        
        # Mapping of symbol to (security_id, expiry_format)
        # These need to be updated based on Dhan's security IDs
        self.symbol_config = {
            "RELIANCE": {"security_id": "1922", "lot_size": 1},
            "HDFC": {"security_id": "1594", "lot_size": 2},
            "ICICIBANK": {"security_id": "1834", "lot_size": 5},
        }
        
        # Data and state
        self.stocks: Dict[str, StockData] = {
            sym: StockData(symbol=sym, security_id=self.symbol_config[sym]["security_id"])
            for sym in self.symbols
        }
        self.trades: Dict[str, List[Trade]] = {sym: [] for sym in self.symbols}
        self.active_trades: Dict[str, Optional[Trade]] = {sym: None for sym in self.symbols}
        
        # Broker API
        self.feed = None
        self.order_api = None
        self._stop_event = False
        
        logger.info(f"NiftyStocksVWAPStrategy initialized for {self.symbols}")

    def connect(self) -> bool:
        """Connect to Dhan Market Data API and Order API."""
        try:
            logger.info("Connecting to Dhan Market Data...")
            
            # Prepare instruments: [(exchange, security_id, sub_type), ...]
            instruments = [
                (marketfeed.NSE, self.symbol_config[sym]["security_id"], marketfeed.Ticker)
                for sym in self.symbols
            ]
            
            self.feed = marketfeed.DhanFeed(
                self.client_id,
                self.access_token,
                instruments,
                version="v2",
            )
            self.feed.on_ticks = self._on_tick
            
            # Order API for placing trades
            self.order_api = orderapi.OrderAPI(
                self.client_id,
                self.access_token,
            )
            
            logger.info("Connected to Dhan successfully!")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def start(self) -> None:
        """Start the strategy (blocks until stopped)."""
        if not self.connect():
            logger.error("Failed to connect. Exiting.")
            sys.exit(1)
        
        try:
            logger.info("Starting market data feed...")
            self.feed.run_forever()
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Gracefully shut down the strategy and close open positions."""
        logger.info("Shutting down strategy...")
        self._stop_event = True
        
        # Close all open trades
        for symbol in self.symbols:
            if self.active_trades[symbol]:
                self._exit_trade(symbol, reason="SHUTDOWN")
        
        if self.feed:
            try:
                self.feed.close_connection()
            except:
                pass
        
        logger.info("Strategy shutdown complete.")

    # ────────────────────────────────────────────────────────────────────

    def _on_tick(self, data: dict) -> None:
        """
        Callback invoked for each market tick.
        Parse the tick data and route to the appropriate symbol handler.
        """
        try:
            # Dhan tick data structure depends on the version
            # Typical: {"security_id": "...", "LTP": "1234.56", "Volume": "1000", ...}
            ltp = float(data.get("LTP", 0))
            volume = float(data.get("Volume", 0))
            security_id = str(data.get("security_id", ""))
            
            if ltp <= 0 or volume <= 0:
                return
            
            now = datetime.now(tz=IST)
            
            # Find which symbol this tick belongs to
            for symbol in self.symbols:
                if self.symbol_config[symbol]["security_id"] == security_id:
                    self._process_tick(symbol, ltp, volume, now)
                    break
        except Exception as e:
            logger.warning(f"Error processing tick: {e}")

    def _process_tick(self, symbol: str, ltp: float, volume: float, timestamp: datetime) -> None:
        """Process a single tick for a symbol and check strategy signals."""
        stock = self.stocks[symbol]
        stock.add_tick(ltp, volume, timestamp)
        
        # Aggregate into 5-min candles
        self._update_candles(symbol, timestamp)
        
        # Check for buy signal (price > VWAP)
        if self.active_trades[symbol] is None:
            self._check_buy_signal(symbol)
        else:
            # Check for exit signal (price < VWAP)
            self._check_exit_signal(symbol)

    def _update_candles(self, symbol: str, timestamp: datetime) -> None:
        """
        Aggregate ticks into 5-minute candles.
        This is a simplified version; in production, use proper candle aggregation.
        """
        stock = self.stocks[symbol]
        ltp = stock.current_ltp
        volume = stock.current_volume
        
        # Get or create current candle (5-min interval)
        # Floor timestamp to nearest 5-min interval
        minute = (timestamp.minute // 5) * 5
        candle_start = timestamp.replace(minute=minute, second=0, microsecond=0)
        
        if not stock.candles or stock.candles[-1].timestamp != candle_start:
            # New 5-min candle
            vwap_val = calculate_vwap(stock.candles) if stock.candles else ltp
            new_candle = Candle(
                timestamp=candle_start,
                open=ltp,
                high=ltp,
                low=ltp,
                close=ltp,
                volume=volume,
                vwap=vwap_val,
            )
            stock.candles.append(new_candle)
        else:
            # Update current candle
            current = stock.candles[-1]
            current.high = max(current.high, ltp)
            current.low = min(current.low, ltp)
            current.close = ltp
            current.volume += volume
            # Recalculate VWAP
            current.vwap = calculate_vwap(stock.candles)

    def _check_buy_signal(self, symbol: str) -> None:
        """Check if we should buy a call (price > VWAP)."""
        stock = self.stocks[symbol]
        vwap = stock.get_current_vwap()
        current_price = stock.current_ltp
        
        if vwap == 0 or current_price <= vwap:
            return
        
        logger.info(f"{symbol}: Buy signal! Price {current_price:.2f} > VWAP {vwap:.2f}")
        
        # Buy ATM call
        self._buy_call(symbol, current_price, vwap)

    def _check_exit_signal(self, symbol: str) -> None:
        """Check if we should exit (price < VWAP)."""
        stock = self.stocks[symbol]
        vwap = stock.get_current_vwap()
        current_price = stock.current_ltp
        
        if vwap == 0 or current_price >= vwap:
            return
        
        trade = self.active_trades[symbol]
        if trade:
            logger.info(f"{symbol}: Exit signal! Price {current_price:.2f} < VWAP {vwap:.2f}")
            self._exit_trade(symbol, reason="VWAP_CLOSE_BELOW")

    def _buy_call(self, symbol: str, entry_price: float, vwap_sl: float) -> None:
        """Place a buy call order at ATM strike."""
        try:
            # Find the ATM strike (simplified: use current price rounded to nearest 100)
            strike = round(entry_price / 100) * 100
            
            # Get expiry (this is mock; in production, fetch from API)
            today = datetime.now(tz=IST).date()
            expiry_date = today + timedelta(days=3)  # Example: 3 days out
            expiry_str = expiry_date.strftime("%d%b%Y").upper()
            
            qty = self.symbol_config[symbol]["lot_size"]
            
            # Place order via Dhan API (mock implementation)
            logger.info(
                f"Placing BUY CALL order: {symbol} {strike} {expiry_str} "
                f"Qty={qty} Entry={entry_price:.2f} SL={vwap_sl:.2f}"
            )
            
            # In production, uncomment and use actual order API:
            # response = self.order_api.place_order(
            #     security_id=self.symbol_config[symbol]["security_id"],
            #     order_type=orderapi.LIMIT,
            #     price=entry_price,
            #     quantity=qty,
            #     side=orderapi.BUY,
            #     ...
            # )
            # order_id = response["order_id"]
            
            # Create trade object
            trade = Trade(
                trade_id=f"{symbol}_{datetime.now(tz=IST).timestamp()}",
                symbol=symbol,
                trade_type="CALL_BUY",
                entry_time=datetime.now(tz=IST),
                entry_price=entry_price,
                entry_qty=qty,
                strike_price=strike,
                expiry=expiry_str,
                dhan_order_id=None,  # order_id in production
            )
            
            self.active_trades[symbol] = trade
            self.trades[symbol].append(trade)
            
            logger.info(f"Trade opened: {trade.trade_id}")
        except Exception as e:
            logger.error(f"Error placing buy order for {symbol}: {e}")

    def _exit_trade(self, symbol: str, reason: str = "MANUAL") -> None:
        """Close an open trade at current market price."""
        trade = self.active_trades[symbol]
        if not trade:
            return
        
        try:
            current_price = self.stocks[symbol].current_ltp
            
            # Sell to close
            logger.info(f"Selling to close: {symbol} qty={trade.entry_qty} @ {current_price:.2f}")
            
            # In production:
            # response = self.order_api.place_order(
            #     security_id=self.symbol_config[symbol]["security_id"],
            #     order_type=orderapi.MARKET,
            #     quantity=trade.entry_qty,
            #     side=orderapi.SELL,
            #     ...
            # )
            
            # Close the trade
            trade.exit_time = datetime.now(tz=IST)
            trade.exit_price = current_price
            trade.exit_reason = reason
            
            pnl = trade.pnl
            logger.info(
                f"Trade closed: {trade.trade_id} | "
                f"Entry: {trade.entry_price:.2f} Exit: {current_price:.2f} | "
                f"P&L: ₹{pnl:.2f} ({trade.pnl_pct:.2f}%)"
            )
            
            self.active_trades[symbol] = None
        except Exception as e:
            logger.error(f"Error closing trade for {symbol}: {e}")

    # ────────────────────────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        """Return a summary of all trades and current state."""
        summary = {
            "timestamp": datetime.now(tz=IST).isoformat(),
            "symbols": {},
        }
        
        for symbol in self.symbols:
            stock = self.stocks[symbol]
            active_trade = self.active_trades[symbol]
            trades = self.trades[symbol]
            
            closed_trades = [t for t in trades if not t.is_open]
            total_pnl = sum(t.pnl for t in closed_trades)
            
            summary["symbols"][symbol] = {
                "ltp": stock.current_ltp,
                "vwap": stock.get_current_vwap(),
                "active_trade": {
                    "entry_price": active_trade.entry_price,
                    "entry_time": active_trade.entry_time.isoformat(),
                    "strike": active_trade.strike_price,
                    "expiry": active_trade.expiry,
                } if active_trade else None,
                "closed_trades": len(closed_trades),
                "total_pnl": total_pnl,
            }
        
        return summary


# ============================================================================
# Main Runner
# ============================================================================

def main():
    """
    Main entry point for the strategy.
    Reads credentials from environment and starts the strategy.
    """
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    client_id = os.environ.get("DHAN_CLIENT_ID")
    access_token = os.environ.get("DHAN_ACCESS_TOKEN")
    
    if not client_id or not access_token:
        logger.error("Missing DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN in environment")
        sys.exit(1)
    
    strategy = NiftyStocksVWAPStrategy(client_id, access_token)
    strategy.start()


if __name__ == "__main__":
    main()
