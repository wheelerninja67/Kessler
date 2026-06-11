import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def download_data():
    print("[*] Downloading 60 days of NQ=F (NAS100) 5-minute data...")
    df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    
    # yfinance returns timezone-aware data. Convert to US/Eastern
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('US/Eastern')
    return df

def backtest_orb(df):
    wins = 0
    losses = 0
    
    grouped = df.groupby(df.index.date)
    for date, day_data in grouped:
        orb_data = day_data.between_time('09:30', '09:55')
        if len(orb_data) < 4: continue
        
        orb_high = orb_data['High'].max()
        orb_low = orb_data['Low'].min()
        
        post_orb = day_data.between_time('10:00', '15:55')
        in_trade = False
        entry = 0.0
        sl = 0.0
        tp = 0.0
        dir = 0
        
        for i in range(len(post_orb)):
            row = post_orb.iloc[i]
            if not in_trade:
                if row['Close'] > orb_high:
                    in_trade = True
                    entry = row['Close']
                    sl = orb_low # Stop below ORB
                    tp = entry + ((entry - sl) * 2.0) # 1:2 R/R
                    dir = 1
                elif row['Close'] < orb_low:
                    in_trade = True
                    entry = row['Close']
                    sl = orb_high # Stop above ORB
                    tp = entry - ((sl - entry) * 2.0) # 1:2 R/R
                    dir = -1
            else:
                if dir == 1:
                    if row['Low'] <= sl:
                        losses += 1
                        break
                    elif row['High'] >= tp:
                        wins += 1
                        break
                else:
                    if row['High'] >= sl:
                        losses += 1
                        break
                    elif row['Low'] <= tp:
                        wins += 1
                        break
    
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    return total, win_rate

def backtest_silver_bullet(df):
    wins = 0
    losses = 0
    
    grouped = df.groupby(df.index.date)
    for date, day_data in grouped:
        # 1. Identify liquidity pools before 10:00
        pre_10_data = day_data.between_time('08:00', '09:55')
        if len(pre_10_data) < 10: continue
        bsl = pre_10_data['High'].max()
        ssl = pre_10_data['Low'].min()
        
        # 2. 10:00 AM - 11:00 AM Silver Bullet Window
        sb_window = day_data.between_time('10:00', '11:00')
        if len(sb_window) == 0: continue
        
        # Mechanical proxy for Sweep -> MSS -> FVG
        # We look for a sweep of BSL or SSL, followed by a close back inside the range (MSS proxy)
        in_trade = False
        swept_bsl = False
        swept_ssl = False
        
        entry = 0.0
        sl = 0.0
        tp = 0.0
        dir = 0
        
        for i in range(len(sb_window)):
            row = sb_window.iloc[i]
            if not in_trade:
                if row['High'] > bsl: swept_bsl = True
                if row['Low'] < ssl: swept_ssl = True
                
                # Faded entry (MSS proxy)
                if swept_bsl and row['Close'] < (bsl - 10.0):
                    in_trade = True
                    entry = row['Close']
                    sl = row['High'] + 10.0 # Stop above the sweep
                    tp = entry - ((sl - entry) * 2.0)
                    dir = -1
                elif swept_ssl and row['Close'] > (ssl + 10.0):
                    in_trade = True
                    entry = row['Close']
                    sl = row['Low'] - 10.0 # Stop below the sweep
                    tp = entry + ((entry - sl) * 2.0)
                    dir = 1
            else:
                if dir == 1:
                    if row['Low'] <= sl:
                        losses += 1
                        break
                    elif row['High'] >= tp:
                        wins += 1
                        break
                else:
                    if row['High'] >= sl:
                        losses += 1
                        break
                    elif row['Low'] <= tp:
                        wins += 1
                        break
                        
        # If trade is still open after 11:00, manage it until 15:55
        if in_trade:
            post_sb = day_data.between_time('11:05', '15:55')
            for i in range(len(post_sb)):
                row = post_sb.iloc[i]
                if dir == 1:
                    if row['Low'] <= sl:
                        losses += 1; break
                    elif row['High'] >= tp:
                        wins += 1; break
                else:
                    if row['High'] >= sl:
                        losses += 1; break
                    elif row['Low'] <= tp:
                        wins += 1; break
    
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    return total, win_rate

if __name__ == "__main__":
    df = download_data()
    print("\n--- ORB (Opening Range Breakout) ---")
    t1, w1 = backtest_orb(df)
    print(f"Trades: {t1} | Win Rate: {w1:.1f}% | R:R = 1:2")
    
    print("\n--- ICT Silver Bullet (Sweep + MSS Proxy) ---")
    t2, w2 = backtest_silver_bullet(df)
    print(f"Trades: {t2} | Win Rate: {w2:.1f}% | R:R = 1:2")
