"""
Kessler V1.1 Parameter Optimizer
Sweeps SL/TP multipliers, breakout period, and strategy features.
Finds the combination that maximizes returns while keeping max DD under 10%.
"""
import time as pytime
import math
import sys
import itertools

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except ImportError:
    print("[!] Need: pip install yfinance pandas numpy")
    sys.exit(1)

# ===== FETCH DATA ONCE =====
print("[*] Downloading NQ=F M5 data from Yahoo Finance...")
df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
if df is None or len(df) == 0:
    print("[!] No data")
    sys.exit(1)

# Convert to numpy arrays for speed
timestamps = np.array([int(idx.timestamp()) for idx in df.index])
opens = df['Open'].values.flatten().astype(np.float64)
highs = df['High'].values.flatten().astype(np.float64)
lows = df['Low'].values.flatten().astype(np.float64)
closes = df['Close'].values.flatten().astype(np.float64)
volumes = df['Volume'].values.flatten().astype(np.float64)

N = len(closes)
print(f"[+] Loaded {N} candles ({df.index[0].strftime('%Y-%m-%d')} → {df.index[-1].strftime('%Y-%m-%d')})")

# ===== PRECOMPUTE HELPERS =====
def fast_ema(prices, period):
    """Compute EMA series"""
    ema = np.empty_like(prices)
    ema[0] = prices[0]
    mult = 2.0 / (period + 1)
    for i in range(1, len(prices)):
        ema[i] = (prices[i] - ema[i-1]) * mult + ema[i-1]
    return ema

def fast_atr(highs, lows, closes, period=14):
    """Compute ATR series"""
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

# Precompute ATR (doesn't change with strategy params)
print("[*] Precomputing ATR...")
atr_14 = fast_atr(highs, lows, closes, 14)

# Precompute EMAs for different periods
print("[*] Precomputing EMAs...")
ema_cache = {}
for p in [10, 20, 50, 100, 200, 300]:
    ema_cache[p] = fast_ema(closes, p)

# Precompute hours and weekdays from timestamps
print("[*] Precomputing time filters...")
hours = np.array([pytime.gmtime(ts).tm_hour for ts in timestamps])
weekdays = np.array([pytime.gmtime(ts).tm_wday for ts in timestamps])
days = np.array([f"{pytime.gmtime(ts).tm_year}-{pytime.gmtime(ts).tm_mon:02d}-{pytime.gmtime(ts).tm_mday:02d}" for ts in timestamps])

# Precompute rolling highs/lows for different breakout periods
print("[*] Precomputing breakout levels...")
breakout_cache = {}
for period in [12, 18, 20, 24, 26, 36, 48, 72, 96]:
    rolling_high = np.empty(N)
    rolling_low = np.empty(N)
    for i in range(period, N):
        rolling_high[i] = np.max(highs[i-period:i])
        rolling_low[i] = np.min(lows[i-period:i])
    rolling_high[:period] = highs[:period]
    rolling_low[:period] = lows[:period]
    breakout_cache[period] = (rolling_high, rolling_low)

print("[*] Precomputation done. Starting parameter sweep...\n")

