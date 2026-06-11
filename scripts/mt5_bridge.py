import time
import json
import os
import csv
import sys
import random
import math
from datetime import datetime, timezone, timedelta
import ctypes

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] MetaTrader5 library not found or running on non-Windows OS.")
    mt5 = None

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
MAGIC_NUMBER = 777777
JOURNAL_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "trade_journal.csv")

try:
    kessler_ai = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "..", "kessler.dll"))
    kessler_ai.init_kessler_ai()
    kessler_ai.predict_trade.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    kessler_ai.predict_trade.restype = ctypes.c_uint8
    kessler_ai.evaluate_veto.argtypes = [ctypes.c_uint8, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
    kessler_ai.evaluate_veto.restype = ctypes.c_uint8
    kessler_ai.load_brain()
    print("[*] Kessler Zig Neural Network loaded successfully.")
except Exception as e:
    print(f"[!] FFI Load Error: {e}")
    kessler_ai = None

# --- V7 GLOBAL STATE ---
INITIAL_DAILY_EQUITY = 0.0
CURRENT_DATE = None
MAX_DAILY_DRAWDOWN = 0.03 # 3% Circuit Breaker

def init_journal():
    os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)
    if not os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Action", "Symbol", "Price", "Lot_Size", "Magic_Number", "Result"])

def log_trade(action, price, result_code, volume):
    with open(JOURNAL_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().isoformat(), action, SYMBOL, price, volume, MAGIC_NUMBER, result_code])

def initialize_mt5():
    if mt5 is None: return True
    if not mt5.initialize():
        print(f"[*] MT5 Initialization failed.")
        return False
    mt5.market_book_add(SYMBOL)
    return True

# --- V7 UTILITIES ---
def calculate_sma(data_list):
    if len(data_list) == 0: return 1.0
    return sum(data_list) / len(data_list)

def calculate_std_dev(data_list, mean):
    if len(data_list) <= 1: return 0.0001
    variance = sum((x - mean) ** 2 for x in data_list) / len(data_list)
    std = math.sqrt(variance)
    return std if std > 0 else 0.0001

def get_vwap(rates):
    cumulative_vol = 0
    cumulative_vol_price = 0
    for r in rates:
        typ_price = (r['high'] + r['low'] + r['close']) / 3.0
        cumulative_vol += r['tick_volume']
        cumulative_vol_price += typ_price * r['tick_volume']
    if cumulative_vol == 0: return rates[-1]['close']
    return cumulative_vol_price / cumulative_vol

def get_point_of_control(rates):
    bins = {}
    for r in rates:
        price_bin = round(r['close'], 1)
        bins[price_bin] = bins.get(price_bin, 0) + r['tick_volume']
    if not bins: return 0.0
    return max(bins, key=bins.get)

def check_daily_drawdown():
    global INITIAL_DAILY_EQUITY, CURRENT_DATE
    if mt5 is None: return False
    
    acc = mt5.account_info()
    if acc is None: return False
    
    today = datetime.utcnow().date()
    if CURRENT_DATE != today:
        CURRENT_DATE = today
        INITIAL_DAILY_EQUITY = acc.equity
        print(f"[*] V7 DRAWDOWN RESET: Initial Equity set to ${INITIAL_DAILY_EQUITY:,.2f}")
        
    current_dd = (INITIAL_DAILY_EQUITY - acc.equity) / INITIAL_DAILY_EQUITY
    if current_dd >= MAX_DAILY_DRAWDOWN:
        print(f"[!] V7 CIRCUIT BREAKER: Daily Drawdown limit ({MAX_DAILY_DRAWDOWN*100}%) hit! Halting trading.")
        return True
    return False

def check_spread_manipulation(spread):
    return spread > 50 # Veto if spread > 5 pips

def check_economic_news_embargo():
    # Architecture ready for ForexFactory API
    return False

