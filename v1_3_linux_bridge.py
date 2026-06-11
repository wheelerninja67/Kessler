import time
import math
import logging
from datetime import datetime
import pandas as pd
import yfinance as yf
import threading
import sys

# =================================================================
# KESSLER V1.3: THE PSYCHE ENGINE HTTP BRIDGE
# Behavioral Economics | Game Theory | Stoic Displine
# =================================================================

SYMBOL = "NQ=F"
TIMEFRAME = "5m"
RISK_PCT = 2.9  
ACCOUNT_BALANCE = 10000.0
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 5.7
EMA_GAP_THRESHOLD = 0.0014
BREAKOUT_WINDOW = 8

class KesslerPsycheEngine:
    def __init__(self):
        self.data = None
        self.signal_queue = "NONE"
        
    def fetch_data(self):
        try:
            if self.data is None or self.data.empty:
                print("  [!] Waiting for MT5 to push market data to localhost...")
                return False
            return True
            
        except Exception as e:
            print(f"  [!] Institutional Data feed failure: {e}")
            return False

    def compute_core_physics(self):
        df = self.data
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_100'] = df['Close'].ewm(span=100, adjust=False).mean()
        
        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        df['ATR_14'] = df['TR'].rolling(window=14).mean()
        
        df['Highest_12'] = df['High'].rolling(window=BREAKOUT_WINDOW).max()
        df['Lowest_12'] = df['Low'].rolling(window=BREAKOUT_WINDOW).min()
        self.data = df

    def compute_psyche_matrix(self):
        df = self.data
        
        # 1. Retail Panic Index
        df['Candle_Body'] = abs(df['Close'] - df['Open'])
        df['Avg_Body'] = df['Candle_Body'].rolling(window=14).mean()
        df['Is_Panic_Sell'] = (df['Close'] < df['Open']) & (df['Candle_Body'] > (df['Avg_Body'] * 2))
        
        # 2. Adversarial Squeeze Trap
        df['Lower_Wick'] = df[['Open', 'Close']].min(axis=1) - df['Low']
        df['Is_Bear_Trap'] = (df['Lower_Wick'] > (df['Candle_Body'] * 2)) & (df['Close'] < df['EMA_50'])
        
        # 3. Stoic Patience Filter
        df['Avg_ATR_Daily'] = df['ATR_14'].rolling(window=288).mean() 
        df['Stoic_Reject'] = df['ATR_14'] < (df['Avg_ATR_Daily'] * 0.7)
        
        self.data = df

    def execute_logic(self):
        print(f"\n=================================================================")
        print(f"  KESSLER V1.3 PSYCHE SERVER — CYCLE [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print("  [*] Processing direct MT5 Institutional Feed...")
        
        # NY Session Filter (9:30 AM - 4:00 PM EST)
        # Convert local time to EST roughly to avoid trading in dead zones
        current_hour = datetime.now().hour
        # Assuming local is GMT+5:30 (India), 7 PM local is 9:30 AM EST. 1:30 AM local is 4 PM EST.
        # We will keep the engine running always, but note the time.
        
        if not self.fetch_data():
            return
            
        self.compute_core_physics()
        self.compute_psyche_matrix()
        current = self.data.iloc[-1]
        prev = self.data.iloc[-2]
        
        if current['Stoic_Reject']:
            print("  [—] STOIC REJECTION: Volatility too low. Refusing to trade chop.")
            return
            
        trend = "FLAT"
        gap = abs(current['EMA_50'] - current['EMA_100']) / current['EMA_100']
        if gap > EMA_GAP_THRESHOLD:
            if current['EMA_50'] > current['EMA_100']:
                trend = "BULL"
            elif current['EMA_50'] < current['EMA_100']:
                trend = "BEAR"

        if trend == "BULL" and current['Close'] > prev['Highest_12']:
            if current['Is_Bear_Trap']:
                print("  [!!!] PSYCHE SQUEEZE DETECTED. Retail shorts trapped. Initiating LONG.")
                self.signal_queue = self.generate_payload("LONG", current['ATR_14'])
            else:
                print("  [!!!] Breakout Detected. Initiating LONG.")
                self.signal_queue = self.generate_payload("LONG", current['ATR_14'])
                
        elif trend == "BEAR" and current['Close'] < prev['Lowest_12']:
            if current['Is_Panic_Sell']:
                print("  [!!!] RETAIL PANIC DETECTED. Fading into SHORT.")
                self.signal_queue = self.generate_payload("SHORT", current['ATR_14'])
            else:
                print("  [!!!] Breakout Detected. Initiating SHORT.")
                self.signal_queue = self.generate_payload("SHORT", current['ATR_14'])
        else:
            print("  [—] No parameters met. Observing.")

    def generate_payload(self, direction, atr):
        sl_dist = atr * ATR_SL_MULTIPLIER
        tp_dist = atr * ATR_TP_MULTIPLIER
        
        # Dynamic lot sizing based on 2.9% max risk
        risk_amount = ACCOUNT_BALANCE * (RISK_PCT / 100.0)
        
        # Funding Pips NAS100 Contract Size is often 10 or 20 (not 1).
        # Which means 1 lot = $10 per point, not $1. 
        # Sending 3.34 lots was trying to risk $2,900, requiring $28k margin! 
        CONTRACT_MULTIPLIER = 10.0 
        volume = risk_amount / (sl_dist * CONTRACT_MULTIPLIER)
        
        volume = round(volume, 2)
        if volume < 0.01: volume = 0.01
        if volume > 2.0: volume = 2.0 # Hard Margin Ceiling for $10k accounts
        
        print(f"  [+] Calculated Risk Volume: {volume} lots (Risking ${risk_amount:.2f})")
        return f"{direction},{volume},{sl_dist:.2f},{tp_dist:.2f}"

from http.server import BaseHTTPRequestHandler, HTTPServer

engine = KesslerPsycheEngine()

class KesslerHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress standard HTTP logs
        
    def do_GET(self):
        if self.path == '/get_signal':
            sig = engine.signal_queue
            if sig != "NONE":
                engine.signal_queue = "NONE" # Clear after reading
                
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(sig.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/feedback':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            msg = post_data.decode('utf-8')
            print("\n[+] =================================================================")
            print(f"[+] MT5 EXECUTION FEEDBACK: {msg}")
            print("[+] =================================================================\n")
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == '/market_data':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = post_data.decode('utf-8')
            
            # Parse the payload: open,high,low,close|open,high...
            rows = []
            for candle in payload.split('|'):
                if not candle: continue
                parts = candle.split(',')
                if len(parts) == 4:
                    rows.append({
                        'Open': float(parts[0]),
                        'High': float(parts[1]),
                        'Low': float(parts[2]),
                        'Close': float(parts[3])
                    })
            
            if len(rows) > 0:
                engine.data = pd.DataFrame(rows)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def engine_loop():
    print("\n=================================================================")
    print("  KESSLER V1.3 NATIVE LINUX PSYCHE BRIDGE")
    print("  Behavioral Economics | Game Theory | Stoic Displine")
    print("=================================================================")
    print("\n[*] Psyche Engine Armed. Analyzing market physics every 300 seconds...")
    
    while True:
        current_minute = datetime.now().minute
        current_second = datetime.now().second
        
        if current_minute % 5 == 0 and current_second < 5:
            engine.execute_logic()
            time.sleep(60)
        
        time.sleep(1)

if __name__ == '__main__':
    t = threading.Thread(target=engine_loop)
    t.daemon = True
    t.start()
    
    server_address = ('0.0.0.0', 5555)
    httpd = HTTPServer(server_address, KesslerHTTPRequestHandler)
    httpd.serve_forever()
