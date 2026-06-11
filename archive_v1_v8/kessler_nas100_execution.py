"""
KESSLER V1.1 LIVE EXECUTION ENGINE
===================================
Target: NAS100 (5-minute timeframe)
Strategy: NY Session Liquidity Sweep & EMA Breakout
Parameters: Optimized via 145,152 permutation sweep.
"""

import time
import datetime
import numpy as np
import yfinance as yf
from shadow_broker import (
    init_db, open_position, check_stop_loss_take_profit, 
    update_equity_snapshot, log_signal, print_portfolio_report, get_open_positions
)

# ==========================================
# 🏆 OPTIMAL PARAMETERS HARDCODED
# ==========================================
SYMBOL = "NQ=F"               # Nasdaq 100 Futures
TIMEFRAME = "5m"              # 5-minute candles
SL_ATR_MULT = 2.5
TP_ATR_MULT = 4.0             # Updated: High-frequency cash flow
BREAKOUT_PERIOD = 12          # Updated: Faster accumulation tracking (1 hour)
EMA_FAST_P = 50
EMA_SLOW_P = 100
RISK_PCT = 0.01               # 1.0% Risk per trade
SESSION_START = 17            # Broker time start (NY Open / 09:30 EST equivalent)
SESSION_END = 21              # Broker time end
EMA_GAP_FILTER = True         # Require gap between EMAs
MIN_EMA_GAP = 0.002           # 0.2% gap minimum

CYCLE_INTERVAL = 300          # Run every 5 minutes

def fast_ema(prices, period):
    ema = np.empty_like(prices)
    ema[0] = prices[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(prices)):
        ema[i] = (prices[i] - ema[i-1]) * mult + ema[i-1]
    return ema

def fast_atr(highs, lows, closes, period=14):
    n = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i], 
                     abs(highs[i] - closes[i-1]), 
                     abs(lows[i] - closes[i-1]))
    atr = np.empty(n)
    atr[:period] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = np.mean(tr[i-period+1:i+1])
    return atr

def fetch_market_data():
    """Fetches the latest data to compute indicators."""
    df = yf.download(SYMBOL, period="5d", interval=TIMEFRAME, progress=False)
    if df.empty:
        return None
    return df

def run_v1_1_cycle(cycle_num):
    now = datetime.datetime.now()
    print(f"\n{'='*65}")
    print(f"  KESSLER V1.1 (NAS100) — CYCLE #{cycle_num} [{now.strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"{'='*65}")

    # 1. Check existing positions
    print("\n[PHASE 1] Managing open positions...")
    check_stop_loss_take_profit()
    open_pos = get_open_positions()
    if open_pos:
        print("  [—] Position already active. Holding fire.")
        return

    # 2. Session Check
    hour = now.hour
    if not (SESSION_START <= hour < SESSION_END):
        print(f"  [—] Outside trading session ({hour}:00). Waiting for NY Volume.")
        return

    # 3. Fetch Data & Compute Math
    print("\n[PHASE 2] Computing quantitative states...")
    df = fetch_market_data()
    if df is None:
        print("  [!] Data fetch failed.")
        return

    closes = df['Close'].values.flatten().astype(np.float64)
    highs = df['High'].values.flatten().astype(np.float64)
    lows = df['Low'].values.flatten().astype(np.float64)

    # Calculate indicators
    ema_fast = fast_ema(closes, EMA_FAST_P)
    ema_slow = fast_ema(closes, EMA_SLOW_P)
    atr_series = fast_atr(highs, lows, closes, 14)

    # Current values (last closed candle)
    c = closes[-1]
    ef = ema_fast[-1]
    es = ema_slow[-1]
    atr = atr_series[-1]

    # Rolling High/Low for Accumulation box (Breakout Period)
    local_high = np.max(highs[-BREAKOUT_PERIOD:])
    local_low = np.min(lows[-BREAKOUT_PERIOD:])

    print(f"  Price: ${c:.2f} | Local High: ${local_high:.2f} | Local Low: ${local_low:.2f}")
    print(f"  EMA50: ${ef:.2f} | EMA100: ${es:.2f} | ATR: {atr:.2f}")

    # 4. Strategy Logic
    print("\n[PHASE 3] Checking alignment...")
    is_uptrend = c > es and ef > es
    is_downtrend = c < es and ef < es

    if EMA_GAP_FILTER:
        ema_gap = abs(ef - es) / es
        if ema_gap < MIN_EMA_GAP:
            print("  [—] EMA Gap too tight. Market is chopping. No entry.")
            return

    signal = None
    if c > local_high and is_uptrend:
        signal = "LONG"
    elif c < local_low and is_downtrend:
        signal = "SHORT"

    if not signal:
        print("  [—] No breakout detected. Liquidity accumulating.")
        return

    # 5. Execution
    print(f"  [!!!] {signal} BREAKOUT DETECTED. Executing trade.")
    
    # Calculate SL/TP distances based on ATR
    sl_dist = atr * SL_ATR_MULT
    tp_dist = atr * TP_ATR_MULT
    
    # Send to Shadow Broker
    trade = open_position(
        symbol=SYMBOL,
        direction=signal,
        market_price=c,
        kessler_confidence=100.0, # Pure mathematical trigger
        kessler_cascade_depth=0,
        kessler_defaults=0,
        reason=f"V1.1 {signal} Breakout. SL: {sl_dist:.2f} pts, TP: {tp_dist:.2f} pts"
    )

    if trade:
        print(f"  [+] Trade executed successfully. Targeting {tp_dist:.2f} pts.")
    else:
        print("  [!] Trade rejected by risk manager.")

def main():
    init_db()
    print("\n" + "=" * 65)
    print("  KESSLER V1.1 ENGINE (NAS100 OPTIMIZED)")
    print("  Zero-Trust Local Execution Pipeline")
    print("=" * 65)
    print_portfolio_report()

    cycle = 1
    run_v1_1_cycle(cycle)

    print(f"\n[*] CONTINUOUS MONITORING ENGAGED ({CYCLE_INTERVAL}s intervals)")
    try:
        while True:
            time.sleep(CYCLE_INTERVAL)
            cycle += 1
            run_v1_1_cycle(cycle)
    except KeyboardInterrupt:
        print("\n\n[*] V1.1 Engine terminated.")
        sys.exit(0)

if __name__ == "__main__":
    main()