# ===== BACKTEST FUNCTION =====
def run_backtest(params):
    sl_mult = params['sl_mult']
    tp_mult = params['tp_mult']
    breakout_period = params['breakout_period']
    ema_fast_p = params['ema_fast']
    ema_slow_p = params['ema_slow']
    risk_pct = params['risk_pct']
    trailing_be = params['trailing_be']
    min_atr_filter = params['min_atr_filter']
    ema_gap_filter = params['ema_gap_filter']
    session_start = params['session_start']
    session_end = params['session_end']
    max_trades_day = params['max_trades_day']
    
    ema_fast = ema_cache[ema_fast_p]
    ema_slow = ema_cache[ema_slow_p]
    local_high, local_low = breakout_cache[breakout_period]
    
    balance = 900000.0
    peak = balance
    max_dd_pct = 0.0
    
    total_trades = 0
    wins = 0
    losses = 0
    total_profit = 0.0
    total_loss_amt = 0.0
    
    # Open position tracking
    pos_type = 0  # 0=none, 1=buy, -1=sell
    pos_entry = 0.0
    pos_sl = 0.0
    pos_tp = 0.0
    pos_risk_amt = 0.0
    pos_sl_dist = 0.0
    pos_trailing_activated = False
    
    circuit_trips = 0
    daily_pnl = {}
    trades_by_day = {}
    
    start_idx = max(1000, breakout_period + 1)
    
    # Median ATR for min_atr_filter
    median_atr = np.median(atr_14[start_idx:]) if min_atr_filter else 0
    
    for i in range(start_idx, N):
        c = closes[i]
        h = highs[i]
        l = lows[i]
        hour = hours[i]
        wday = weekdays[i]
        day = days[i]
        atr = atr_14[i]
        
        # === MANAGE OPEN POSITION ===
        if pos_type != 0:
            trade_won = False
            trade_lost = False
            
            # Trailing stop to breakeven
            if trailing_be and not pos_trailing_activated:
                if pos_type == 1 and h >= pos_entry + pos_sl_dist:
                    pos_sl = pos_entry + 1.0  # Move SL to breakeven + 1 point
                    pos_trailing_activated = True
                elif pos_type == -1 and l <= pos_entry - pos_sl_dist:
                    pos_sl = pos_entry - 1.0
                    pos_trailing_activated = True
            
            if pos_type == 1:
                if l <= pos_sl:
                    trade_lost = True
                elif h >= pos_tp:
                    trade_won = True
            elif pos_type == -1:
                if h >= pos_sl:
                    trade_lost = True
                elif l <= pos_tp:
                    trade_won = True
            
            if trade_won:
                pnl = pos_risk_amt * (tp_mult / sl_mult)
                balance += pnl
                wins += 1
                total_trades += 1
                total_profit += pnl
                daily_pnl[day] = daily_pnl.get(day, 0) + pnl
                pos_type = 0
            elif trade_lost:
                if pos_trailing_activated:
                    # Breakeven stop — minimal loss/gain
                    pnl = 0  # Approximately breakeven
                    balance += pnl
                    total_trades += 1
                    # Count as neither win nor loss
                else:
                    pnl = pos_risk_amt
                    balance -= pnl
                    losses += 1
                    total_trades += 1
                    total_loss_amt += pnl
                    daily_pnl[day] = daily_pnl.get(day, 0) - pnl
                pos_type = 0
        
        # === DRAWDOWN ===
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak if peak > 0 else 0
        if dd > max_dd_pct:
            max_dd_pct = dd
        
        if balance <= 0:
            break
        
        # === FRIDAY KILL ===
        if wday == 4:
            if pos_type != 0:
                # Close at market
                total_trades += 1
                pos_type = 0
            continue
        
        # === CIRCUIT BREAKER ===
        day_pnl = daily_pnl.get(day, 0)
        if day_pnl < 0 and abs(day_pnl) / balance >= 0.028:
            circuit_trips += 1
            continue
        
        # === SESSION FILTER ===
        if not (session_start <= hour < session_end):
            continue
        
        # === MAX TRADES ===
        trades_by_day[day] = trades_by_day.get(day, 0)
        if trades_by_day.get(day, 0) >= max_trades_day:
            continue
        
        # === ALREADY IN POSITION ===
        if pos_type != 0:
            continue
        
        # === STRATEGY LOGIC ===
        ef = ema_fast[i]
        es = ema_slow[i]
        
        is_uptrend = c > es and ef > es
        is_downtrend = c < es and ef < es
        
        # EMA gap filter — require meaningful trend
        if ema_gap_filter:
            ema_gap = abs(ef - es) / es
            if ema_gap < 0.002:  # Less than 0.2% gap = chop zone
                continue
        
        # Min ATR filter — skip low volatility
        if min_atr_filter and atr < median_atr * 0.5:
            continue
        
        lh = local_high[i]
        ll = local_low[i]
        
        signal = 0
        if c > lh and is_uptrend:
            signal = 1
        elif c < ll and is_downtrend:
            signal = -1
        
        if signal == 0:
            continue
        
        # === OPEN TRADE ===
        sl_dist = atr * sl_mult
        tp_dist = atr * tp_mult
        
        if sl_dist == 0:
            continue
        
        risk_amt = balance * risk_pct
        
        pos_type = signal
        pos_entry = c
        pos_sl_dist = sl_dist
        pos_trailing_activated = False
        
        if signal == 1:
            pos_sl = c - sl_dist
            pos_tp = c + tp_dist
        else:
            pos_sl = c + sl_dist
            pos_tp = c - tp_dist
        
        pos_risk_amt = risk_amt
        trades_by_day[day] = trades_by_day.get(day, 0) + 1
    
    # === RESULTS ===
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    net_profit = balance - 900000.0
    net_return = net_profit / 900000.0 * 100
    pf = total_profit / total_loss_amt if total_loss_amt > 0 else 99.0
    
    # Composite score: maximize returns while penalizing drawdown
    # Must keep max DD < 10% for prop firm
    if max_dd_pct >= 0.10:
        score = -999  # Disqualified
    elif total_trades < 5:
        score = -999  # Too few trades
    else:
        score = (net_return * pf) / (max_dd_pct * 100 + 1)
    
    return {
        'score': score,
        'net_return': net_return,
        'net_profit': net_profit,
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'profit_factor': pf,
        'max_dd_pct': max_dd_pct * 100,
        'circuit_trips': circuit_trips,
        'balance': balance,
        'params': params,
    }

