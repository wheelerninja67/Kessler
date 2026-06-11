"""
Kessler V1.2 Global Parameter Optimizer (AMD Cycle)
Sweeps parameters across all 3 sessions: Asia (Accumulation), London (Judas Swing), NY (Displacement).
"""
import time as pytime
import sys
import itertools

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except ImportError:
    print("[!] Need: pip install yfinance pandas numpy")
    sys.exit(1)

print("[*] Downloading NQ=F M5 data from Yahoo Finance...")
df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
if df is None or len(df) == 0:
    print("[!] No data")
    sys.exit(1)

timestamps = np.array([int(idx.timestamp()) for idx in df.index])
opens = df['Open'].values.flatten().astype(np.float64)
highs = df['High'].values.flatten().astype(np.float64)
lows = df['Low'].values.flatten().astype(np.float64)
closes = df['Close'].values.flatten().astype(np.float64)

N = len(closes)
print(f"[+] Loaded {N} candles ({df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')})")

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

print("[*] Precomputing ATR and EMAs...")
atr_14 = fast_atr(highs, lows, closes, 14)
ema_50 = fast_ema(closes, 50)
ema_100 = fast_ema(closes, 100)

print("[*] Precomputing time arrays...")
# Convert to EST approximation (YF NQ=F is usually EST)
hours = np.array([pytime.gmtime(ts).tm_hour for ts in timestamps])
weekdays = np.array([pytime.gmtime(ts).tm_wday for ts in timestamps])
days = np.array([f"{pytime.gmtime(ts).tm_year}-{pytime.gmtime(ts).tm_yday}" for ts in timestamps])

# Precompute Asian Range (Let's assume hours 0-8 is Asia, 8-14 is London, 14-21 is NY)
# We will track the rolling Asian High and Low for each day
asian_high = np.zeros(N)
asian_low = np.zeros(N)
current_day = ""
ch = 0.0
cl = 999999.0

for i in range(N):
    day = days[i]
    h = hours[i]
    if day != current_day:
        current_day = day
        ch = highs[i]
        cl = lows[i]
    
    # Asia Accumulation Phase (Hours 0 to 7)
    if h < 8:
        if highs[i] > ch: ch = highs[i]
        if lows[i] < cl: cl = lows[i]
        
    asian_high[i] = ch
    asian_low[i] = cl

print("[*] Starting V1.2 Global Sweep...\n")

