import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def download_data():
    print("[*] QUANT ENGINE: Downloading 60 days of NAS100 5-minute institutional data...")
    df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('US/Eastern')
    return df

def backtest_wyckoff(df, period=50, rr=2.0):
    wins = 0
    losses = 0
    
    in_trade = False
    entry = 0.0
    sl = 0.0
    tp = 0.0
    dir = 0
    
    for i in range(period, len(df)):
        window = df.iloc[i-period:i]
        current_c = df.iloc[i]
        
        # Only trade the NY Session volume (9:30 AM - 4:00 PM EST)
        hour = current_c.name.hour
        minute = current_c.name.minute
        time_val = hour * 60 + minute
        
        if time_val < 570 or time_val > 960:
            if in_trade:
                # Institutional close at end of day
                if dir == 1:
                    if current_c['Close'] > entry: wins +=1
                    else: losses += 1
                else:
                    if current_c['Close'] < entry: wins +=1
                    else: losses += 1
                in_trade = False
            continue
            
        if not in_trade:
            # Locate the structural extremes and their exact volume
            local_low = window['Low'].min()
            low_idx = window['Low'].argmin()
            low_vol = window.iloc[low_idx]['Volume']
            
            local_high = window['High'].max()
            high_idx = window['High'].argmax()
            high_vol = window.iloc[high_idx]['Volume']
            
            # Wyckoff Spring (Accumulation)
            # Price breaks low, but volume is exhausted (lower than the structural low)
            if current_c['Low'] < local_low and current_c['Volume'] < low_vol:
                in_trade = True
                entry = current_c['Close']
                sl = current_c['Low'] - 10.0 # Stop loss tightly below the spring wick
                tp = entry + ((entry - sl) * rr) # Target RR
                dir = 1
                
            # Wyckoff Upthrust (Distribution)
            # Price breaks high, but volume is exhausted
            elif current_c['High'] > local_high and current_c['Volume'] < high_vol:
                in_trade = True
                entry = current_c['Close']
                sl = current_c['High'] + 10.0
                tp = entry - ((sl - entry) * rr)
                dir = -1
        else:
            if dir == 1:
                if current_c['Low'] <= sl:
                    losses += 1
                    in_trade = False
                elif current_c['High'] >= tp:
                    wins += 1
                    in_trade = False
            else:
                if current_c['High'] >= sl:
                    losses += 1
                    in_trade = False
                elif current_c['Low'] <= tp:
                    wins += 1
                    in_trade = False
                    
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    return total, win_rate

if __name__ == "__main__":
    df = download_data()
    print("\n=========================================================")
    print(" [KESSLER MD] WYCKOFF VOLUME DIVERGENCE STRESS TEST ")
    print("=========================================================")
    for r in [2.0, 3.0, 5.0]:
        print(f"\n--- Testing Risk/Reward: 1:{r} ---")
        for p in [20, 50, 100]:
            t, w = backtest_wyckoff(df, period=p, rr=r)
            print(f"Structure Period {p} Candles | Trades: {t:4d} | Win Rate: {w:5.1f}%")
    print("=========================================================\n")
