"""
Kessler V1.1 HIGH-FREQUENCY SPEED OPTIMIZER
Target: Maximize absolute cash flow within a 60-day window (August 11 Deadline).
Constraint: Max Drawdown < 4.5%
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
    sys.exit(1)

timestamps = np.array([int(idx.timestamp()) for idx in df.index])
opens = df['Open'].values.flatten().astype(np.float64)
highs = df['High'].values.flatten().astype(np.float64)
lows = df['Low'].values.flatten().astype(np.float64)
closes = df['Close'].values.flatten().astype(np.float64)

N = len(closes)

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

atr_14 = fast_atr(highs, lows, closes, 14)
ema_20 = fast_ema(closes, 20)
ema_50 = fast_ema(closes, 50)
ema_100 = fast_ema(closes, 100)

hours = np.array([pytime.gmtime(ts).tm_hour for ts in timestamps])
weekdays = np.array([pytime.gmtime(ts).tm_wday for ts in timestamps])
days = np.array([f"{pytime.gmtime(ts).tm_year}-{pytime.gmtime(ts).tm_yday}" for ts in timestamps])

breakout_cache = {}
for period in [8, 12, 18]:
    rolling_high = np.empty(N)
    rolling_low = np.empty(N)
    for i in range(period, N):
        rolling_high[i] = np.max(highs[i-period:i])
        rolling_low[i] = np.min(lows[i-period:i])
    rolling_high[:period] = highs[:period]
    rolling_low[:period] = lows[:period]
    breakout_cache[period] = (rolling_high, rolling_low)

def run_speed_backtest(params):
    sl_mult = params['sl_mult']
    tp_mult = params['tp_mult']
    breakout_period = params['breakout_period']
    ema_fast = ema_20 if params['ema_fast'] == 20 else ema_50
    ema_slow = ema_50 if params['ema_slow'] == 50 else ema_100
    risk_pct = 0.015 # 1.5% Risk to compound faster
    
    local_high, local_low = breakout_cache[breakout_period]
    
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
    
    start_idx = max(100, breakout_period + 1)
    
    for i in range(start_idx, N):
        c = closes[i]
        h = highs[i]
        l = lows[i]
        hour = hours[i]
        wday = weekdays[i]
        atr = atr_14[i]
        
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
                wins += 1
                total_trades += 1
                total_profit += pnl
                pos_type = 0
            elif lost:
                balance -= pos_risk
                losses = 1
                total_trades += 1
                total_loss += pos_risk
                pos_type = 0
                
        if balance > peak: peak = balance
        dd = (peak - balance) / peak if peak > 0 else 0
        if dd > max_dd_pct: max_dd_pct = dd
        if balance <= 0: break
        
        if wday == 4:
            if pos_type != 0:
                total_trades += 1
                pos_type = 0
            continue
            
        if not (15 <= hour < 22):
            continue
            
        if pos_type != 0: continue
        
        ef = ema_fast[i]
        es = ema_slow[i]
        
        is_uptrend = c > es and ef > es
        is_downtrend = c < es and ef < es
        
        lh = local_high[i]
        ll = local_low[i]
        
        signal = 0
        if c > lh and is_uptrend: signal = 1
        elif c < ll and is_downtrend: signal = -1
        
        if signal != 0:
            sl_dist = atr * sl_mult
            tp_dist = atr * tp_mult
            if sl_dist == 0: continue
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
    net_return = (balance - 10000.0) / 10000.0 * 100
    pf = total_profit / total_loss if total_loss > 0 else 99.0
    
    # Target: At least 30 trades in 60 days (1 trade every 2 days on average)
    if max_dd_pct >= 0.045 or total_trades < 30:
        score = -999
    else:
        score = net_return * pf
        
    return {
        'score': score,
        'return': net_return,
        'trades': total_trades,
        'win_rate': win_rate,
        'pf': pf,
        'max_dd': max_dd_pct * 100,
        'params': params
    }

grid = {
    'sl_mult': [1.0, 1.5, 2.0],
    'tp_mult': [2.0, 3.0, 4.0, 5.0],
    'breakout_period': [8, 12, 18],
    'ema_fast': [20, 50],
    'ema_slow': [50, 100]
}

keys = list(grid.keys())
values = list(grid.values())
combinations = list(itertools.product(*values))

print(f"[*] Sweeping {len(combinations)} Speed Combinations...\n")

results = []
for combo in combinations:
    p = dict(zip(keys, combo))
    results.append(run_speed_backtest(p))

results.sort(key=lambda x: x['score'], reverse=True)
valid = [r for r in results if r['score'] > 0]

print("=" * 80)
print(f"{'RANK':<5} {'RETURN':>8} {'TRADES':>7} {'WIN%':>6} {'PF':>6} {'MAX_DD':>7} {'SL':>4} {'TP':>4} {'BK':>4}")
print("=" * 80)

for rank, r in enumerate(valid[:15], 1):
    p = r['params']
    print(f"{rank:<5} {r['return']:>7.1f}% {r['trades']:>7} {r['win_rate']:>5.1f}% {r['pf']:>5.2f} {r['max_dd']:>6.2f}% {p['sl_mult']:>4.1f} {p['tp_mult']:>4.1f} {p['breakout_period']:>4}")
print("=" * 80)