def fetch_live_data():
    if mt5 is None: return

    last_candle_time = 0
    while True:
        if check_daily_drawdown():
            time.sleep(3600) # Sleep for an hour
            continue
            
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 100)
        if rates is not None and len(rates) >= 50:
            current_candle = rates[-1]
            
            if current_candle['time'] != last_candle_time:
                last_candle_time = current_candle['time']
                
                closes = [float(r['close']) for r in rates]
                highs = [float(r['high']) for r in rates]
                lows = [float(r['low']) for r in rates]
                opens = [float(r['open']) for r in rates]
                volumes = [float(r['tick_volume']) for r in rates]
                
                c_close = closes[-1]
                p_close = closes[-2]
                pp_close = closes[-3]
                
                sma_15 = calculate_sma(closes[-15:])
                sma_vol = calculate_sma([h - l for h, l in zip(highs[-15:], lows[-15:])])
                sma_volume = calculate_sma(volumes[-15:])
                
                norm_close = c_close / sma_15 if sma_15 > 0 else 1.0
                norm_volatility = (highs[-1] - lows[-1]) / sma_vol if sma_vol > 0 else 1.0
                velocity = c_close - p_close
                acceleration = velocity - (p_close - pp_close)
                std_dev = calculate_std_dev(closes[-15:], sma_15)
                z_score = (c_close - sma_15) / std_dev if std_dev > 0 else 0
                momentum = c_close - closes[-6]
                slope = (c_close - closes[-6]) / 5.0
                tick_volume_norm = volumes[-1] / sma_volume if sma_volume > 0 else 1.0
                shadow_upper = highs[-1] - max(opens[-1], c_close)
                shadow_lower = min(opens[-1], c_close) - lows[-1]
                
                features = [norm_close, norm_volatility, velocity, acceleration, z_score, momentum, slope, tick_volume_norm, shadow_upper, shadow_lower]
                
                vwap = get_vwap(rates[-50:])
                poc = get_point_of_control(rates[-100:])
                
                payload = {
                    "symbol": SYMBOL,
                    "close": float(c_close),
                    "features": features,
                    "atr": float(sma_vol),
                    "timestamp": int(current_candle['time'] * 1000),
                    "swing_high": max(highs[-10:]),
                    "swing_low": min(lows[-10:]),
                    "vwap": vwap,
                    "poc": poc
                }
                yield payload
                
                acc = mt5.account_info()
                if acc is not None:
                    print(f"\\n[PORTFOLIO] Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Floating PnL: ${acc.profit:,.2f}\\n")
                    
        time.sleep(5)

def enforce_position_limits(max_positions=3):
    if mt5 is None: return
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions is None or len(positions) <= max_positions:
        return
        
    positions = list(positions)
    positions.sort(key=lambda p: p.time)
    to_close = len(positions) - max_positions
    for i in range(to_close):
        pos = positions[i]
        price = mt5.symbol_info_tick(SYMBOL).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(SYMBOL).ask
        action_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": pos.volume,
            "type": action_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": "Kessler-Quant-Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        mt5.order_send(request)

def execute_trade(action, atr, volume=1.0, swing_high=0.0, swing_low=0.0):
    if mt5 is None: return
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(SYMBOL).ask if action == "BUY" else mt5.symbol_info_tick(SYMBOL).bid

    spread = mt5.symbol_info(SYMBOL).spread * mt5.symbol_info(SYMBOL).point
    min_distance = max(spread * 2.0, atr * 1.5)

    if action == "BUY":
        sl_price = min(price - min_distance, swing_low - min_distance)
        risk = price - sl_price
        tp_price = price + (risk * 2.0)
    else:
        sl_price = max(price + min_distance, swing_high + min_distance)
        risk = sl_price - price
        tp_price = price - (risk * 2.0)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": round(sl_price, 2),
        "tp": round(tp_price, 2),
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "V7-Matrix",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"[*] Order executed successfully. Ticket: {result.order}")
        log_trade(action, price, f"SUCCESS: {result.order}", volume)
    else:
        print(f"[-] ERROR: Broker Rejected Trade. Reason: {result.comment} (Code: {result.retcode})")
        log_trade(action, price, f"FAILED: {result.retcode}", volume)

def calculate_kelly_volume(confidence_percent):
    p = confidence_percent / 100.0
    q = 1.0 - p
    b = 2.0 
    kelly_fraction = p - (q / b)
    dynamic_lot = kelly_fraction * 10.0
    return round(max(0.1, min(dynamic_lot, 10.0)), 2)

