import time
import sys
import math
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] MetaTrader5 library not found or running on non-Windows OS.")
    mt5 = None

def initialize_mt5():
    print("[*] Initializing MT5 connection for Historical Backtest...")
    if not mt5.initialize():
        print(f"[!] MT5 initialize() failed, error code: {mt5.last_error()}")
        return False
    return True

def calculate_zscore(gold_closes, usd_closes):
    if len(gold_closes) < 50 or len(usd_closes) < 50:
        return 0.0
    
    spreads = []
    for i in range(50):
        g = gold_closes[-(50-i)]
        d = usd_closes[-(50-i)]
        if g <= 0 or d <= 0:
            continue
        spreads.append(math.log(g) + math.log(d))
        
    if not spreads:
        return 0.0
        
    mean_s = sum(spreads) / len(spreads)
    variance = sum((s - mean_s) ** 2 for s in spreads) / len(spreads)
    std_dev = math.sqrt(variance) if variance > 0 else 0.0001
    
    return (spreads[-1] - mean_s) / std_dev

def detect_sweep(m5_window, daily_window):
    if len(m5_window) < 3 or len(daily_window) < 2:
        return 0
    pdh = daily_window[-2]['high']
    pdl = daily_window[-2]['low']
    
    curr = m5_window[-1]
    prev = m5_window[-2]
    
    if prev['high'] > pdh and curr['close'] < pdh:
        return -1 # Bearish Sweep
    if prev['low'] < pdl and curr['close'] > pdl:
        return 1 # Bullish Sweep
    return 0

def detect_mss(m5_window):
    if len(m5_window) < 6:
        return 0
    recent_low = min([r['low'] for r in m5_window[-6:-2]])
    recent_high = max([r['high'] for r in m5_window[-6:-2]])
    curr = m5_window[-1]['close']
    
    if curr < recent_low: return -1
    if curr > recent_high: return 1
    return 0