def run_global_backtest(params):
    asia_enabled = params['asia_enabled']
    london_enabled = params['london_enabled']
    ny_enabled = params['ny_enabled']
    
    tp_mult = params['tp_mult']
    sl_mult = params['sl_mult']
    risk_pct = 0.01

    balance = 10000.0
    peak = balance
    max_dd_pct = 0.0
    
    wins = 0
    total_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    
    pos_type = 0
    pos_entry = 0.0
    pos_sl = 0.0
    pos_tp = 0.0
    pos_risk = 0.0
    
    # London Judas state tracking
    london_swept_high = False
    london_swept_low = False
    
    for i in range(100, N):
        c = closes[i]
        h = highs[i]
        l = lows[i]
        hour = hours[i]
        atr = atr_14[i]
        day = days[i]
        
        # Position Management
        if pos_type != 0:
            won = False
            lost = False
            if pos_type == 1:
                if l <= pos_sl: lost = True
                elif h >= pos_tp: won = True
            elif pos_type == -1:
                if h >= pos_sl: lost = True
                elif l <= pos_tp: won = True
                
            if won:
                pnl = pos_risk * (tp_mult / sl_mult)
                balance += pnl
                total_profit += pnl
                wins += 1
                total_trades += 1
                pos_type = 0
            elif lost:
                balance -= pos_risk
                total_loss += pos_risk
                total_trades += 1
                pos_type = 0
                
        # Drawdown Tracking
        if balance > peak: peak = balance
        dd = (peak - balance) / peak
        if dd > max_dd_pct: max_dd_pct = dd
        if balance <= 0: break
        
        # New Day Reset
        if i > 0 and days[i] != days[i-1]:
            london_swept_high = False
            london_swept_low = False
            
        if pos_type != 0: continue
        
        signal = 0
        a_high = asian_high[i]
        a_low = asian_low[i]
        
        # 1. ASIA (Mean Reversion inside the box)
        if asia_enabled and hour >= 4 and hour < 8:
            if h >= a_high: signal = -1 # Fade the top
            elif l <= a_low: signal = 1 # Fade the bottom
            
        # 2. LONDON (Judas Swing)
        elif london_enabled and hour >= 8 and hour < 14:
            if h > a_high: london_swept_high = True
            if l < a_low: london_swept_low = True
            
            # If it swept high, and then falls back UNDER the high -> trapped buyers -> SHORT
            if london_swept_high and c < a_high:
                signal = -1
            # If it swept low, and then crosses back ABOVE the low -> trapped sellers -> LONG
            elif london_swept_low and c > a_low:
                signal = 1
                
        # 3. NEW YORK (V1.1 Displacement Breakout)
        elif ny_enabled and hour >= 15 and hour < 21:
            ef = ema_50[i]
            es = ema_100[i]
            if c > es and ef > es and c > a_high:
                signal = 1
            elif c < es and ef < es and c < a_low:
                signal = -1
                
        # Execute Signal
        if signal != 0:
            sl_dist = atr * sl_mult
            tp_dist = atr * tp_mult
            pos_risk = balance * risk_pct
            pos_type = signal
            pos_entry = c
            if signal == 1:
                pos_sl = c - sl_dist
                pos_tp = c + tp_dist
            else:
                pos_sl = c + sl_dist
                pos_tp = c - tp_dist
                
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    pf = total_profit / total_loss if total_loss > 0 else 99.0
    net_return = (balance - 10000) / 10000 * 100
    
    if max_dd_pct >= 0.10 or total_trades < 10:
        score = -999
    else:
        score = (net_return * pf) / (max_dd_pct * 100 + 1)
        
    return {
        'score': score,
        'return': net_return,
        'trades': total_trades,
        'win_rate': win_rate,
        'pf': pf,
        'max_dd': max_dd_pct * 100,
        'params': params
    }

# Parameters to sweep
grid = {
    'asia_enabled': [True, False],
    'london_enabled': [True, False],
    'ny_enabled': [True, False],
    'sl_mult': [1.5, 2.0, 2.5],
    'tp_mult': [3.0, 5.0, 8.0, 11.0]
}

keys = list(grid.keys())
values = list(grid.values())
combinations = list(itertools.product(*values))
total = len(combinations)

print(f"[*] Sweeping {total} AMD Cycle Logic structures...\n")

results = []
for combo in combinations:
    p = dict(zip(keys, combo))
    # Exclude the "all disabled" combo
    if not (p['asia_enabled'] or p['london_enabled'] or p['ny_enabled']):
        continue
    results.append(run_global_backtest(p))

results.sort(key=lambda x: x['score'], reverse=True)
valid = [r for r in results if r['score'] > 0]

print("=" * 85)
print(f"{'ASIA':<6} {'LOND':<6} {'NY':<6} {'SL':<4} {'TP':<4} | {'RETURN':>8} {'TRADES':>7} {'WIN%':>6} {'PF':>6} {'MAX_DD':>7}")
print("=" * 85)

for r in valid[:15]:
    p = r['params']
    asia = "ON" if p['asia_enabled'] else "OFF"
    lond = "ON" if p['london_enabled'] else "OFF"
    ny = "ON" if p['ny_enabled'] else "OFF"
    print(f"{asia:<6} {lond:<6} {ny:<6} {p['sl_mult']:<4.1f} {p['tp_mult']:<4.1f} | {r['return']:>7.1f}% {r['trades']:>7} {r['win_rate']:>5.1f}% {r['pf']:>5.2f} {r['max_dd']:>6.2f}%")

print("=" * 85)
