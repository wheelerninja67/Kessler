"""
KESSLER V1.1 LIVE MT5 EXECUTION BRIDGE
=======================================
Directly connects the Kessler V1.1 engine to a live MetaTrader 5 terminal.
WARNING: THIS SCRIPT EXECUTES REAL MONEY TRADES.
"""

import time
import datetime
import numpy as np
import sys

try:
    import yfinance as yf
    import MetaTrader5 as mt5
except ImportError:
    print("[!] ERROR: Missing packages. Run: pip install yfinance MetaTrader5")
    sys.exit(1)

# ==========================================
# 🏆 OPTIMAL PARAMETERS HARDCODED (MNQ)
# ==========================================
SYMBOL = "NQ=F"               # Data Fetch Symbol
MT5_SYMBOL = "MNQ"            # MT5 Execution Symbol (Micro Nasdaq)
TIMEFRAME = "5m"
SL_ATR_MULT = 2.5
TP_ATR_MULT = 4.0
BREAKOUT_PERIOD = 12
EMA_FAST_P = 50
EMA_SLOW_P = 100
RISK_PCT = 0.01               # 1.0% Risk
SESSION_START = 17            # 17:00 MT5 Server Time (NY Open)
SESSION_END = 21              # 21:00 MT5 Server Time
EMA_GAP_FILTER = True
MIN_EMA_GAP = 0.002
CYCLE_INTERVAL = 300          # 5 minutes

# ==========================================

def init_mt5():
    print("[*] Initializing MetaTrader 5 Connection...")
    if not mt5.initialize():
        print(f"[!] MT5 Initialization Failed. Error: {mt5.last_error()}")
        sys.exit(1)
        
    account = mt5.account_info()
    if account is None:
        print("[!] Could not retrieve account data.")
        mt5.shutdown()
        sys.exit(1)
        
    print(f"[+] CONNECTED: {account.company} - {account.server} (ID: {account.login})")
    print(f"[+] BALANCE: ${account.balance:,.2f} | EQUITY: ${account.equity:,.2f}")
    
    # Ensure symbol is visible
    if not mt5.symbol_select(MT5_SYMBOL, True):
        print(f"[!] Failed to select {MT5_SYMBOL}. Check your broker's symbol name (e.g. MNQ, MNQZ4).")
        mt5.shutdown()
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

def execute_mt5_trade(direction, entry_price, sl_dist, tp_dist):
    """Executes the trade directly on the MT5 terminal."""
    symbol_info = mt5.symbol_info(MT5_SYMBOL)
    if symbol_info is None:
        print(f"[!] MT5 Symbol {MT5_SYMBOL} not found.")
        return False
        
    # Calculate point value and volume
    point = symbol_info.point
    
    # Standard MNQ is $2 per point. 
    # Calculate volume based on 1% risk.
    account = mt5.account_info()
    risk_amt = account.balance * RISK_PCT
    dollar_risk_per_contract = sl_dist * 2.0 
    
    volume = risk_amt / dollar_risk_per_contract
    # Round down to nearest allowed lot step
    volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step
    if volume < symbol_info.volume_min:
        volume = symbol_info.volume_min
        
    print(f"  [MT5] Calculated Volume: {volume} lots (Risk: ${risk_amt:.2f})")
    
    if direction == "LONG":
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(MT5_SYMBOL).ask
        sl = price - sl_dist
        tp = price + tp_dist
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(MT5_SYMBOL).bid
        sl = price + sl_dist
        tp = price - tp_dist
        
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": MT5_SYMBOL,
        "volume": float(volume),
        "type": order_type,
        "price": price,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": 777777,
        "comment": "Kessler V1.1",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print(f"  [MT5] Sending Order: {direction} {volume} {MT5_SYMBOL} @ {price:.2f}")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"  [!] MT5 Order Failed: {result.comment} (Code: {result.retcode})")
        return False
        
    print(f"  [+] SUCCESS! Ticket #{result.order} filled at {result.price}")
    return True

def run_live_cycle():
    now = datetime.datetime.now()
    print(f"\n{'='*65}")
    print(f"  KESSLER V1.1 MT5 BRIDGE — CYCLE [{now.strftime('%Y-%m-%d %H:%M:%S')}]")
    
    # Check if we already have open positions
    positions = mt5.positions_get(symbol=MT5_SYMBOL)
    if positions is not None and len(positions) > 0:
        print(f"  [—] Already holding {len(positions)} open positions on {MT5_SYMBOL}. Holding fire.")
        return
        
    # Check MT5 Server Time for Session Filtering
    server_time = mt5.symbol_info_tick(MT5_SYMBOL).time
    if server_time is None:
        print("  [!] Could not fetch MT5 server tick.")
        return
        
    mt5_hour = datetime.datetime.fromtimestamp(server_time).hour
    if not (SESSION_START <= mt5_hour < SESSION_END):
        print(f"  [—] MT5 Server Hour is {mt5_hour}:00. Waiting for NY Session ({SESSION_START}:00).")
        return
        
    # Fetch quantitative data
    print("  [*] Fetching data and computing institutional parameters...")
    df = yf.download(SYMBOL, period="5d", interval=TIMEFRAME, progress=False)
    if df.empty: return
    
    closes = df['Close'].values.flatten().astype(np.float64)
    highs = df['High'].values.flatten().astype(np.float64)
    lows = df['Low'].values.flatten().astype(np.float64)
    
    atr_series = fast_atr(highs, lows, closes, 14)
    ema_fast = fast_ema(closes, EMA_FAST_P)
    ema_slow = fast_ema(closes, EMA_SLOW_P)
    
    c, ef, es, atr = closes[-1], ema_fast[-1], ema_slow[-1], atr_series[-1]
    local_high = np.max(highs[-BREAKOUT_PERIOD:])
    local_low = np.min(lows[-BREAKOUT_PERIOD:])
    
    # Logic Checks
    is_uptrend = c > es and ef > es
    is_downtrend = c < es and ef < es
    
    if EMA_GAP_FILTER:
        if abs(ef - es) / es < MIN_EMA_GAP:
            print("  [—] EMA Gap too tight. Market chopping. Standby.")
            return
            
    signal = None
    if c > local_high and is_uptrend: signal = "LONG"
    elif c < local_low and is_downtrend: signal = "SHORT"
    
    if not signal:
        print("  [—] No breakout detected. Accumulation phase active.")
        return
        
    print(f"  [!!!] {signal} BREAKOUT DETECTED ON DATA FEED.")
    
    # Execute
    sl_dist = atr * SL_ATR_MULT
    tp_dist = atr * TP_ATR_MULT
    
    execute_mt5_trade(signal, c, sl_dist, tp_dist)

def main():
    init_mt5()
    print(f"\n[*] KESSLER LIVE MT5 ENGINE ARMED.")
    print(f"[*] Executing via {MT5_SYMBOL} every {CYCLE_INTERVAL} seconds.")
    
    try:
        while True:
            run_live_cycle()
            time.sleep(CYCLE_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n[*] Kessler Live Engine terminated by operator.")
        mt5.shutdown()
        sys.exit(0)

if __name__ == "__main__":
    main()
