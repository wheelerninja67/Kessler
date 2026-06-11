import time
import json
import os
import sys
import math
from datetime import datetime, timezone, timedelta
import ctypes

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] MetaTrader5 library not found or running on non-Windows OS.")
    mt5 = None

# Core trading parameters
PRIMARY_SYMBOL = "XAUUSD"
CORRELATED_SYMBOLS = ["USDX", "US10Y", "XAGUSD", "VIX"]  # Dollar, Yields, Silver, Volatility Index
MAGIC_NUMBER = 888888

def initialize_mt5():
    print("[*] Initializing MT5 connection...")
    if not mt5.initialize():
        print(f"[!] MT5 initialize() failed, error code: {mt5.last_error()}")
        return False
    print("[*] Successfully connected to MT5 Terminal.")
    
    # Ensure all symbols are available
    for sym in [PRIMARY_SYMBOL] + CORRELATED_SYMBOLS:
        if not mt5.symbol_select(sym, True):
            print(f"[!] Warning: Could not select {sym} in Market Watch.")
    return True

def calculate_statarb_zscore(gold_rates, dollar_rates):
    """
    Calculates the statistical divergence between Gold and the US Dollar.
    Returns a Z-Score. Positive means Gold is overvalued compared to historical norm.
    """
    if gold_rates is None or dollar_rates is None or len(gold_rates) < 50 or len(dollar_rates) < 50:
        return 0.0

    spreads = []
    # Using the last 50 hours of data to find the rolling correlation
    for i in range(50):
        # Normalize prices to percentage changes or log returns for accurate comparison
        g_price = gold_rates[-(50-i)]['close']
        d_price = dollar_rates[-(50-i)]['close']
        spread = math.log(g_price) + math.log(d_price) # Simplified inverse relationship
        spreads.append(spread)
    
    current_spread = spreads[-1]
    mean_spread = sum(spreads) / len(spreads)
    
    variance = sum((s - mean_spread) ** 2 for s in spreads) / len(spreads)
    std_dev = math.sqrt(variance) if variance > 0 else 0.0001
    
    z_score = (current_spread - mean_spread) / std_dev
    return z_score

def detect_smc_liquidity_sweep(m5_rates, d1_rates):
    """
    Retail Logic: Detects if the current price just swept the Previous Day's High or Low.
    Returns 1 for Bullish Sweep (Swept PDL and reversed up)
    Returns -1 for Bearish Sweep (Swept PDH and reversed down)
    """
    if len(m5_rates) < 3 or len(d1_rates) < 2:
        return 0

    previous_day = d1_rates[-2]
    pdh = previous_day['high']
    pdl = previous_day['low']
    
    current_m5 = m5_rates[-1]
    prev_m5 = m5_rates[-2]
    
    # Bearish Sweep: Swept PDH, but closed below it
    if prev_m5['high'] > pdh and current_m5['close'] < pdh:
        return -1
        
    # Bullish Sweep: Swept PDL, but closed above it
    if prev_m5['low'] < pdl and current_m5['close'] > pdl:
        return 1
        
    return 0

def detect_fair_value_gap(m5_rates):
    """
    Retail Logic (ICT/TJR): Detects a 3-candle imbalance (FVG).
    Returns 1 for Bullish FVG, -1 for Bearish FVG.
    """
    if len(m5_rates) < 4:
        return 0
        
    c1 = m5_rates[-4]
    c2 = m5_rates[-3] # The violent expansion candle
    c3 = m5_rates[-2]
    
    # Bullish FVG
    if c1['high'] < c3['low']:
        return 1
        
    # Bearish FVG
    if c1['low'] > c3['high']:
        return -1
        
    return 0

def detect_market_structure_shift(m5_rates):
    """
    Retail Logic (ICT/TJR): Detects a 'Change of Character' (ChoCh) / MSS.
    After a sweep, did price break a recent swing low/high?
    Returns 1 for Bullish Shift, -1 for Bearish Shift.
    """
    if len(m5_rates) < 6:
        return 0
        
    # Simplified Swing High/Low detection
    recent_low = min([r['low'] for r in m5_rates[-6:-2]])
    recent_high = max([r['high'] for r in m5_rates[-6:-2]])
    
    current_close = m5_rates[-1]['close']
    
    # Bearish MSS: Price closes below the recent swing low
    if current_close < recent_low:
        return -1
        
    # Bullish MSS: Price closes above the recent swing high
    if current_close > recent_high:
        return 1
        
    return 0

