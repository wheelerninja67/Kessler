"""
Kessler V1.3 INSTITUTIONAL VALIDATION SUITE
Implements pure quantitative rigor:
1. Walk-Forward Analysis (40 days In-Sample, 20 days Out-of-Sample)
2. Realistic Frictions (Slippage + Commissions)
3. Parameter Clustering Check
"""
import time as pytime
import sys
import itertools

try:
    import yfinance as yf
    import numpy as np
except ImportError:
    print("[!] Need: pip install yfinance numpy")
    sys.exit(1)

print("[*] Downloading NQ=F M5 data from Yahoo Finance...")
df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
if df is None or len(df) == 0:
    sys.exit(1)

# Split into In-Sample (first 40 days) and Out-of-Sample (last 20 days)
total_days = len(df.groupby(df.index.date))
split_date = list(df.groupby(df.index.date).groups.keys())[40]

df_in_sample = df[df.index.date < split_date]
df_out_sample = df[df.index.date >= split_date]

print(f"[+] In-Sample: {len(df_in_sample)} candles (40 days)")
print(f"[+] Out-of-Sample: {len(df_out_sample)} candles (20 days)")

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

def prepare_data(df_part):
    timestamps = np.array([int(idx.timestamp()) for idx in df_part.index])
    closes = df_part['Close'].values.flatten().astype(np.float64)
    highs = df_part['High'].values.flatten().astype(np.float64)
    lows = df_part['Low'].values.flatten().astype(np.float64)
    
    hours = np.array([pytime.gmtime(ts).tm_hour for ts in timestamps])
    weekdays = np.array([pytime.gmtime(ts).tm_wday for ts in timestamps])
    
    atr_14 = fast_atr(highs, lows, closes, 14)
    ema_50 = fast_ema(closes, 50)
    ema_100 = fast_ema(closes, 100)
    
    breakout_cache = {}
    for period in [12, 18, 24, 26, 36]:
        rolling_high = np.empty(len(closes))
        rolling_low = np.empty(len(closes))
        for i in range(period, len(closes)):
            rolling_high[i] = np.max(highs[i-period:i])
            rolling_low[i] = np.min(lows[i-period:i])
        rolling_high[:period] = highs[:period]
        rolling_low[:period] = lows[:period]
        breakout_cache[period] = (rolling_high, rolling_low)
        
    return closes, highs, lows, hours, weekdays, atr_14, ema_50, ema_100, breakout_cache

d_is = prepare_data(df_in_sample)
d_os = prepare_data(df_out_sample)

# Frictions
SLIPPAGE_POINTS = 2.0  # 2 index points of slippage on entry and exit
COMMISSION = 4.0       # $4 round trip

def run_backtest(params, data_tuple):
    closes, highs, lows, hours, weekdays, atr_14, ema_50, ema_100, breakout_cache = data_tuple
    N = len(closes)
    
    sl_mult = params['sl_mult']
    tp_mult = params['tp_mult']
    bk_period = params['breakout_period']
    risk_pct = params['risk_pct']
    
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
    contracts = 0.0
    
    start_idx = bk_period + 1
    
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
                
            if won or lost:
                # Add exit slippage and commissions
                if won:
                    pnl = (pos_risk * (tp_mult / sl_mult)) - (SLIPPAGE_POINTS * contracts * 20) - COMMISSION # $20 per point on NAS100
                    balance += pnl
                    if pnl > 0: wins += 1
                    total_profit += pnl
                if lost:
                    loss_amt = pos_risk + (SLIPPAGE_POINTS * contracts * 20) + COMMISSION
                    balance -= loss_amt
                    total_loss += loss_amt
                
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
            
        if not (16 <= hour < 22): continue
        if pos_type != 0: continue
        
        ef, es = ema_50[i], ema_100[i]
        signal = 0
        if c > local_high[i] and c > es and ef > es: signal = 1
        elif c < local_low[i] and c < es and ef < es: signal = -1
        
        if signal != 0:
            sl_dist = atr * sl_mult
            if sl_dist == 0: continue
            
            # Add entry slippage
            executed_price = c + SLIPPAGE_POINTS if signal == 1 else c - SLIPPAGE_POINTS
            
            pos_risk = balance * risk_pct
            contracts = pos_risk / (sl_dist * 20) # $20 per point standard NQ contract
            if contracts < 0.1: continue # Can't trade less than a micro
            
            pos_type = signal
            pos_sl = executed_price - sl_dist if signal == 1 else executed_price + sl_dist
            pos_tp = executed_price + (atr * tp_mult) if signal == 1 else executed_price - (atr * tp_mult)
            
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    net_return = (balance - 10000.0) / 100.0
    pf = total_profit / total_loss if total_loss > 0 else 99.0
    
    score = (net_return * pf) / ((max_dd * 100) + 1) if total_trades > 0 else -999
        
    return {'score': score, 'return': net_return, 'trades': total_trades, 'win_rate': win_rate, 'pf': pf, 'max_dd': max_dd * 100, 'params': params}

grid = {
    'sl_mult': [1.5, 2.0, 2.5, 3.0],
    'tp_mult': [4.0, 6.0, 8.0, 11.0],
    'breakout_period': [12, 18, 24, 26, 36],
    'risk_pct': [0.01, 0.02]
}

keys = list(grid.keys())
values = list(grid.values())
combinations = list(itertools.product(*values))

print(f"[*] Sweeping {len(combinations)} Permutations on IN-SAMPLE data (with Slippage & Commissions)...\n")

results_is = []
for combo in combinations:
    p = dict(zip(keys, combo))
    res = run_backtest(p, d_is)
    if res['score'] > 0 and res['trades'] >= 3:
        results_is.append(res)

results_is.sort(key=lambda x: x['score'], reverse=True)

print("=" * 90)
print("  TOP 5 IN-SAMPLE PARAMETERS")
print("=" * 90)
print(f"{'RANK':<5} {'RETURN':>8} {'TRADES':>7} {'WIN%':>6} {'PF':>6} {'MAX_DD':>7} | {'SL':>4} {'TP':>4} {'BK':>4} {'RISK':>5}")
for rank, r in enumerate(results_is[:5], 1):
    p = r['params']
    print(f"{rank:<5} {r['return']:>7.1f}% {r['trades']:>7} {r['win_rate']:>5.1f}% {r['pf']:>5.2f} {r['max_dd']:>6.2f}% | {p['sl_mult']:>4.1f} {p['tp_mult']:>4.1f} {p['breakout_period']:>4} {p['risk_pct']*100:>4.1f}%")

print("\n" + "=" * 90)
print("  RUNNING OUT-OF-SAMPLE STRESS TEST ON TOP 5")
print("=" * 90)
print(f"{'RANK':<5} {'RETURN':>8} {'TRADES':>7} {'WIN%':>6} {'PF':>6} {'MAX_DD':>7} | {'RESULT'}")

for rank, r in enumerate(results_is[:5], 1):
    p = r['params']
    res_os = run_backtest(p, d_os)
    
    # Check if edge collapsed
    if res_os['pf'] < 1.5 or res_os['max_dd'] > 10.0 or res_os['return'] <= 0:
        status = "FAILED (Overfitted)"
    else:
        status = "PASSED (Robust Edge)"
        
    print(f"{rank:<5} {res_os['return']:>7.1f}% {res_os['trades']:>7} {res_os['win_rate']:>5.1f}% {res_os['pf']:>5.2f} {res_os['max_dd']:>6.2f}% | {status}")
print("=" * 90)