# ===== PARAMETER SWEEP =====
param_grid = {
    'sl_mult': [1.0, 1.5, 1.8, 2.0, 2.5, 3.0],
    'tp_mult': [4.0, 6.0, 8.0, 10.0, 11.0, 15.0],
    'breakout_period': [12, 18, 24, 26, 36, 48, 72],
    'ema_fast': [20, 50],
    'ema_slow': [100, 200],
    'risk_pct': [0.01],
    'trailing_be': [False, True],
    'min_atr_filter': [False, True],
    'ema_gap_filter': [False, True],
    'session_start': [15, 16, 17],
    'session_end': [21, 22, 23],
    'max_trades_day': [1, 2],
}

# Generate all combinations
keys = list(param_grid.keys())
values = list(param_grid.values())
combinations = list(itertools.product(*values))
total_combos = len(combinations)

print(f"[*] Sweeping {total_combos} parameter combinations...")
print(f"[*] This may take a few minutes...\n")

results = []
start_time = pytime.time()

for idx, combo in enumerate(combinations):
    params = dict(zip(keys, combo))
    result = run_backtest(params)
    results.append(result)
    
    if (idx + 1) % 100 == 0:
        elapsed = pytime.time() - start_time
        rate = (idx + 1) / elapsed
        remaining = (total_combos - idx - 1) / rate
        print(f"  [{idx+1}/{total_combos}] {elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining")

elapsed = pytime.time() - start_time
print(f"\n[+] Sweep complete in {elapsed:.1f}s")

# Sort by score
results.sort(key=lambda x: x['score'], reverse=True)

# Filter valid results
valid = [r for r in results if r['score'] > 0]
print(f"[+] {len(valid)}/{total_combos} combinations passed (DD < 10%, trades >= 5)\n")

# ===== DISPLAY TOP 10 =====
print("=" * 100)
print(f"{'RANK':<5} {'RETURN':>8} {'TRADES':>7} {'WIN%':>6} {'PF':>6} {'MAX_DD':>7} {'CB':>4} {'SL':>5} {'TP':>5} {'BK':>4} {'RISK':>6} {'TRAIL':>6} {'ATR_F':>6} {'EMA_G':>6} {'SCORE':>8}")
print("=" * 100)