def manage_trailing_stops():
    if mt5 is None: return
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions is None or len(positions) == 0:
        return
        
    for pos in positions:
        current_price = pos.price_current
        open_price = pos.price_open
        sl = pos.sl
        tp = pos.tp
        comment = pos.comment
        
        # V7 Partial Scaling at 1:1 Risk/Reward
        if sl != 0.0 and tp != 0.0:
            risk = open_price - sl if pos.type == mt5.ORDER_TYPE_BUY else sl - open_price
            if risk > 0 and "V7-Scaled" not in comment:
                profit_distance = current_price - open_price if pos.type == mt5.ORDER_TYPE_BUY else open_price - current_price
                if profit_distance >= risk: # 1:1 reached
                    close_vol = round(pos.volume / 2.0, 2)
                    if close_vol > 0.01:
                        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                        close_price = mt5.symbol_info_tick(SYMBOL).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(SYMBOL).ask
                        req = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": SYMBOL,
                            "volume": close_vol,
                            "type": close_type,
                            "position": pos.ticket,
                            "price": close_price,
                            "magic": MAGIC_NUMBER,
                            "comment": "V7-Scaled-BE",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": mt5.ORDER_FILLING_FOK,
                        }
                        mt5.order_send(req)
                        print(f"[*] V7 SCALE-OUT: 50% of Ticket {pos.ticket} secured at 1:1. Moving SL to Break-Even.")
                        
                        mod_req = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": open_price,
                            "tp": tp
                        }
                        mt5.order_send(mod_req)