def run_hybrid_engine():
    print("=========================================================")
    print("  [KESSLER V8] INDESTRUCTIBLE GOLD ENGINE (STATARB + FVG) ")
    print("=========================================================")

    if not initialize_mt5():
        sys.exit(1)

    print("[*] Engine Online. Scanning XAUUSD Matrix...")
    
    bearish_hunter_timer = 0
    bullish_hunter_timer = 0
    pending_order_type = 0
    pending_limit_price = 0.0
    pending_sl = 0.0
    pending_timer = 0
    
    try:
        while True:
            # 1. Fetch Data
            gold_h1 = mt5.copy_rates_from_pos(PRIMARY_SYMBOL, mt5.TIMEFRAME_H1, 0, 100)
            dollar_h1 = mt5.copy_rates_from_pos("USDX", mt5.TIMEFRAME_H1, 0, 100)
            vix_h1 = mt5.copy_rates_from_pos("VIX", mt5.TIMEFRAME_H1, 0, 10)
            gold_m5 = mt5.copy_rates_from_pos(PRIMARY_SYMBOL, mt5.TIMEFRAME_M5, 0, 20)
            
            if gold_h1 is None or dollar_h1 is None or gold_m5 is None:
                time.sleep(5)
                continue

            current_close = gold_m5[-1]['close']
            
            # Decrement Timers
            if bearish_hunter_timer > 0: bearish_hunter_timer -= 1
            if bullish_hunter_timer > 0: bullish_hunter_timer -= 1
            if pending_timer > 0: pending_timer -= 1

            # 2. Institutional Math
            z_score = calculate_statarb_zscore(gold_h1, dollar_h1)
            
            vix_spike = False
            if vix_h1 is not None and len(vix_h1) > 2:
                vix_curr = vix_h1[-1]['close']
                vix_prev = vix_h1[-2]['close']
                vix_pct_change = ((vix_curr - vix_prev) / vix_prev) * 100.0
                if vix_pct_change > 5.0:
                    vix_spike = True

            # ACTIVATE HUNTER MODE
            if z_score > 2.0:
                bearish_hunter_timer = 288 # Active for 24 hours
            elif z_score < -2.0:
                bullish_hunter_timer = 288 # Active for 24 hours
            
            # 3. Retail Structure
            mss = detect_market_structure_shift(gold_m5)
            c1 = gold_m5[-4]
            c3 = gold_m5[-2]
            
            # PENDING ORDER EXECUTION TRIGGER CHECK
            if pending_timer > 0:
                if pending_order_type == 1 and current_close <= pending_limit_price:
                    print(f"\\n[!!!] LIMIT ORDER TRIGGERED: BUY XAUUSD @ {pending_limit_price} [!!!]")
                    print(f"      [SL: {pending_sl:.2f}]")
                    pending_order_type = 0
                elif pending_order_type == -1 and current_close >= pending_limit_price:
                    print(f"\\n[!!!] LIMIT ORDER TRIGGERED: SELL XAUUSD @ {pending_limit_price} [!!!]")
                    print(f"      [SL: {pending_sl:.2f}]")
                    pending_order_type = 0
            
            # NEW ENTRY SCANNING
            if bearish_hunter_timer > 0 and mss == -1:
                if c1['low'] > c3['high']: 
                    fvg_mid = (c1['low'] + c3['high']) / 2.0
                    pending_order_type = -1
                    pending_limit_price = fvg_mid
                    pending_sl = c1['high'] + 1.0
                    pending_timer = 24
                    bearish_hunter_timer = 0
                    print(f"\\n[>] SETUP FOUND: Placed SELL LIMIT at {fvg_mid:.2f}")
            elif bullish_hunter_timer > 0 and mss == 1:
                if c1['high'] < c3['low']:
                    fvg_mid = (c1['high'] + c3['low']) / 2.0
                    pending_order_type = 1
                    pending_limit_price = fvg_mid
                    pending_sl = c1['low'] - 1.0
                    pending_timer = 24
                    bullish_hunter_timer = 0
                    print(f"\\n[>] SETUP FOUND: Placed BUY LIMIT at {fvg_mid:.2f}")

            # Print Telemetry
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"=========================================================")
            print(f"              [KESSLER V8 LIVE TELEMETRY]                ")
            print(f"=========================================================")
            print(f"[*] Time:  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"[*] Asset: {PRIMARY_SYMBOL} | Price: {current_close:.2f}")
            print(f"---------------------------------------------------------")
            print(f"[BIG MONEY] StatArb Z-Score: {z_score:+.2f} (Needs 2.0)")
            print(f"[BIG MONEY] VIX Veto:        {'PANIC' if vix_spike else 'CLEAR'}")
            print(f"---------------------------------------------------------")
            
            hunter_status = "IDLE"
            if bearish_hunter_timer > 0: hunter_status = f"BEARISH HUNTER ACTIVE ({bearish_hunter_timer} Ticks)"
            if bullish_hunter_timer > 0: hunter_status = f"BULLISH HUNTER ACTIVE ({bullish_hunter_timer} Ticks)"
            print(f"[STATE]     Hunter Mode:     {hunter_status}")
            
            order_status = "NONE"
            if pending_timer > 0:
                side = "BUY LIMIT" if pending_order_type == 1 else "SELL LIMIT"
                order_status = f"{side} @ {pending_limit_price:.2f} (Expires in {pending_timer} Ticks)"
            print(f"[STATE]     Pending Orders:  {order_status}")
            
            print(f"=========================================================")

            time.sleep(300) # Wait for next M5 candle
            
    except KeyboardInterrupt:
        print("\\n[*] Engine shutting down...")
        mt5.shutdown()

if __name__ == "__main__":
    run_hybrid_engine()
