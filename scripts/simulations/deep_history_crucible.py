import pandas as pd
import numpy as np

class DeepHistoryCrucible:
    def __init__(self, initial_balance=100000.0, risk_pct=0.005):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0
        self.risk_pct = risk_pct
        self.trades = 0
        self.wins = 0
        
    def execute(self):
        print(f"[*] Igniting Deep History Crucible (20-Year Macro Execution)...")
        
        try:
            # yfinance creates multi-index headers. Row 0 is Price type, Row 1 is Ticker. Index is col 0.
            gold = pd.read_csv("data/macro/GOLD_20yr.csv", header=[0, 1], index_col=0, parse_dates=True)
            usdx = pd.read_csv("data/macro/USDX_20yr.csv", header=[0, 1], index_col=0, parse_dates=True)
            us10y = pd.read_csv("data/macro/US10Y_20yr.csv", header=[0, 1], index_col=0, parse_dates=True)
            
            # Align data by date
            df = pd.DataFrame({
                "Gold_Close": gold["Close"].iloc[:, 0],
                "USDX_Close": usdx["Close"].iloc[:, 0],
                "US10Y_Close": us10y["Close"].iloc[:, 0]
            }).dropna()
            
            print(f"[*] Aligned 20-Year Institutional Matrix: {len(df)} trading days.")
            
            # Calculate metrics
            # 1. 50-day rolling correlation spread (Inverse)
            spread = np.log(df["Gold_Close"]) + np.log(df["USDX_Close"])
            mean_spread = spread.rolling(window=50).mean()
            std_spread = spread.rolling(window=50).std()
            df["Z_Score"] = (spread - mean_spread) / std_spread
            
            # 2. US10Y Velocity (5-day percentage change)
            df["US10Y_Velocity"] = df["US10Y_Close"].pct_change(periods=5)
            
            # 3. Future 5-Day Return for Gold (to measure outcome of trade)
            df["Gold_Future_Ret"] = df["Gold_Close"].shift(-5) / df["Gold_Close"] - 1.0
            
            df = df.dropna()
            
            for index, row in df.iterrows():
                z = row["Z_Score"]
                yield_vel = row["US10Y_Velocity"]
                future_ret = row["Gold_Future_Ret"]
                
                # Check for Black Swan Anomalies (2008 Crash, 2020 COVID)
                if index.year == 2008 and index.month == 9 and index.day == 15:
                    print("[!] BLACK SWAN EVENT: Lehman Brothers Collapse (Sep 15, 2008)")
                if index.year == 2020 and index.month == 3 and index.day == 9:
                    print("[!] BLACK SWAN EVENT: COVID-19 Flash Crash (Mar 9, 2020)")
                
                # Execution Logic (Kessler V9 Macro)
                trade_taken = False
                pnl_pct = 0.0
                
                # BUY CONDITION
                if z < -2.0 and yield_vel < -0.05:
                    trade_taken = True
                    pnl_pct = future_ret  # Long Gold
                    
                # SELL CONDITION
                elif z > 2.0 and yield_vel > 0.05:
                    trade_taken = True
                    pnl_pct = -future_ret # Short Gold
                    
                if trade_taken:
                    self.trades += 1
                    # 1:2.5 Risk Reward simulation -> PnL normalized to risk.
                    # Since we hold for 5 days, if it goes in our favor, we make 2.5x our risk.
                    if pnl_pct > 0:
                        self.wins += 1
                        self.balance += (self.balance * self.risk_pct * 2.5)
                    else:
                        self.balance -= (self.balance * self.risk_pct)
                        
                    if self.balance > self.peak_balance:
                        self.peak_balance = self.balance
                    
                    dd = (self.peak_balance - self.balance) / self.peak_balance * 100
                    if dd > self.max_drawdown:
                        self.max_drawdown = dd
                        
            print("\\n=========================================================")
            print("  [KESSLER V9] THE 20-YEAR DEEP HISTORY CRUCIBLE           ")
            print("=========================================================")
            print(f"[*] Duration:      2004 - 2024 (20 Years)")
            print(f"[*] Initial Bal:   ${self.initial_balance:,.2f}")
            print(f"[*] Final Bal:     ${self.balance:,.2f}")
            profit = self.balance - self.initial_balance
            print(f"[*] Net Profit:    ${profit:,.2f} ({(profit/self.initial_balance)*100:.2f}%)")
            print(f"[*] Max Drawdown:  {self.max_drawdown:.2f}%")
            print(f"---------------------------------------------------------")
            print(f"[*] Total Trades:  {self.trades}")
            if self.trades > 0:
                print(f"[*] Win Rate:      {(self.wins/self.trades)*100:.2f}%")
            print("=========================================================")
            
        except Exception as e:
            print(f"[!] Crucible Execution Error: {e}")

if __name__ == "__main__":
    crucible = DeepHistoryCrucible()
    crucible.execute()
