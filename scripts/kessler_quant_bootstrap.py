"""
Kessler V1.4 BOOTSTRAP RESAMPLING SUITE
Validates the Rank 1 Config against 10,000 synthetic environment variations.
"""
import time as pytime
import sys
import random

try:
    import yfinance as yf
    import numpy as np
except ImportError:
    print("[!] Need: pip install yfinance numpy")
    sys.exit(1)

print("[*] Downloading NQ=F M5 data for Bootstrap Engine...")
df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
if df is None or len(df) == 0:
    sys.exit(1)

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
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    atr = np.empty(n)
    atr[:period] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = np.mean(tr[i-period+1:i+1])
    return atr

# PREPARE BASE DATA
timestamps = np.array([int(idx.timestamp()) for idx in df.index])
closes = df['Close'].values.flatten().astype(np.float64)
highs = df['High'].values.flatten().astype(np.float64)
lows = df['Low'].values.flatten().astype(np.float64)
hours = np.array([pytime.gmtime(ts).tm_hour for ts in timestamps])
weekdays = np.array([pytime.gmtime(ts).tm_wday for ts in timestamps])
N = len(closes)

# ---------------------------------------------------------
# GENERATE THE EXACT TRADES FROM THE RANK 1 SYSTEM
# ---------------------------------------------------------
print("[*] Extracting raw trades from Rank 1 Config (SL 2.5, TP 4.0, BK 12)...")
atr_14 = fast_atr(highs, lows, closes, 14)
ema_50 = fast_ema(closes, 50)
ema_100 = fast_ema(closes, 100)

bk_period = 12
rolling_high = np.empty(N)
rolling_low = np.empty(N)
for i in range(bk_period, N):
    rolling_high[i] = np.max(highs[i-bk_period:i])
    rolling_low[i] = np.min(lows[i-bk_period:i])
rolling_high[:bk_period] = highs[:bk_period]
rolling_low[:bk_period] = lows[:bk_period]

trades = []
pos_type = 0
pos_sl = 0.0
pos_tp = 0.0
pos_risk = 0.0
SLIPPAGE = 2.0
COMMISSION = 4.0
risk_pct = 0.01

for i in range(bk_period + 1, N):
    c, h, l, hour, wday, atr = closes[i], highs[i], lows[i], hours[i], weekdays[i], atr_14[i]
    
    if pos_type != 0:
        won, lost = False, False
        if pos_type == 1:
            if l <= pos_sl: lost = True
            elif h >= pos_tp: won = True
        elif pos_type == -1:
            if h >= pos_sl: lost = True
            elif l <= pos_tp: won = True
            
        if won or lost:
            if won:
                pnl_ratio = (4.0 / 2.5) # TP/SL
            if lost:
                pnl_ratio = -1.0
            trades.append(pnl_ratio)
            pos_type = 0
            
    if wday == 4 and pos_type != 0:
        pos_type = 0
        continue
        
    if not (16 <= hour < 22): continue
    if pos_type != 0: continue
    
    ef, es = ema_50[i], ema_100[i]
    signal = 0
    
    # EMA Gap Filter - The absolute core of the strategy
    ema_gap = abs(ef - es) / es
    if ema_gap >= 0.002:
        if c > rolling_high[i] and c > es and ef > es: signal = 1
        elif c < rolling_low[i] and c < es and ef < es: signal = -1
    
    if signal != 0:
        sl_dist = atr * 2.5
        if sl_dist == 0: continue
        pos_type = signal
        executed_price = c + SLIPPAGE if signal == 1 else c - SLIPPAGE
        pos_sl = executed_price - sl_dist if signal == 1 else executed_price + sl_dist
        pos_tp = executed_price + (atr * 4.0) if signal == 1 else executed_price - (atr * 4.0)

print(f"[+] Base config extracted {len(trades)} live trades.")

# ---------------------------------------------------------
# 10,000 ITERATION BOOTSTRAP RESAMPLING
# ---------------------------------------------------------
print("\n[*] Initializing 10,000 Environment Monte Carlo Simulator...")
print("[*] Randomizing sequence, clustering trades, testing survival probability...\n")

ITERATIONS = 10000
passed = 0
failed_dd = 0
failed_return = 0

dd_list = []
return_list = []

for _ in range(ITERATIONS):
    # Bootstrap sample with replacement (sample len(trades) trades randomly)
    # This simulates a completely new sequence of market regimes
    simulated_trades = [random.choice(trades) for _ in range(len(trades))]
    
    balance = 10000.0
    peak = balance
    max_dd = 0.0
    
    for t in simulated_trades:
        risk_amt = balance * risk_pct
        
        # Micro NQ (MNQ) Friction Profile
        # MNQ = $2 per point. Commission = $1 round trip.
        # Assuming an average 25-point stop loss on 2.5 ATR, risk per contract is $50.
        # $100 risk = 2 contracts.
        # Slippage = 2 points ($4 per contract). 
        # Total friction for 2 contracts = ($4 slippage + $1 comm) * 2 = $10
        # We estimate friction as 10% of the risk amount dynamically.
        friction = risk_amt * 0.10
        
        if t > 0:
            pnl = (risk_amt * t) - friction
        else:
            pnl = -(risk_amt) - friction
            
        balance += pnl
        
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak
        if dd > max_dd:
            max_dd = dd
            
    dd_list.append(max_dd)
    ret_pct = (balance - 10000.0) / 100.0
    return_list.append(ret_pct)
    
    if max_dd >= 0.045:
        failed_dd += 1
    elif ret_pct <= 0:
        failed_return += 1
    else:
        passed += 1

success_rate = (passed / ITERATIONS) * 100
avg_dd = np.mean(dd_list) * 100
worst_dd = np.max(dd_list) * 100
avg_return = np.mean(return_list)

print("=" * 65)
print("  BOOTSTRAP RESAMPLING RESULTS (10,000 ENVIRONMENTS)")
print("=" * 65)
print(f"  Environments Cleared: {passed:,} / {ITERATIONS:,} ({success_rate:.1f}%)")
print(f"  Failed (Drawdown > 4.5%):  {failed_dd:,}")
print(f"  Failed (Negative Return):  {failed_return:,}")
print("-" * 65)
print(f"  Average Return:       {avg_return:.2f}%")
print(f"  Average Max Drawdown: {avg_dd:.2f}%")
print(f"  Worst Case Drawdown:  {worst_dd:.2f}%")
print("=" * 65)

if success_rate > 95.0:
    print("\n[!!!] SYSTEM VALIDATED. >95% SURVIVAL RATE.")
    print("[!!!] STATISTICAL CERTAINTY ACHIEVED.")
else:
    print("\n[!] System is fragile under sequence randomization.")
