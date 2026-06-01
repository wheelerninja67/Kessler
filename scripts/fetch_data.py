#!/usr/bin/env python3
"""
Kessler Institutional Market Data Fetcher
Downloads global macro data for the systemic risk simulation engine.
Handles transient Yahoo Finance errors gracefully – failed tickers are skipped
without destroying the entire dataset.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# The Institutional Macro Universe
# ---------------------------------------------------------------------------
INSTITUTIONAL_TICKERS = [
    # US Equity Indices
    "^GSPC",
    "^DJI",
    "^IXIC",
    "^RUT",
    # Global Equity Indices
    "^FTSE",
    "^GDAXI",
    "^FCHI",
    "^N225",
    "^HSI",
    "000001.SS",
    "^BSESN",
    "^KS11",
    "^BVSP",
    "^GSPTSE",
    "^AXJO",
    "^STOXX50E",
    # FX (vs USD)
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "AUDUSD=X",
    "USDCAD=X",
    "USDCHF=X",
    "NZDUSD=X",
    # US Sovereign Bond Yields
    "^TNX",
    "^IRX",
    "^TYX",
    # Futures
    "ES=F",
    "NQ=F",
    "ZN=F",
    "ZB=F",
    "CL=F",
    "GC=F",
    "SI=F",
    # Credit ETFs
    "HYG",
    "LQD",
    # Volatility
    "^VIX",
    # Crypto
    "BTC-USD",
]

DEFAULT_START = "2015-01-01"
DEFAULT_END = "2025-12-31"
DEFAULT_INTERVAL = "1d"
DEFAULT_OUTDIR = "data"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def download_ticker(ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
    """Download a single ticker with retries on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = yf.download(
                ticker,
                start=start,
                end=end,
                interval=interval,
                auto_adjust=True,
                progress=False,
            )
            if df.empty:
                log.warning("%s returned empty DataFrame (attempt %d)", ticker, attempt)
                time.sleep(RETRY_DELAY)
                continue
            # If single ticker, yfinance returns simple columns; rename 'Close' to ticker
            if isinstance(df.columns, pd.Index) and "Close" in df.columns:
                close = df[["Close"]].rename(columns={"Close": ticker})
            else:
                # Multi-ticker? shouldn't happen, but handle gracefully
                close = (
                    df.xs("Close", axis=1, level=1)
                    if hasattr(df.columns, "levels")
                    else df[["Close"]]
                )
                close.columns = [ticker]
            return close
        except Exception as exc:
            log.warning("%s download failed (attempt %d): %s", ticker, attempt, exc)
            time.sleep(RETRY_DELAY)
    log.error("%s failed after %d retries – skipping", ticker, MAX_RETRIES)
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Kessler institutional data fetcher")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    args = parser.parse_args()

    tickers = INSTITUTIONAL_TICKERS
    start, end, interval = args.start, args.end, args.interval
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    log.info(
        "Fetching %d institutional tickers (%s → %s, interval=%s)",
        len(tickers),
        start,
        end,
        interval,
    )

    # ------------------------------------------------------------------
    # Download each ticker independently, merge into one DataFrame
    # ------------------------------------------------------------------
    all_closes = []
    failed = []
    for i, tkr in enumerate(tickers, 1):
        log.info("[%02d/%02d] %s", i, len(tickers), tkr)
        close = download_ticker(tkr, start, end, interval)
        if close.empty:
            failed.append(tkr)
        else:
            all_closes.append(close)

    if not all_closes:
        log.error("No data downloaded for any ticker. Exiting.")
        sys.exit(1)

    prices = pd.concat(all_closes, axis=1)

    # Forward-fill missing values (e.g., non-trading days)
    prices = prices.ffill()

    # Drop rows where *all* tickers are NaN (shouldn't happen after forward-fill)
    prices = prices.dropna(how="all")

    # For remaining NaNs (some tickers start later than others), forward-fill again
    prices = prices.ffill().dropna()

    if prices.empty:
        log.error("After cleaning, no price data remains")
        sys.exit(1)

    log.info("Merged data: %d rows × %d columns", len(prices), len(prices.columns))
    if failed:
        log.warning("Failed tickers (skipped): %s", ", ".join(failed))

    # ------------------------------------------------------------------
    # Compute log returns
    # ------------------------------------------------------------------
    returns = np.log(prices / prices.shift(1)).dropna()

    # ------------------------------------------------------------------
    # Write CSVs
    # ------------------------------------------------------------------
    prices_path = outdir / "prices.csv"
    returns_path = outdir / "returns.csv"
    prices.to_csv(prices_path, float_format="%.6f")
    returns.to_csv(returns_path, float_format="%.8f")
    log.info(
        "Prices  → %s  (%d rows, %d cols)",
        prices_path,
        len(prices),
        len(prices.columns),
    )
    log.info(
        "Returns → %s  (%d rows, %d cols)",
        returns_path,
        len(returns),
        len(returns.columns),
    )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    metadata = {
        "tickers": [t for t in tickers if t not in failed],
        "failed_tickers": failed,
        "num_tickers": len(tickers) - len(failed),
        "start_date": start,
        "end_date": end,
        "interval": interval,
        "num_days": len(prices),
        "first_date": str(prices.index[0].date()),
        "last_date": str(prices.index[-1].date()),
        "prices_file": str(prices_path),
        "returns_file": str(returns_path),
        "generated_at": datetime.now().isoformat(),
    }
    meta_path = outdir / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Metadata → %s", meta_path)

    log.info(
        "Done. %d tickers, %d days (%s → %s)",
        metadata["num_tickers"],
        metadata["num_days"],
        metadata["first_date"],
        metadata["last_date"],
    )


if __name__ == "__main__":
    main()
