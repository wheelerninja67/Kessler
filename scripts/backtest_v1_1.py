"""
Kessler V1.1 Backtester — NAS100 4H Breakout + EMA Strategy
Pulls historical M5 data from MT5 and replays the exact V1.1 logic:
  1. 50/200 EMA trend filter
  2. 4-hour breakout detection (48 candles)
  3. ATR-based SL (2x) and TP (6x) — 1:3 R/R
  4. Confidence-weighted position sizing (0.5% / 1.5% / 2.45%)
  5. NY session filter (broker hours 16-23)
  6. Max 2 trades per day
  7. Friday kill-switch
  8. 2.8% daily drawdown circuit breaker
"""

import time as pytime
import math
import os
import sys

# Try MT5 for data, fall back to yfinance
USE_MT5 = False
try:
    import MetaTrader5 as mt5
    USE_MT5 = True
except ImportError:
    pass

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("[!] yfinance/pandas not found. Install with: pip install yfinance pandas")
    sys.exit(1)

# ===== STRATEGY PARAMETERS (exact V1.1 match) =====
SYMBOL = "NDX100"
STARTING_BALANCE = 900000.0  # ₹9 lakhs (matching live account)
ATR_PERIOD = 14
SL_ATR_MULT = 1.5   # Optimizer tuned (was 2.0)
TP_ATR_MULT = 10.0  # Optimizer tuned (was 6.0) — 1:6.7 R/R
BREAKOUT_PERIOD = 24  # 2 hours of M5 candles (optimizer: 24 beats 48)
EMA_FAST = 50
EMA_SLOW = 200
EMA_GAP_THRESHOLD = 0.002  # Skip chop zones (optimizer: in ALL top 20)
SESSION_START = 16  # Broker time (UTC+3)
SESSION_END = 23
MAX_TRADES_PER_DAY = 2
CIRCUIT_BREAKER_PCT = 0.028
FRIDAY = 4

# Confidence tiers (without ML volume filter — we can't backtest yfinance volume easily)
# Using fixed mid-tier risk since we don't have the ML model's historical predictions
RISK_PCT_TIERS = {
    'funded_200k': 0.02,  # 2.0% — for $200k account acceleration
    'safe_phase': 0.01,   # 1.0% — bulletproof for prop firm phases
    'aggressive': 0.015,  # 1.5% — mid tier
    'safe': 0.005,        # 0.5% — low confidence
}
BACKTEST_RISK = RISK_PCT_TIERS['safe_phase']  # 1% for prop firm phases

def calc_ema(prices, period):
    """Exact EMA calculation from V1.1"""
    ema = prices[0]
    multiplier = 2.0 / (period + 1)
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calc_atr(rates, period=14):
    """Exact ATR calculation from V1.1"""
    tr_list = []
    for i in range(1, len(rates)):
        high = float(rates[i]['high'])
        low = float(rates[i]['low'])
        prev_close = float(rates[i-1]['close'])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    if len(tr_list) == 0:
        return 2.0
    return sum(tr_list[-period:]) / min(period, len(tr_list))

def fetch_data_mt5():
    """Fetch historical NDX100 M5 data from MT5"""
    if not mt5.initialize():
        print(f"[!] MT5 init failed: {mt5.last_error()}")
        return None
    
    mt5.login(20073104, password="EVoDLj0>E", server="FundingPips-SIM1")
    
    # Request as much history as possible
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 500000)
    mt5.shutdown()
    
    if rates is None or len(rates) == 0:
        print("[!] No data returned from MT5")
        return None
    
    print(f"[+] MT5 returned {len(rates)} M5 candles for {SYMBOL}")
    return rates

