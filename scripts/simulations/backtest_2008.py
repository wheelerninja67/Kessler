#!/usr/bin/env python3
import pandas as pd
import numpy as np
import subprocess
import re
import os
import random
from datetime import datetime

# =============================================================================
# KESSLER HISTORICAL BACKTEST & ENGINE CALIBRATION
# =============================================================================
# This script removes the "vaporware" limitation by physically linking the 
# Kessler Zig engine's parameters to real-world market volatility.
# 
# Mapping:
# - High Volatility (VIX equivalent) -> High systemic leverage cap
# - Low Market Returns -> Shallow base depth (liquidity vacuum)
# =============================================================================

PRICES_FILE = "data/2008_crash/prices.csv"
INITIAL_CAPITAL = 65000.0

def run_kessler_probe(leverage_cap, base_depth, seed):
    """Write a probe scenario and run Kessler to test fragility."""
    scenario_yaml = f"""
name: Daily Probe
count: 100000
leverage_cap: {leverage_cap}
base_depth: {base_depth}
decay_rate: 0.10
forward_ticks: 100
shocks:
  - tick: 10
    type: systemic
    agent_ids: [0, 1, 2, 3, 4]
    asset_id: 0
    magnitude: 2.0
"""
    with open("data/temp_probe.yaml", "w") as f:
        f.write(scenario_yaml)

    cmd = [
        "/home/mid/.local/bin/kessler",
        "--scenario", "data/temp_probe.yaml",
        "--seed", str(seed)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

def parse_output(output):
    """Parse the engine output for cascade depth and defaults."""
    defaults = 0
    cascade = 0
    for line in output.split("\n"):
        match = re.search(r"DEFAULTS:\s*(\d+)\s*\|\s*CAS:\s*(\d+)", line)
        if match:
            defaults = max(defaults, int(match.group(1)))
            cascade = max(cascade, int(match.group(2)))
    return defaults, cascade

def main():
    if not os.path.exists(PRICES_FILE):
        print(f"[!] {PRICES_FILE} not found. Ensure fetch_data.py has finished.")
        return

    print("[*] Loading historical market data...")
    df = pd.read_csv(PRICES_FILE, index_col=0)
    df.index = pd.to_datetime(df.index, errors='coerce')
    df = df[df.index.notna()]
    
    # We use S&P 500 (^GSPC) as the global macro proxy
    spx = pd.to_numeric(df['^GSPC'], errors='coerce')
    spx = spx.dropna()
    
    # Calculate 30-day rolling volatility (annualized)
    returns = np.log(spx / spx.shift(1))
    volatility = returns.rolling(window=30).std() * np.sqrt(252) * 100
    
    # Filter to the core crash period: August 2008 to Dec 2008
    start_date = "2008-08-01"
    end_date = "2008-12-31"
    
    test_dates = spx.loc[start_date:end_date].index
    
    print("\n=======================================================")
    print(" KESSLER FRAGILITY PROBE: THE 2008 LEHMAN CRASH")
    print("=======================================================\n")
    
    position = None
    cash = INITIAL_CAPITAL
    shares = 0
    entry_price = 0
    
    for date in test_dates:
        price = spx.loc[date]
        vol = volatility.loc[date]
        
        if pd.isna(vol):
            continue
            
        # -----------------------------------------------------
        # THE KESSLER MAPPING FUNCTION (REAL DATA -> PHYSICS)
        # -----------------------------------------------------
        # Normal vol (~15) -> leverage 3.0
        # Crash vol (~80) -> leverage 8.0+
        mapped_leverage = 2.0 + (vol / 15.0)
        
        # Normal depth -> 1000
        # Crash depth -> 200 (liquidity dries up)
        mapped_depth = max(100, 1500 - (vol * 15))
        
        seed = random.randint(1000, 9999)
        
        # Run the engine
        out = run_kessler_probe(mapped_leverage, mapped_depth, seed)
        defaults, cascade = parse_output(out)
        
        date_str = str(date)[:10]
        print(f"[{date_str}] SPX: ${price:.2f} | Lev: {mapped_leverage:.2f}x | Defaults: {defaults:,}")
        
        # -----------------------------------------------------
        # SIGNAL EVALUATION
        # -----------------------------------------------------
        if defaults > 25000 and cascade >= 1:
            print(f"  [!!!] KESSLER CASCADE DETECTED: {defaults:,} defaults (Depth: {cascade})")
            
            if position is None:
                # Open SHORT position
                position = "SHORT"
                entry_price = price
                shares = int(cash / price)
                print(f"  [ACTION] Executed SHORT on {shares} shares of SPX @ ${price:.2f}")
        else:
            if position == "SHORT":
                # Check for take-profit or exit if volatility normalizes
                profit = (entry_price - price) * shares
                if price < entry_price * 0.85: # 15% drop captured
                    print(f"  [ACTION] Taking profit! Market dumped 15%.")
                    cash += profit
                    print(f"  [CLOSED] PnL: +${profit:.2f} | New Capital: ${cash:.2f}")
                    position = None
        
    print("\n=======================================================")
    print(" BACKTEST COMPLETE")
    print(f" Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    if position == "SHORT":
        profit = (entry_price - spx.loc[end_date]) * shares
        cash += profit
    print(f" Final Capital:   ${cash:,.2f}")
    print(f" Total Return:    {((cash - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100:.2f}%")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
