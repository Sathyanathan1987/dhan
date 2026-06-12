"""
On-demand CLI runner for post-market / off-market analysis.

Usage:
    # Analyse today's data
    python -m nifty50_tracker.analysis_runner

    # Analyse a specific date
    python -m nifty50_tracker.analysis_runner --date 2026-06-10

    # Analyse a date range
    python -m nifty50_tracker.analysis_runner --from 2026-06-09 --to 2026-06-10

    # Skip the NIFTY 50 index itself, only stocks
    python -m nifty50_tracker.analysis_runner --no-index
"""
import argparse
import logging
import sys
from datetime import date, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from nifty50_tracker.market_analysis import run_analysis, StockAnalysis


def _print_table(results: list[StockAnalysis]) -> None:
    """Print a clean aligned summary table to stdout."""
    # Column widths
    w_sym  = 12
    w_seg  = 8
    w_cnd  = 7
    w_cls  = 10
    w_sma  = 10
    w_ema  = 10
    w_err  = 30

    header = (
        f"{'SYMBOL':<{w_sym}} "
        f"{'SEGMENT':<{w_seg}} "
        f"{'CANDLES':>{w_cnd}} "
        f"{'LAST CLOSE':>{w_cls}} "
        f"{'SMA-7':>{w_sma}} "
        f"{'EMA-7':>{w_ema}} "
        f"{'NOTE':<{w_err}}"
    )
    separator = "-" * len(header)

    print()
    print(header)
    print(separator)

    ok_count = 0
    err_count = 0

    for r in results:
        if r.error:
            err_count += 1
            print(
                f"{r.symbol:<{w_sym}} "
                f"{r.exchange_segment:<{w_seg}} "
                f"{'—':>{w_cnd}} "
                f"{'—':>{w_cls}} "
                f"{'—':>{w_sma}} "
                f"{'—':>{w_ema}} "
                f"{r.error:<{w_err}}"
            )
        else:
            ok_count += 1
            close = f"{r.latest_close:.2f}" if r.latest_close is not None else "—"
            sma7  = f"{r.latest_sma7:.4f}"  if r.latest_sma7  is not None else "< 7 bars"
            ema7  = f"{r.latest_ema7:.4f}"  if r.latest_ema7  is not None else "< 7 bars"
            print(
                f"{r.symbol:<{w_sym}} "
                f"{r.exchange_segment:<{w_seg}} "
                f"{len(r.candles):>{w_cnd}} "
                f"{close:>{w_cls}} "
                f"{sma7:>{w_sma}} "
                f"{ema7:>{w_ema}}"
            )

    print(separator)
    print(f"Total: {len(results)} instruments  |  OK: {ok_count}  |  Errors: {err_count}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NIFTY 50 post-market moving average analysis via Dhan API"
    )
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Analyse a single date (default: today)",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        metavar="YYYY-MM-DD",
        help="Start date for range analysis",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        metavar="YYYY-MM-DD",
        help="End date for range analysis",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="Skip the NIFTY 50 index itself, only process constituent stocks",
    )
    parser.add_argument(
        "--period",
        type=int,
        default=7,
        help="MA period (default: 7)",
    )
    args = parser.parse_args()

    # Resolve dates
    if args.date:
        from_date = to_date = args.date
    elif args.from_date and args.to_date:
        from_date = args.from_date
        to_date   = args.to_date
    elif args.from_date or args.to_date:
        parser.error("Provide both --from and --to for a date range.")
        return
    else:
        # Default: today
        today = date.today().isoformat()
        from_date = to_date = today

    print(f"\nNIFTY 50 Moving Average Analysis")
    print(f"Period : {from_date}  →  {to_date}")
    print(f"MA     : SMA-{args.period} / EMA-{args.period}")
    print(f"Candles: 1-minute OHLCV\n")

    try:
        results = run_analysis(
            from_date=from_date,
            to_date=to_date,
            include_index=not args.no_index,
            ma_period=args.period,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    _print_table(results)


if __name__ == "__main__":
    main()
