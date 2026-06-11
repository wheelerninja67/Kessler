import yfinance as yf
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def download_data():
    print("[*] VELOCITY MATRIX: Downloading NAS100 5-Minute Data...")
    df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('US/Eastern')
    
    # EMAs
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    return df

def backtest_velocity(df, max_trades_per_day):
    wins = 0
    losses = 0
    period = 48 # 4 hours
    rr = 3.0
    
    grouped = df.groupby(df.index.date)
    for date, day_data in grouped:
        trades_today = 0
        in_trade = False
        entry = 0.0
        sl = 0.0
        tp = 0.0
        dir = 0
        
        for i in range(period, len(day_data)):
            if trades_today >= max_trades_per_day:
                break
                
            window = day_data.iloc[i-period:i]
            current_c = day_data.iloc[i]
            
            # Session filter
            hour = current_c.name.hour
            minute = current_c.name.minute
            time_val = hour * 60 + minute
            
            if time_val < 570 or time_val > 960:
                if in_trade:
                    if dir == 1:
                        if current_c['Close'] > entry: wins +=1
                        else: losses += 1
                    else:
                        if current_c['Close'] < entry: wins +=1
                        else: losses += 1
                    in_trade = False
                continue
                
            if not in_trade:
                local_high = window['High'].max()
                local_low = window['Low'].min()
                
                is_uptrend = current_c['Close'] > current_c['EMA_200'] and current_c['EMA_50'] > current_c['EMA_200']
                is_downtrend = current_c['Close'] < current_c['EMA_200'] and current_c['EMA_50'] < current_c['EMA_200']
                
                if current_c['Close'] > local_high and is_uptrend:
                    in_trade = True
                    entry = current_c['Close']
                    sl = current_c['Low'] - 10.0
                    tp = entry + ((entry - sl) * rr)
                    dir = 1
                elif current_c['Close'] < local_low and is_downtrend:
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
                        trades_today += 1
                    elif current_c['High'] >= tp:
                        wins += 1
                        in_trade = False
                        trades_today += 1
                else:
                    if current_c['High'] >= sl:
                        losses += 1
                        in_trade = False
                        trades_today += 1
                    elif current_c['Low'] <= tp:
                        wins += 1
                        in_trade = False
                        trades_today += 1
                        
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    expectancy = ( (win_rate/100) * rr ) - ( (1 - win_rate/100) * 1 ) if total > 0 else 0
    return total, win_rate, expectancy

if __name__ == "__main__":
    df = download_data()
    print("\n=========================================================")
    print(" [KESSLER MD] VELOCITY BACKTEST: 1 Trade vs 2 Trades/Day")
    print("=========================================================")
    
    t1, w1, e1 = backtest_velocity(df, max_trades_per_day=1)
    print(f"[*] STRICT 1 TRADE PER DAY:")
    print(f"    Total Trades: {t1} | Win Rate: {w1:.1f}% | Expectancy: {e1:.2f}R | Net Profit: +{t1 * e1:.2f}R")
    
    print("\n---------------------------------------------------------")
    
    t2, w2, e2 = backtest_velocity(df, max_trades_per_day=2)
    print(f"[*] AGGRESSIVE 2 TRADES PER DAY:")
    print(f"    Total Trades: {t2} | Win Rate: {w2:.1f}% | Expectancy: {e2:.2f}R | Net Profit: +{t2 * e2:.2f}R")
    
    print("=========================================================\n")
