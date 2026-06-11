import yfinance as yf
import pandas as pd
import numpy as np
import itertools
import warnings
import time

warnings.filterwarnings('ignore')

def download_data():
    print("[*] QUANT GRID: Downloading 60 days of pure NAS100 5-minute data...")
    df = yf.download("NQ=F", period="60d", interval="5m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    df.index = df.index.tz_convert('US/Eastern')
    
    # Calculate Macro Trend Filters
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    return df

def simulate_grid(df):
    print("[*] QUANT GRID: Initiating Deep-Matrix Permutations...")
    
    # Grid Parameters
    strategies = ['MOMENTUM_BREAKOUT', 'TRAP_FADE', 'WYCKOFF_DELTA']
    lookback_periods = [12, 24, 48] # 1hr, 2hr, 4hr structural mapping
    sessions = [
        ('09:30', '16:00'), # All Day NY
        ('09:30', '10:30'), # Pure Open Volatility
        ('10:00', '11:00')  # ICT Silver Bullet Window
    ]
    trend_filters = [False, True] # Trade against macro trend or strictly with it
    rrs = [1.5, 2.0, 3.0]
    
    permutations = list(itertools.product(strategies, lookback_periods, sessions, trend_filters, rrs))
    total_perms = len(permutations)
    print(f"[*] QUANT GRID: Testing {total_perms} distinct algorithmic variants...\n")
    
    best_expectancy = -999.0
    best_setup = None
    
    # Fast iteration by extracting values to numpy arrays for speed, 
    # but we'll stick to a fast pandas loop for simplicity in this prototype.
    
    results = []
    
    for idx, (strategy, period, session, use_trend, rr) in enumerate(permutations):
        wins = 0
        losses = 0
        
        session_start, session_end = session
        
        for i in range(period, len(df), 5): # Stride by 5 to speed up the brute force
            window = df.iloc[i-period:i]
            current_c = df.iloc[i]
            
            # Session Filter
            time_str = current_c.name.strftime('%H:%M')
            if not (session_start <= time_str <= session_end):
                continue
                
            # Trend Filter
            is_uptrend = current_c['Close'] > current_c['EMA_200'] and current_c['EMA_50'] > current_c['EMA_200']
            is_downtrend = current_c['Close'] < current_c['EMA_200'] and current_c['EMA_50'] < current_c['EMA_200']
            
            local_high = window['High'].max()
            local_low = window['Low'].min()
            
            entry = 0.0
            sl = 0.0
            tp = 0.0
            dir = 0
            
            if strategy == 'MOMENTUM_BREAKOUT':
                if current_c['Close'] > local_high and (not use_trend or is_uptrend):
                    entry = current_c['Close']; sl = current_c['Low'] - 5.0; tp = entry + ((entry - sl) * rr); dir = 1
                elif current_c['Close'] < local_low and (not use_trend or is_downtrend):
                    entry = current_c['Close']; sl = current_c['High'] + 5.0; tp = entry - ((sl - entry) * rr); dir = -1
                    
            elif strategy == 'TRAP_FADE':
                if current_c['Close'] > local_high and (not use_trend or is_downtrend): # Fade the high
                    entry = current_c['Close']; sl = current_c['High'] + 10.0; tp = entry - ((sl - entry) * rr); dir = -1
                elif current_c['Close'] < local_low and (not use_trend or is_uptrend): # Fade the low
                    entry = current_c['Close']; sl = current_c['Low'] - 10.0; tp = entry + ((entry - sl) * rr); dir = 1
                    
            elif strategy == 'WYCKOFF_DELTA':
                low_idx = window['Low'].argmin(); low_vol = window.iloc[low_idx]['Volume']
                high_idx = window['High'].argmax(); high_vol = window.iloc[high_idx]['Volume']
                if current_c['Low'] < local_low and current_c['Volume'] < low_vol and (not use_trend or is_uptrend):
                    entry = current_c['Close']; sl = current_c['Low'] - 10.0; tp = entry + ((entry - sl) * rr); dir = 1
                elif current_c['High'] > local_high and current_c['Volume'] < high_vol and (not use_trend or is_downtrend):
                    entry = current_c['Close']; sl = current_c['High'] + 10.0; tp = entry - ((sl - entry) * rr); dir = -1
                    
            if dir != 0:
                # Fast forward to resolve trade
                for j in range(i+1, min(i+100, len(df))):
                    future_c = df.iloc[j]
                    if dir == 1:
                        if future_c['Low'] <= sl: losses += 1; break
                        elif future_c['High'] >= tp: wins += 1; break
                    else:
                        if future_c['High'] >= sl: losses += 1; break
                        elif future_c['Low'] <= tp: wins += 1; break

        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        # Expectancy formula: (Win% * Reward) - (Loss% * Risk)
        # Using 1 unit of risk
        expectancy = ( (win_rate/100) * rr ) - ( (1 - win_rate/100) * 1 ) if total > 20 else -999.0
        
        if expectancy > best_expectancy and total >= 20: # Minimum 20 trades to be statistically valid
            best_expectancy = expectancy
            best_setup = {
                'Strategy': strategy, 'Lookback': period, 'Session': session,
                'Trend_Filter': use_trend, 'Risk_Reward': rr,
                'Trades': total, 'Win_Rate': win_rate, 'Expectancy': expectancy
            }
            print(f"[NEW BEST FOUND] {strategy} | Window: {session} | Trend: {use_trend} | R/R: 1:{rr} -> Win Rate: {win_rate:.1f}% | Expectancy: {expectancy:.2f}R")

    print("\n=========================================================")
    print(" [KESSLER MD] QUANTITATIVE GRID SEARCH COMPLETE")
    print("=========================================================")
    print("THE MATHEMATICALLY PERFECT SETUP:")
    for k, v in best_setup.items():
        print(f" > {k}: {v}")
    print("=========================================================\n")

if __name__ == "__main__":
    df = download_data()
    simulate_grid(df)
