import time
import math
import os
import ctypes
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] MetaTrader5 library not found.")
    mt5 = None

SYMBOL = "XAUUSD"

def calculate_sma(data_list):
    if len(data_list) == 0: return 1.0
    return sum(data_list) / len(data_list)

def calculate_std_dev(data_list, mean):
    if len(data_list) <= 1: return 0.0001
    variance = sum((x - mean) ** 2 for x in data_list) / len(data_list)
    std = math.sqrt(variance)
    return std if std > 0 else 0.0001

def run_backtest():
    print("=========================================================")
    print("[*] KESSLER V7 <-> INSTITUTIONAL RENAISSANCE BACKTESTER [*]")
    print("=========================================================")
    
    if mt5 is None or not mt5.initialize():
        print("[!] MT5 Init failed.")
        return

    # Load Zig DLL
    try:
        kessler_ai = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "..", "kessler.dll"))
        kessler_ai.init_kessler_ai()
        kessler_ai.predict_trade.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        kessler_ai.predict_trade.restype = ctypes.c_uint8
        kessler_ai.load_brain.argtypes = []
        kessler_ai.load_brain.restype = None
        kessler_ai.load_brain()
    except Exception as e:
        print(f"[!] DLL Error: {e}")
        return

    print(f"[*] Downloading Historical Data for {SYMBOL}...")
    # Get last 5,000 M15 candles (roughly 2-3 months of data)
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M15, 0, 5000)
    
    if rates is None or len(rates) < 100:
        print("[!] Failed to get historical data.")
        return

    print(f"[*] Received {len(rates)} candles. Commencing Simulation...")
    
    total_trades = 0
    wins = 0
    losses = 0
    breakevens = 0
    balance = 100000.0
    peak_balance = 100000.0
    max_drawdown = 0.0

    # We start from index 20 to have enough lookback data
    for i in range(20, len(rates) - 5): # -5 to peek into future for result
        lookback = rates[i-20:i]
        current_candle = lookback[-1]
        
        closes = [float(r['close']) for r in lookback]
        highs = [float(r['high']) for r in lookback]
        lows = [float(r['low']) for r in lookback]
        opens = [float(r['open']) for r in lookback]
        volumes = [float(r['tick_volume']) for r in lookback]
        
        c_close = closes[-1]
        p_close = closes[-2]
        pp_close = closes[-3]
        
        sma_15 = calculate_sma(closes[-15:])
        sma_vol = calculate_sma([h - l for h, l in zip(highs[-15:], lows[-15:])])
        sma_volume = calculate_sma(volumes[-15:])
        
        norm_close = c_close / sma_15 if sma_15 > 0 else 1.0
        norm_volatility = (highs[-1] - lows[-1]) / sma_vol if sma_vol > 0 else 1.0
        velocity = c_close - p_close
        prev_velocity = p_close - pp_close
        acceleration = velocity - prev_velocity
        
        std_dev = calculate_std_dev(closes[-15:], sma_15)
        z_score = (c_close - sma_15) / std_dev
        
        momentum = c_close - closes[-6]
        slope = (c_close - closes[-6]) / 5.0
        
        tick_volume_norm = volumes[-1] / sma_volume if sma_volume > 0 else 1.0
        shadow_upper = highs[-1] - max(opens[-1], c_close)
        shadow_lower = min(opens[-1], c_close) - lows[-1]
        
        features = [
            norm_close, norm_volatility, velocity, acceleration, z_score,
            momentum, slope, tick_volume_norm, shadow_upper, shadow_lower
        ]
        
        DoubleArray10 = ctypes.c_double * 10
        c_features = DoubleArray10(*features)
        
        confidence = ctypes.c_double(0.0)
        action = kessler_ai.predict_trade(c_features, ctypes.byref(confidence))
        conf_percent = confidence.value * 100.0
        
        if conf_percent >= 80.0:
            if action == 1 or action == 2:
                total_trades += 1
                
                # Check future candles to simulate TP/SL hit
                # We look 6 candles ahead (30 minutes)
                future_rates = rates[i+1:i+7]
                
                # Structural V7 Stop Loss (10-candle lookback)
                swing_low = min(lows[-10:])
                swing_high = max(highs[-10:])
                
                trade_closed = False
                
                for f_candle in future_rates:
                    if trade_closed: break
                    
                    f_high = float(f_candle['high'])
                    f_low = float(f_candle['low'])
                    
                    if action == 1: # BUY
                        risk = c_close - swing_low
                        tp = c_close + (risk * 2.0)
                        be_point = c_close + risk # 1:1 Scale out
                        
                        if f_low <= swing_low:
                            losses += 1
                            balance -= (balance * 0.02) # 2% risk hit
                            trade_closed = True
                        elif f_high >= tp:
                            wins += 1
                            balance += (balance * 0.04) # 4% profit
                            trade_closed = True
                        elif f_high >= be_point:
                            breakevens += 1
                            balance += (balance * 0.01) # 1% profit from half position
                            trade_closed = True
                            
                    elif action == 2: # SELL
                        risk = swing_high - c_close
                        tp = c_close - (risk * 2.0)
                        be_point = c_close - risk
                        
                        if f_high >= swing_high:
                            losses += 1
                            balance -= (balance * 0.02)
                            trade_closed = True
                        elif f_low <= tp:
                            wins += 1
                            balance += (balance * 0.04)
                            trade_closed = True
                        elif f_low <= be_point:
                            breakevens += 1
                            balance += (balance * 0.01)
                            trade_closed = True
                            
                # Update Drawdown
                if balance > peak_balance:
                    peak_balance = balance
                
                dd = (peak_balance - balance) / peak_balance
                if dd > max_drawdown:
                    max_drawdown = dd

    print("=========================================================")
    print(f"[*] BACKTEST COMPLETE ({len(rates)} Candles Processed)")
    print(f"[*] Total Trades Taken (>90% Conf): {total_trades}")
    if total_trades > 0:
        win_rate = (wins / total_trades) * 100
        print(f"[*] Full Wins (1:2): {wins}")
        print(f"[*] Break-Evens (1:1): {breakevens}")
        print(f"[*] Full Losses: {losses}")
        print(f"[*] Initial Balance: $100,000.00")
        print(f"[*] Final Balance: ${balance:,.2f}")
        print(f"[*] Historical Win Rate: {win_rate:.2f}%")
        print(f"[*] Maximum Drawdown: {max_drawdown*100:.2f}%")
    print("=========================================================")

if __name__ == "__main__":
    run_backtest()
