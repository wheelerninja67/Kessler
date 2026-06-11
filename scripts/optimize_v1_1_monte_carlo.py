"""
Kessler V1.1 MONTE CARLO TORTURE SCRIPT
Randomizes every parameter (including obscure time blocks) to find a high-frequency edge.
"""
import time as pytime
import sys
import random

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

print("[*] Precomputing Arrays...")
atr_14 = fast_atr(highs, lows, closes, 14)
hours = np.array([pytime.gmtime(ts).tm_hour for ts in timestamps])
weekdays = np.array([pytime.gmtime(ts).tm_wday for ts in timestamps])

ema_cache = {p: fast_ema(closes, p) for p in [10, 20, 30, 50, 100, 200]}
breakout_cache = {}
for period in range(5, 51, 5):
    rolling_high = np.empty(N)
    rolling_low = np.empty(N)
    for i in range(period, N):
        rolling_high[i] = np.max(highs[i-period:i])
        rolling_low[i] = np.min(lows[i-period:i])
    rolling_high[:period] = highs[:period]
    rolling_low[:period] = lows[:period]
    breakout_cache[period] = (rolling_high, rolling_low)

def run_random_backtest(params):
    sl_mult = params['sl_mult']
    tp_mult = params['tp_mult']
    bk_period = params['breakout_period']
    ema_f = ema_cache[params['ema_fast']]
    ema_s = ema_cache[params['ema_slow']]
    risk_pct = 0.015
    start_hr = params['session_start']
    end_hr = params['session_end']
    
    local_high, local_low = breakout_cache[bk_period]
    
    balance = 10000.0
    peak = balance
    max_dd = 0.0
    wins = 0
    total_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    
    pos_type = 0
    pos_entry = 0.0
    pos_sl = 0.0
    pos_tp = 0.0
    pos_risk = 0.0
    
    start_idx = max(200, bk_period + 1)
    
    for i in range(start_idx, N):
        c, h, l, hour, wday, atr = closes[i], highs[i], lows[i], hours[i], weekdays[i], atr_14[i]
        
        if pos_type != 0:
            won, lost = False, False
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
                
        if balance > peak: peak = balance
        dd = (peak - balance) / peak if peak > 0 else 0
        if dd > max_dd: max_dd = dd
        if balance <= 0: break
        
        if wday == 4 and pos_type != 0:
            total_trades += 1
            pos_type = 0
            continue
            
        if not (start_hr <= hour < end_hr): continue
        if pos_type != 0: continue
        
        ef, es = ema_f[i], ema_s[i]
        signal = 0
        if c > local_high[i] and c > es and ef > es: signal = 1
        elif c < local_low[i] and c < es and ef < es: signal = -1
        
        if signal != 0:
            sl_dist = atr * sl_mult
            if sl_dist == 0: continue
            pos_risk = balance * risk_pct
            pos_type = signal
            pos_entry = c
            pos_sl = c - sl_dist if signal == 1 else c + sl_dist
            pos_tp = c + (atr * tp_mult) if signal == 1 else c - (atr * tp_mult)
            
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    net_return = (balance - 10000.0) / 100.0
    pf = total_profit / total_loss if total_loss > 0 else 99.0
    
    if max_dd >= 0.045 or total_trades < 25:
        score = -999
    else:
        score = net_return * pf
        
    return {'score': score, 'return': net_return, 'trades': total_trades, 'win_rate': win_rate, 'pf': pf, 'max_dd': max_dd * 100, 'params': params}

print("[*] Generating 10,000 Random Torture Configurations...")

results = []
for _ in range(10000):
    start = random.randint(0, 20)
    end = random.randint(start + 2, 24)
    p = {
        'sl_mult': round(random.uniform(0.5, 3.0), 1),
        'tp_mult': round(random.uniform(1.0, 8.0), 1),
        'breakout_period': random.choice(list(breakout_cache.keys())),
        'ema_fast': random.choice([10, 20, 30]),
        'ema_slow': random.choice([50, 100, 200]),
        'session_start': start,
        'session_end': end
    }
    results.append(run_random_backtest(p))

results.sort(key=lambda x: x['score'], reverse=True)
valid = [r for r in results if r['score'] > 0]

print("=" * 100)
print(f"{'RANK':<5} {'RETURN':>8} {'TRADES':>7} {'WIN%':>6} {'PF':>6} {'MAX_DD':>7} | {'SESS':>7} {'SL':>4} {'TP':>4} {'BK':>4}")
print("=" * 100)

for rank, r in enumerate(valid[:15], 1):
    p = r['params']
    sess = f"{p['session_start']:02d}-{p['session_end']:02d}"
    print(f"{rank:<5} {r['return']:>7.1f}% {r['trades']:>7} {r['win_rate']:>5.1f}% {r['pf']:>5.2f} {r['max_dd']:>6.2f}% | {sess:>7} {p['sl_mult']:>4.1f} {p['tp_mult']:>4.1f} {p['breakout_period']:>4}")
print("=" * 100)
if len(valid) == 0:
    print("[!] 10,000 simulations completed. 0 passed. The noise is absolute.")