def run_kessler_bridge():
    print("=========================================================")
    print("[*] KESSLER V7 <-> INSTITUTIONAL RENAISSANCE MATRIX [*]")
    print("=========================================================")
    
    if not initialize_mt5():
        sys.exit(1)
        
    init_journal()
    
    for candle_data in fetch_live_data():
        manage_trailing_stops()
        print(f"\\n[M5 STRUCTURAL MATRIX] Time: {candle_data['timestamp']} | Close: {candle_data['close']}")
        print(f"[*] POC: {candle_data['poc']} | VWAP: {candle_data['vwap']:.2f}")
        
        if kessler_ai:
            features = candle_data["features"]
            DoubleArray10 = ctypes.c_double * 10
            c_features = DoubleArray10(*features)
            
            confidence = ctypes.c_double(1.0) # GOD-MODE max confidence
            action = kessler_ai.predict_trade(c_features, ctypes.byref(confidence))
            conf_percent = 100.0 # Force maximum confidence
            
            # GOD-MODE OVERRIDE: Randomly force BUY or SELL if Zig returned HOLD (to generate massive training data points)
            if action == 0:
                action = random.choice([1, 2])
            
            # Disable confidence check for GOD-MODE scraping
            # if conf_percent < 30.0:
            #    action = 0
            
            # --- V7 MASTER VETO PROTOCOLS ---
            if action != 0:
                if check_economic_news_embargo():
                    print(f"[*] V7 VETO: High-Impact News Embargo. Action blocked.")
                    action = 0

                symbol_info = mt5.symbol_info(SYMBOL)
                if symbol_info and check_spread_manipulation(symbol_info.spread):
                    print(f"[*] V7 VETO: Broker Spread Manipulation detected ({symbol_info.spread} pts). Action blocked.")
                    action = 0

                now_utc = datetime.utcnow()
                if not (7 <= now_utc.hour <= 17):
                    print(f"[*] V7 VETO: Outside of London/NY Killzone. Action blocked.")
                    action = 0

                if action != 0:
                    h1_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 0, 20)
                    if h1_rates is not None and len(h1_rates) >= 20:
                        h1_closes = [r['close'] for r in h1_rates]
                        h1_sma_20 = sum(h1_closes) / len(h1_closes)
                        h1_trend = 1 if h1_closes[-1] > h1_sma_20 else 2
                        if action == 1 and h1_trend != 1:
                            print("[*] V7 VETO: M5 BUY blocked. H1 Trend is BEARISH.")
                            action = 0
                        elif action == 2 and h1_trend != 2:
                            print("[*] V7 VETO: M5 SELL blocked. H1 Trend is BULLISH.")
                            action = 0

                dxy_curr, dxy_prev = 0.0, 0.0
                if action != 0:
                    dxy_rates = mt5.copy_rates_from_pos("USDX", mt5.TIMEFRAME_H1, 0, 5)
                    us10y_rates = mt5.copy_rates_from_pos("US10Y", mt5.TIMEFRAME_H1, 0, 2)
                    vix_rates = mt5.copy_rates_from_pos("VIX", mt5.TIMEFRAME_H1, 0, 2)
                    
                    if dxy_rates is not None and len(dxy_rates) >= 2:
                        dxy_curr, dxy_prev = dxy_rates[-1]['close'], dxy_rates[-2]['close']
                        dxy_momentum = dxy_curr - dxy_prev
                        if action == 1 and dxy_momentum > 0.05:
                            print(f"[*] V7 VETO: BUY blocked. DXY H1 Momentum surging.")
                            action = 0
                        elif action == 2 and dxy_momentum < -0.05:
                            print(f"[*] V7 VETO: SELL blocked. DXY H1 Momentum dumping.")
                            action = 0

                    if action != 0 and us10y_rates is not None and len(us10y_rates) >= 2:
                        us10y_mom = us10y_rates[-1]['close'] - us10y_rates[-2]['close']
                        if SYMBOL == "XAUUSD" and action == 1 and us10y_mom > 0.02:
                            print("[*] V7 VETO: BUY blocked. US10Y Yields Spiking (Risk-Off Gold).")
                            action = 0
                            
                    if action != 0 and vix_rates is not None and len(vix_rates) >= 2:
                        vix_mom = vix_rates[-1]['close'] - vix_rates[-2]['close']
                        if SYMBOL in ["US500", "SPX500"] and action == 1 and vix_mom > 0.5:
                            print("[*] V7 VETO: BUY blocked. VIX Volatility Spiking (Panic Selling).")
                            action = 0

                if action == 1 and candle_data['close'] < candle_data['vwap']:
                    print("[*] V7 VETO: BUY blocked. Price is below institutional VWAP.")
                    action = 0
                elif action == 2 and candle_data['close'] > candle_data['vwap']:
                    print("[*] V7 VETO: SELL blocked. Price is above institutional VWAP.")
                    action = 0

                buy_vol, sell_vol = 0.0, 0.0
                book = mt5.market_book_get(SYMBOL)
                if book:
                    buy_vol = sum([o.volume for o in book if o.type == mt5.BOOK_TYPE_BUY])
                    sell_vol = sum([o.volume for o in book if o.type == mt5.BOOK_TYPE_SELL])
                
                if action != 0 and kessler_ai:
                    kessler_ai.evaluate_veto.argtypes = [ctypes.c_uint8, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
                    kessler_ai.evaluate_veto.restype = ctypes.c_uint8
                    veto_action = kessler_ai.evaluate_veto(action, dxy_curr, dxy_prev, buy_vol, sell_vol)
                    if veto_action == 0:
                        print(f"[*] V7 MATRIX VETO TRIGGERED: Action blocked by L2 Delta: {buy_vol - sell_vol:.1f}")
                        action = 0
            
            if action == 1:
                dynamic_vol = calculate_kelly_volume(conf_percent)
                print(f"[GOD-MODE SCRAPE] BUY Signal Logged. Features: {features}")
                log_trade_journal("BUY", 100.0, dynamic_vol)
                # GOD-MODE execution skip
                # execute_trade("BUY", candle_data['atr'], dynamic_vol, candle_data.get('swing_high', 0.0), candle_data.get('swing_low', 0.0))
            elif action == 2:
                dynamic_vol = calculate_kelly_volume(conf_percent)
                print(f"[GOD-MODE SCRAPE] SELL Signal Logged. Features: {features}")
                log_trade_journal("SELL", 100.0, dynamic_vol)
                # GOD-MODE execution skip
                # execute_trade("SELL", candle_data['atr'], dynamic_vol, candle_data.get('swing_high', 0.0), candle_data.get('swing_low', 0.0))
            else:
                print(f"[*] V7 MATRIX: Action=HOLD (Conf: {conf_percent:.2f}%)")

if __name__ == "__main__":
    run_kessler_bridge()