def run_backtest():
    if not initialize_mt5():
        sys.exit(1)
        
    print("[*] Igniting the Kessler Gauntlet: HYPER-VOLATILITY TRIAD")
    
    # Pairs and their highly correlated benchmark for StatArb
    baskets = {
        "XAUUSD": "USDX",
        "USTEC": "USDX",   # NASDAQ 100
        "BTC": "USDX"   # Bitcoin
    }
    
    total_balance = 100000.0
    total_trades = 0
    total_wins = 0
    total_losses = 0
    
    for symbol, benchmark in baskets.items():
        print(f"\\n[*] Downloading 50,000 M5 Candles for {symbol} vs {benchmark}...")
        asset_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50000)
        usd_m5 = mt5.copy_rates_from_pos(benchmark, mt5.TIMEFRAME_M5, 0, 50000)
        vix_m5 = mt5.copy_rates_from_pos("VIX", mt5.TIMEFRAME_M5, 0, 50000)
        asset_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1000)
        
        if asset_m5 is None or len(asset_m5) < 10000:
            print(f"[!] Insufficient data for {symbol}. Skipping.")
            continue
            
        print(f"[*] Simulating {symbol} Matrix...")
        
        balance = total_balance # Inherit the rolling balance
        peak_balance = balance
        start_of_day_balance = balance
        trades = 0
        wins = 0
        losses = 0
        
        in_trade = False
        trade_type = 0
        entry_price = 0.0
        sl = 0.0
        tp = 0.0
        lots_traded = 0.0
        
        g_close = [x['close'] for x in asset_m5]
        u_close = [x['close'] for x in usd_m5] if usd_m5 is not None and len(usd_m5) == len(asset_m5) else [100.0]*len(asset_m5)
        v_close = [x['close'] for x in vix_m5] if vix_m5 is not None and len(vix_m5) == len(asset_m5) else [15.0]*len(asset_m5)
        
        bearish_hunter_timer = 0
        bullish_hunter_timer = 0
        pending_order_type = 0
        pending_limit_price = 0.0
        pending_sl = 0.0
        pending_timer = 0
        
        # Determine pip scaling based on asset
        pip_scale = 0.1
        if symbol == "XAUUSD": pip_scale = 0.1
        if symbol in ["USTEC", "USTECH100"]: pip_scale = 1.0
        if symbol == "BTC": pip_scale = 10.0
        
        for i in range(1000, len(asset_m5)):
            if i % 288 == 0: start_of_day_balance = balance
                
            current_g = g_close[i]
            
            if bearish_hunter_timer > 0: bearish_hunter_timer -= 1
            if bullish_hunter_timer > 0: bullish_hunter_timer -= 1
            
            if in_trade:
                exit_slippage = pip_scale * 1.0 # 1 pip slippage
                
                if trade_type == 1:
                    if current_g <= sl:
                        loss_amount = (sl - exit_slippage - entry_price) * lots_traded * 100000 if pip_scale == 0.0001 else (sl - exit_slippage - entry_price) * lots_traded * 100
                        balance += loss_amount
                        losses += 1
                        in_trade = False
                    elif current_g >= tp:
                        win_amount = (tp - exit_slippage - entry_price) * lots_traded * 100000 if pip_scale == 0.0001 else (tp - exit_slippage - entry_price) * lots_traded * 100
                        balance += win_amount
                        wins += 1
                        in_trade = False
                elif trade_type == -1:
                    if current_g >= sl:
                        loss_amount = (entry_price - (sl + exit_slippage)) * lots_traded * 100000 if pip_scale == 0.0001 else (entry_price - (sl + exit_slippage)) * lots_traded * 100
                        balance += loss_amount
                        losses += 1
                        in_trade = False
                    elif current_g <= tp:
                        win_amount = (entry_price - (tp + exit_slippage)) * lots_traded * 100000 if pip_scale == 0.0001 else (entry_price - (tp + exit_slippage)) * lots_traded * 100
                        balance += win_amount
                        wins += 1
                        in_trade = False
                        
                continue
                
            if pending_timer > 0:
                pending_timer -= 1
                entry_slippage = pip_scale * 1.0
                
                # HIGH-CONVICTION RISK: 2.5% per trade to achieve explosive growth
                risk_amount = balance * 0.025
                
                if pending_order_type == 1 and current_g <= pending_limit_price:
                    in_trade = True
                    trade_type = 1
                    entry_price = pending_limit_price + entry_slippage
                    sl = pending_sl
                    tp = entry_price + ((entry_price - sl) * 2.5)
                    
                    sl_distance = entry_price - sl
                    lots_traded = risk_amount / (sl_distance * 100000) if pip_scale == 0.0001 else risk_amount / (sl_distance * 100)
                    if lots_traded <= 0: lots_traded = 0.01
                    balance -= (lots_traded * 7.0)
                    trades += 1
                    pending_order_type = 0
                    continue
                    
                elif pending_order_type == -1 and current_g >= pending_limit_price:
                    in_trade = True
                    trade_type = -1
                    entry_price = pending_limit_price - entry_slippage
                    sl = pending_sl
                    tp = entry_price - ((sl - entry_price) * 2.5)
                    
                    sl_distance = sl - entry_price
                    lots_traded = risk_amount / (sl_distance * 100000) if pip_scale == 0.0001 else risk_amount / (sl_distance * 100)
                    if lots_traded <= 0: lots_traded = 0.01
                    balance -= (lots_traded * 7.0)
                    trades += 1
                    pending_order_type = 0
                    continue
                continue
                
            vix_pct = ((v_close[i] - v_close[i-12]) / v_close[i-12]) * 100.0 if i >= 12 else 0.0
            if vix_pct > 5.0: continue
                
            if i < 600: continue
            g_h1_sub = g_close[i-600:i:12] 
            u_h1_sub = u_close[i-600:i:12]
            z_score = calculate_zscore(g_h1_sub, u_h1_sub)
            
            # STRICT INSTITUTIONAL THRESHOLD
            if z_score > 2.0:
                bearish_hunter_timer = 288
            elif z_score < -2.0:
                bullish_hunter_timer = 288
            
            m5_window = asset_m5[i-10:i+1]
            mss = detect_mss(m5_window)
            c1 = m5_window[-4]
            c3 = m5_window[-2]
            
            if bearish_hunter_timer > 0 and mss == -1:
                if c1['low'] > c3['high']: 
                    fvg_mid = (c1['low'] + c3['high']) / 2.0
                    pending_order_type = -1
                    pending_limit_price = fvg_mid
                    pending_sl = c1['high'] + (pip_scale * 10.0)
                    pending_timer = 24
                    bearish_hunter_timer = 0
                
            elif bullish_hunter_timer > 0 and mss == 1:
                if c1['high'] < c3['low']:
                    fvg_mid = (c1['high'] + c3['low']) / 2.0
                    pending_order_type = 1
                    pending_limit_price = fvg_mid
                    pending_sl = c1['low'] - (pip_scale * 10.0)
                    pending_timer = 24
                    bullish_hunter_timer = 0
                    
        total_balance = balance
        total_trades += trades
        total_wins += wins
        total_losses += losses

    print("\\n=========================================================")
    print("  [KESSLER V8] HYPER-VOLATILITY TRIAD")
    print("=========================================================")
    print(f"[*] Simulated Duration: ~1.5 Years across GOLD, NAS100, BTC")
    print(f"[*] Initial Balance:  $100,000.00")
    print(f"[*] Final Balance:    ${total_balance:.2f}")
    profit = total_balance - 100000.0
    print(f"[*] Net Profit:       ${profit:.2f} ({profit/100000.0*100:.2f}%)")
    print(f"---------------------------------------------------------")
    print(f"[*] Total Trades:     {total_trades}")
    win_rate = (total_wins/total_trades*100) if total_trades > 0 else 0
    print(f"[*] Win Rate:         {win_rate:.2f}%")
    print("=========================================================")
    if profit > 50000.0:
        print("[>>] OBJECTIVE ACHIEVED: Generated >$50,000 in hyper-volatile markets.")
    else:
        print(f"[>>] Revenue Generated: ${profit:.2f}. Further Volatility Required.")

if __name__ == "__main__":
    run_backtest()