for rank, r in enumerate(valid[:20], 1):
    p = r['params']
    print(f"{rank:<5} {r['net_return']:>7.1f}% {r['total_trades']:>7} {r['win_rate']:>5.1f}% {r['profit_factor']:>5.2f} {r['max_dd_pct']:>6.2f}% {r['circuit_trips']:>4} {p['sl_mult']:>5.1f} {p['tp_mult']:>5.1f} {p['breakout_period']:>4} {p['risk_pct']*100:>5.1f}% {str(p['trailing_be']):>6} {str(p['min_atr_filter']):>6} {str(p['ema_gap_filter']):>6} {r['score']:>8.1f}")

print("=" * 100)

# ===== BEST RESULT DETAIL =====
if valid:
    best = valid[0]
    bp = best['params']
    
    print(f"\n{'='*60}")
    print(f"  🏆 OPTIMAL PARAMETERS")
    print(f"{'='*60}")
    print(f"  SL ATR Multiplier:    {bp['sl_mult']}")
    print(f"  TP ATR Multiplier:    {bp['tp_mult']}")
    print(f"  R/R Ratio:            1:{bp['tp_mult']/bp['sl_mult']:.1f}")
    print(f"  Breakout Period:      {bp['breakout_period']} candles ({bp['breakout_period']*5/60:.1f} hours)")
    print(f"  EMA Fast/Slow:        {bp['ema_fast']}/{bp['ema_slow']}")
    print(f"  Risk Per Trade:       {bp['risk_pct']*100:.2f}%")
    print(f"  Trailing BE:          {bp['trailing_be']}")
    print(f"  Min ATR Filter:       {bp['min_atr_filter']}")
    print(f"  EMA Gap Filter:       {bp['ema_gap_filter']}")
    print(f"  Session:              {bp['session_start']}-{bp['session_end']} broker time")
    print(f"{'='*60}")
    print(f"  Net Return:           {best['net_return']:.2f}%")
    print(f"  Net Profit:           ₹{best['net_profit']:,.0f}")
    print(f"  Total Trades:         {best['total_trades']}")
    print(f"  Win Rate:             {best['win_rate']:.1f}%")
    print(f"  Profit Factor:        {best['profit_factor']:.2f}")
    print(f"  Max Drawdown:         {best['max_dd_pct']:.2f}%")
    print(f"  Circuit Breaker Trips:{best['circuit_trips']}")
    print(f"  Final Balance:        ₹{best['balance']:,.0f}")
    print(f"{'='*60}")
    
    # Compare with baseline
    baseline_params = {
    'sl_mult': 2.0,
    'tp_mult': 6.0,
    'breakout_period': 48,
    'ema_fast': 50,
    'ema_slow': 200,
    'risk_pct': 0.01,
    'trailing_be': False,
    'min_atr_filter': False,
    'ema_gap_filter': False,
    'session_start': 16,
    'session_end': 23,
    'max_trades_day': 2,
}
    try:
        baseline = run_backtest(baseline_params)
        print(f"  Old V1.1 Net Return:  {baseline['net_return']:.2f}%")
        print(f"  Improvement:          +{best['net_return'] - baseline['net_return']:.2f}%")
    except Exception as e:
        pass
    
    print(f"  Max DD:    {baseline['max_dd_pct']:.1f}% → {best['max_dd_pct']:.1f}%  ({best['max_dd_pct']-baseline['max_dd_pct']:+.1f}%)")
    print(f"  Win Rate:  {baseline['win_rate']:.1f}% → {best['win_rate']:.1f}%  ({best['win_rate']-baseline['win_rate']:+.1f}%)")
    print(f"  PF:        {baseline['profit_factor']:.2f} → {best['profit_factor']:.2f}")
    print(f"  CB Trips:  {baseline['circuit_trips']} → {best['circuit_trips']}")