def fetch_data_yfinance():
    """Fallback: fetch NQ futures data from Yahoo Finance"""
    print("[*] Fetching NQ=F (Nasdaq futures) from Yahoo Finance...")
    df = yf.download("NQ=F", period="60d", interval="5m", progress=True)
    
    if df is None or len(df) == 0:
        print("[!] No data from yfinance")
        return None
    
    # Convert to list of dicts (same format as MT5)
    rates = []
    for idx, row in df.iterrows():
        ts = int(idx.timestamp())
        rates.append({
            'time': ts,
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'tick_volume': int(row['Volume']) if 'Volume' in row else 0,
        })
    
    print(f"[+] yfinance returned {len(rates)} M5 candles")
    return rates

def run_backtest(rates):
    """Run V1.1 strategy backtest"""
    
    balance = STARTING_BALANCE
    peak = STARTING_BALANCE
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    
    open_positions = []
    trade_log = []
    daily_pnl = {}
    
    # Need at least 1000 candles for 200 EMA warmup
    if len(rates) < 1000:
        print(f"[!] Need at least 1000 candles, got {len(rates)}")
        return
    
    print(f"\n[*] Running backtest over {len(rates)} candles...")
    print(f"[*] Starting balance: ₹{STARTING_BALANCE:,.0f}")
    print(f"[*] Risk per trade: {BACKTEST_RISK*100:.2f}%")
    print(f"[*] R/R: 1:{TP_ATR_MULT/SL_ATR_MULT:.0f} (ATR×{SL_ATR_MULT:.0f} SL, ATR×{TP_ATR_MULT:.0f} TP)")
    print(f"[*] Session filter: broker hours {SESSION_START}-{SESSION_END}")
    print()
    
    circuit_breaker_trips = 0
    no_signal_days = 0
    signal_days = 0
    
    for i in range(1000, len(rates)):
        current = rates[i]
        current_close = float(current['close'])
        current_high = float(current['high'])
        current_low = float(current['low'])
        
        # Get broker hour from candle timestamp
        gm = pytime.gmtime(current['time'])
        current_hour = gm.tm_hour
        current_day = f"{gm.tm_year}-{gm.tm_mon:02d}-{gm.tm_mday:02d}"
        current_weekday = gm.tm_wday  # 0=Monday ... 4=Friday
        
        # === MANAGE OPEN POSITIONS ===
        still_open = []
        for pos in open_positions:
            trade_won = False
            trade_lost = False
            
            if pos['type'] == 'BUY':
                if current_low <= pos['sl']:
                    trade_lost = True
                elif current_high >= pos['tp']:
                    trade_won = True
            elif pos['type'] == 'SELL':
                if current_high >= pos['sl']:
                    trade_lost = True
                elif current_low <= pos['tp']:
                    trade_won = True
            
            if trade_won:
                profit = pos['risk_amount'] * (TP_ATR_MULT / SL_ATR_MULT)
                balance += profit
                winning_trades += 1
                total_trades += 1
                trade_log.append({
                    'day': current_day, 'type': pos['type'], 
                    'result': 'WIN', 'pnl': profit
                })
                daily_pnl[current_day] = daily_pnl.get(current_day, 0) + profit
            elif trade_lost:
                loss = pos['risk_amount']
                balance -= loss
                losing_trades += 1
                total_trades += 1
                trade_log.append({
                    'day': current_day, 'type': pos['type'],
                    'result': 'LOSS', 'pnl': -loss
                })
                daily_pnl[current_day] = daily_pnl.get(current_day, 0) - loss
            else:
                still_open.append(pos)
        
        open_positions = still_open
        
        # === DRAWDOWN TRACKING ===
        if balance > peak:
            peak = balance
        dd_pct = (peak - balance) / peak if peak > 0 else 0
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct
            max_drawdown = peak - balance
        
        # === MARGIN CALL ===
        if balance <= 0:
            print("[!] ACCOUNT BLOWN")
            break
        
        # === FRIDAY KILL-SWITCH ===
        if current_weekday == FRIDAY:
            # Close all open positions at market
            for pos in open_positions:
                pnl = 0
                if pos['type'] == 'BUY':
                    pnl = (current_close - pos['entry']) * (pos['risk_amount'] / (pos['sl_distance']))
                elif pos['type'] == 'SELL':
                    pnl = (pos['entry'] - current_close) * (pos['risk_amount'] / (pos['sl_distance']))
                balance += pnl
                total_trades += 1
                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
            open_positions = []
            continue
        
        # === CIRCUIT BREAKER (2.8% daily DD) ===
        day_pnl = daily_pnl.get(current_day, 0)
        if day_pnl < 0 and abs(day_pnl) / balance >= CIRCUIT_BREAKER_PCT:
            circuit_breaker_trips += 1
            continue  # Skip rest of day
        
        # === SESSION FILTER ===
        if not (SESSION_START <= current_hour < SESSION_END):
            continue
        
        # === MAX TRADES PER DAY ===
        trades_today = sum(1 for t in trade_log if t['day'] == current_day)
        if trades_today >= MAX_TRADES_PER_DAY:
            continue
        
        # === ALREADY IN A POSITION? ===
        if len(open_positions) >= 1:
            continue
        
        # === V1.1 STRATEGY: 4H BREAKOUT + EMA ALIGNMENT ===
        
        # Need 1000 candles of history for accurate EMAs
        historical_slice = rates[i-999:i+1]
        closes = [float(c['close']) for c in historical_slice]
        
        ema_fast_val = calc_ema(closes, EMA_FAST)
        ema_slow_val = calc_ema(closes, EMA_SLOW)
        
        is_uptrend = current_close > ema_slow_val and ema_fast_val > ema_slow_val
        is_downtrend = current_close < ema_slow_val and ema_fast_val < ema_slow_val
        
        # EMA Gap Filter — skip chop zones
        ema_gap = abs(ema_fast_val - ema_slow_val) / ema_slow_val
        if ema_gap < EMA_GAP_THRESHOLD:
            continue
        
        # 4-hour breakout detection
        recent_candles = rates[i-BREAKOUT_PERIOD:i]  # Exclude current candle
        local_high = max(float(c['high']) for c in recent_candles)
        local_low = min(float(c['low']) for c in recent_candles)
        
        signal = 0
        if current_close > local_high and is_uptrend:
            signal = 1  # BUY
        elif current_close < local_low and is_downtrend:
            signal = -1  # SELL
        
        if signal == 0:
            continue
        
        # === ATR-BASED SL/TP ===
        atr = calc_atr(rates[i-ATR_PERIOD:i+1], ATR_PERIOD)
        sl_distance = atr * SL_ATR_MULT
        tp_distance = atr * TP_ATR_MULT
        
        if sl_distance == 0:
            continue
        
        risk_amount = balance * BACKTEST_RISK
        
        if signal == 1:  # BUY
            entry = current_close
            sl = entry - sl_distance
            tp = entry + tp_distance
            open_positions.append({
                'type': 'BUY', 'entry': entry,
                'sl': sl, 'tp': tp,
                'risk_amount': risk_amount,
                'sl_distance': sl_distance,
            })
        elif signal == -1:  # SELL
            entry = current_close
            sl = entry + sl_distance
            tp = entry - tp_distance
            open_positions.append({
                'type': 'SELL', 'entry': entry,
                'sl': sl, 'tp': tp,
                'risk_amount': risk_amount,
                'sl_distance': sl_distance,
            })
    
    # === RESULTS ===
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    net_profit = balance - STARTING_BALANCE
    net_return = (net_profit / STARTING_BALANCE) * 100
    profit_factor = 0
    
    total_wins_amount = sum(t['pnl'] for t in trade_log if t['pnl'] > 0)
    total_loss_amount = abs(sum(t['pnl'] for t in trade_log if t['pnl'] < 0))
    if total_loss_amount > 0:
        profit_factor = total_wins_amount / total_loss_amount
    
    avg_win = total_wins_amount / winning_trades if winning_trades > 0 else 0
    avg_loss = total_loss_amount / losing_trades if losing_trades > 0 else 0
    
    # Time range
    start_time = pytime.strftime('%Y-%m-%d', pytime.gmtime(rates[1000]['time']))
    end_time = pytime.strftime('%Y-%m-%d', pytime.gmtime(rates[-1]['time']))
    trading_days = len(set(t['day'] for t in trade_log)) if trade_log else 0
    
    print("=" * 60)
    print("   [KESSLER V1.1 BACKTEST RESULTS]")
    print("   NAS100 4H BREAKOUT + 50/200 EMA STRATEGY")
    print("=" * 60)
    print(f"  Period:              {start_time} → {end_time}")
    print(f"  Total Candles:       {len(rates) - 1000}")
    print(f"  Trading Days:        {trading_days}")
    print("-" * 60)
    print(f"  Starting Balance:    ₹{STARTING_BALANCE:>12,.0f}")
    print(f"  Final Balance:       ₹{balance:>12,.0f}")
    print(f"  Net Profit:          ₹{net_profit:>12,.0f}")
    print(f"  Net Return:          {net_return:>11.2f}%")
    print("-" * 60)
    print(f"  Total Trades:        {total_trades:>12}")
    print(f"  Winning Trades:      {winning_trades:>12}")
    print(f"  Losing Trades:       {losing_trades:>12}")
    print(f"  Win Rate:            {win_rate:>11.1f}%")
    print(f"  Profit Factor:       {profit_factor:>11.2f}")
    print("-" * 60)
    print(f"  Avg Win:             ₹{avg_win:>12,.0f}")
    print(f"  Avg Loss:            ₹{avg_loss:>12,.0f}")
    print(f"  Avg Win/Loss Ratio:  {(avg_win/avg_loss if avg_loss > 0 else 0):>11.2f}")
    print(f"  Max Drawdown:        {max_drawdown_pct*100:>11.2f}%")
    print(f"  Max Drawdown (₹):    ₹{max_drawdown:>12,.0f}")
    print(f"  Circuit Breaker Trips: {circuit_breaker_trips:>9}")
    print("=" * 60)
    
    # Phase analysis
    print("\n  [PHASE PROJECTION]")
    if total_trades > 0 and trading_days > 0:
        trades_per_day = total_trades / trading_days
        avg_pnl_per_trade = net_profit / total_trades
        
        phase1_target = STARTING_BALANCE * 0.08
        phase2_target = STARTING_BALANCE * 0.05
        
        if avg_pnl_per_trade > 0:
            trades_for_phase1 = math.ceil(phase1_target / avg_pnl_per_trade)
            trades_for_phase2 = math.ceil(phase2_target / avg_pnl_per_trade)
            days_for_phase1 = math.ceil(trades_for_phase1 / trades_per_day)
            days_for_phase2 = math.ceil(trades_for_phase2 / trades_per_day)
            
            print(f"  Phase 1 (8% = ₹{phase1_target:,.0f}):  ~{trades_for_phase1} trades / ~{days_for_phase1} trading days")
            print(f"  Phase 2 (5% = ₹{phase2_target:,.0f}):  ~{trades_for_phase2} trades / ~{days_for_phase2} trading days")
        else:
            print("  [!] Negative expectancy — strategy needs work")
    
    print("=" * 60)

# ===== MAIN =====
if __name__ == "__main__":
    rates = None
    
    if USE_MT5:
        print("[*] Attempting MT5 data fetch...")
        rates = fetch_data_mt5()
    
    if rates is None:
        print("[*] Falling back to yfinance (NQ=F futures)...")
        rates = fetch_data_yfinance()
    
    if rates is None:
        print("[!] No data available. Cannot backtest.")
        sys.exit(1)
    
    run_backtest(rates)
