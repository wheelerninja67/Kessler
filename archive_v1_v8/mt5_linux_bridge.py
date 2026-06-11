"""
KESSLER V1.1 LIVE LINUX EXECUTION SERVER
========================================
Runs natively on Linux. Hosts a lightweight HTTP server. 
The MT5 EA (running in Wine) continuously polls this server.
When a mathematical signal triggers, this server queues the command.
MT5 fetches it, executes it, and sends the ticket number back.
"""

import time
import datetime
import numpy as np
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    import yfinance as yf
except ImportError:
    print("[!] Need: pip install yfinance")
    sys.exit(1)

# ==========================================
# 🏆 OPTIMAL PARAMETERS HARDCODED
# ==========================================
SYMBOL = "NQ=F"
MT5_SYMBOL = "MNQ"
TIMEFRAME = "5m"
SL_ATR_MULT = 2.5
TP_ATR_MULT = 4.0
BREAKOUT_PERIOD = 12
EMA_FAST_P = 50
EMA_SLOW_P = 100
RISK_PCT = 0.01
SESSION_START = 17
SESSION_END = 21
EMA_GAP_FILTER = True
MIN_EMA_GAP = 0.002

CYCLE_INTERVAL = 300 # 5 minutes

# ==========================================
# THREAD-SAFE SIGNAL QUEUE
# ==========================================
signal_queue = "NONE"
queue_lock = threading.Lock()

class KesslerBridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global signal_queue
        if self.path == '/get_signal':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            
            with queue_lock:
                self.wfile.write(signal_queue.encode())
                if signal_queue != "NONE":
                    signal_queue = "NONE" # Clear after sending
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/feedback':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            print(f"\n  [MT5 EA FEEDBACK] {post_data}")
            self.send_response(200)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress standard HTTP logs so it doesn't clutter the trading terminal
        pass

def start_http_server():
    server = HTTPServer(('127.0.0.1', 5555), KesslerBridgeHandler)
    print("[*] Local Bridge Server listening on http://127.0.0.1:5555")
    server.serve_forever()

# ==========================================
# QUANTITATIVE LOGIC
# ==========================================
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

def queue_trade(direction, atr_val):
    global signal_queue
    # Fixed volume for now (1.0 lot MNQ = $2/pt). MT5 handles the lot size.
    # We send SL distance and TP distance as raw index points.
    sl_dist = atr_val * SL_ATR_MULT
    tp_dist = atr_val * TP_ATR_MULT
    
    # Payload: DIRECTION,VOLUME,SL_DIST,TP_DIST
    # e.g. "LONG,1.0,50.2,80.4"
    payload = f"{direction},1.0,{sl_dist:.2f},{tp_dist:.2f}"
    
    with queue_lock:
        signal_queue = payload
        
    print(f"  [>] Queued Signal for MT5: {payload}")

def run_live_cycle():
    now = datetime.datetime.now()
    print(f"\n{'='*65}")
    print(f"  KESSLER V1.1 LINUX SERVER — CYCLE [{now.strftime('%Y-%m-%d %H:%M:%S')}]")
    
    hour = now.hour
    if not (SESSION_START <= hour < SESSION_END):
        print(f"  [—] Outside trading session ({hour}:00). Waiting for NY Volume.")
        return
        
    print("  [*] Fetching Yahoo data...")
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
        
    print(f"  [!!!] {signal} BREAKOUT DETECTED. Dispatching to MT5.")
    queue_trade(signal, atr)

def main():
    print("\n" + "=" * 65)
    print("  KESSLER V1.1 NATIVE LINUX HTTP ENGINE")
    print("  Designed to bridge with MT5 running inside Wine.")
    print("=" * 65)
    
    # Start the local HTTP server in a background thread
    server_thread = threading.Thread(target=start_http_server, daemon=True)
    server_thread.start()
    
    print(f"\n[*] Engine Armed. Checking math every {CYCLE_INTERVAL} seconds...")
    try:
        while True:
            run_live_cycle()
            time.sleep(CYCLE_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n[*] Server terminated by operator.")
        sys.exit(0)

if __name__ == "__main__":
    main()
