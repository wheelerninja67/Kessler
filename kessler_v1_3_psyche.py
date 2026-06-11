import time
import math
import logging
from datetime import datetime
import pandas as pd
import yfinance as yf

# =================================================================
# KESSLER V1.3: THE PSYCHE ENGINE
# Incorporating Behavioral Economics, Game Theory, & Stoicism
# =================================================================

# --- CORE SETTINGS (Inherited from V1.1) ---
SYMBOL = "NQ=F"
TIMEFRAME = "5m"
RISK_PCT = 2.0  # Upgraded to 2.0% for the August 11 scale
ACCOUNT_BALANCE = 10000.0
ATR_SL_MULTIPLIER = 2.5
ATR_TP_MULTIPLIER = 4.0
EMA_GAP_THRESHOLD = 0.002
BREAKOUT_WINDOW = 12

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class KesslerPsycheEngine:
    def __init__(self):
        self.data = None
        
    def fetch_data(self):
        try:
            ticker = yf.Ticker(SYMBOL)
            df = ticker.history(period="5d", interval=TIMEFRAME)
            if df.empty:
                return False
            self.data = df
            return True
        except Exception as e:
            logging.error(f"Data feed failure: {e}")
            return False

    def compute_core_physics(self):
        """Calculates the standard V1.1 Institutional logic."""
        df = self.data
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_100'] = df['Close'].ewm(span=100, adjust=False).mean()
        
        # True Range and ATR
        df['H-L'] = df['High'] - df['Low']
        df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
        df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        df['ATR_14'] = df['TR'].rolling(window=14).mean()
        
        df['Highest_12'] = df['High'].rolling(window=BREAKOUT_WINDOW).max()
        df['Lowest_12'] = df['Low'].rolling(window=BREAKOUT_WINDOW).min()
        
        self.data = df

    def compute_psyche_matrix(self):
        """
        Incorporates themes from the 735 Book Library:
        1. Behavioral Economics (Kahneman/Thaler): Retail Panic Detection
        2. Game Theory (Axelrod): Adversarial Squeeze Traps
        3. Stoicism (Aurelius): The Patience Filter (Chop rejection)
        """
        df = self.data
        
        # 1. RETAIL PANIC INDEX (Behavioral Economics)
        # Retail traders panic sell at bottoms. If we see massive red candles with expanding volume,
        # we look to fade the panic.
        df['Candle_Body'] = abs(df['Close'] - df['Open'])
        df['Avg_Body'] = df['Candle_Body'].rolling(window=14).mean()
        df['Is_Panic_Sell'] = (df['Close'] < df['Open']) & (df['Candle_Body'] > (df['Avg_Body'] * 2))
        
        # 2. ADVERSARIAL SQUEEZE TRAP (Game Theory)
        # If price makes a sudden sharp wick downward that gets instantly bought up,
        # institutions are trapping retail shorts.
        df['Lower_Wick'] = df[['Open', 'Close']].min(axis=1) - df['Low']
        df['Is_Bear_Trap'] = (df['Lower_Wick'] > (df['Candle_Body'] * 2)) & (df['Close'] < df['EMA_50'])
        
        # 3. STOIC PATIENCE FILTER (Philosophy)
        # Marcus Aurelius: "You have power over your mind, not outside events."
        # If the market ATR drops below 60% of its daily average, the market is chopping. Do not trade.
        df['Avg_ATR_Daily'] = df['ATR_14'].rolling(window=288).mean() # Approx 1 day of 5m candles
        df['Stoic_Reject'] = df['ATR_14'] < (df['Avg_ATR_Daily'] * 0.6)
        
        self.data = df

    def execute_logic(self):
        if not self.fetch_data():
            return "NO_DATA"
            
        self.compute_core_physics()
        self.compute_psyche_matrix()
        
        current = self.data.iloc[-1]
        
        # The Stoic Filter: If market is dead, do not force a trade.
        if current['Stoic_Reject']:
            return "STOIC_REJECTION: Market lacks volatility."
            
        # Core V1.1 Trend Check
        trend = "FLAT"
        gap = abs(current['EMA_50'] - current['EMA_100']) / current['EMA_100']
        if gap > EMA_GAP_THRESHOLD:
            if current['EMA_50'] > current['EMA_100']:
                trend = "BULL"
            elif current['EMA_50'] < current['EMA_100']:
                trend = "BEAR"

        # The V1.3 Psyche Execution
        if trend == "BULL" and current['Close'] > current['Highest_12'].shift(1):
            if current['Is_Bear_Trap']:
                logging.info("[V1.3] PSYCHE SQUEEZE DETECTED. Retail shorts trapped. Initiating LONG.")
                return self.generate_payload("LONG", current['ATR_14'])
            else:
                logging.info("[V1.3] Standard V1.1 Breakout. Initiating LONG.")
                return self.generate_payload("LONG", current['ATR_14'])
                
        elif trend == "BEAR" and current['Close'] < current['Lowest_12'].shift(1):
            if current['Is_Panic_Sell']:
                logging.info("[V1.3] RETAIL PANIC DETECTED. Accelerating SHORT.")
                return self.generate_payload("SHORT", current['ATR_14'])
            else:
                logging.info("[V1.3] Standard V1.1 Breakout. Initiating SHORT.")
                return self.generate_payload("SHORT", current['ATR_14'])

        return "NONE"

    def generate_payload(self, direction, atr):
        sl_dist = atr * ATR_SL_MULTIPLIER
        tp_dist = atr * ATR_TP_MULTIPLIER
        return f"{direction},1.0,{sl_dist:.2f},{tp_dist:.2f}"

if __name__ == "__main__":
    print("=================================================================")
    print("  KESSLER V1.3: THE PSYCHE ENGINE")
    print("  Behavioral Economics | Game Theory | Stoic Displine")
    print("=================================================================")
    
    engine = KesslerPsycheEngine()
    signal = engine.execute_logic()
    print(f"[*] Engine Output: {signal}")
