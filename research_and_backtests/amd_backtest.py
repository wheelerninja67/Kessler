import pandas as pd
import numpy as np

def run_backtest():
    try:
        df = pd.read_csv("xauusd_clean.csv", names=["time", "open", "high", "low", "close"])
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print("=========================================================")
    print("        [KESSLER V1.1] AMD EDGE BACKTEST (60 DAYS)       ")
    print("=========================================================")
    print(f"[*] Python Fallback Engine: Loaded {len(df)} M5 Candles.")
    
    balance = 10750.0  # $10,750 USD = 9 Lakh INR
    max_balance = balance
    total_trades = 0
    wins = 0

    in_trade = False
    trade_dir = 0
    entry_price = 0
    sl = 0
    tp = 0
    trade_volume = 0

    asian_high = 0.0
    asian_low = 99999.0
    has_traded_today = False
    current_day = -1

    # Convert time to datetime
    df['time'] = pd.to_datetime(df['time'], unit='s')

    swept_high = False
    swept_low = False

    for index, row in df.iterrows():
        dt = row['time']
        day = dt.day
        hour = dt.hour

        if day != current_day:
            current_day = day
            asian_high = 0.0
            asian_low = 99999.0
            has_traded_today = False
            swept_high = False
            swept_low = False
            
            # Close trade overnight
            if in_trade:
                if trade_dir == 1:
                    balance += (row['open'] - entry_price) * trade_volume
                else:
                    balance += (entry_price - row['open']) * trade_volume
                in_trade = False

        # Asian Session (01:00 to 09:00 Broker Time)
        if 1 <= hour < 9:
            if row['high'] > asian_high: asian_high = row['high']
            if row['low'] < asian_low: asian_low = row['low']

        # London/NY Session (09:00 to 22:00)
        if 9 <= hour < 22 and not in_trade:
            range_size = asian_high - asian_low
            
            if 3.0 < range_size < 45.0:
                # Track sweeps
                if row['high'] > asian_high: swept_high = True
                if row['low'] < asian_low: swept_low = True

                # Sell Signal: Fade the Breakout of Asian High (Mean Reversion)
                if row['close'] > (asian_high + 0.5):
                    in_trade = True
                    trade_dir = -1
                    entry_price = row['close']
                    sl = entry_price + 6.0  # 60 pip stop
                    risk_dist = sl - entry_price
                    tp = entry_price - 12.0 # 1:2 R/R
                    
                    risk_amount = balance * 0.03
                    trade_volume = risk_amount / risk_dist if risk_dist > 0 else 0
                    has_traded_today = True

                # Buy Signal: Fade the Breakout of Asian Low (Mean Reversion)
                elif row['close'] < (asian_low - 0.5):
                    in_trade = True
                    trade_dir = 1
                    entry_price = row['close']
                    sl = entry_price - 6.0 # 60 pip stop
                    risk_dist = entry_price - sl
                    tp = entry_price + 12.0 # 1:2 R/R
                    
                    risk_amount = balance * 0.03
                    trade_volume = risk_amount / risk_dist if risk_dist > 0 else 0
                    has_traded_today = True

        if in_trade:
            if trade_dir == 1:
                if row['low'] <= sl:
                    balance -= (entry_price - sl) * trade_volume
                    in_trade = False
                    total_trades += 1
                elif row['high'] >= tp:
                    balance += (tp - entry_price) * trade_volume
                    in_trade = False
                    total_trades += 1
                    wins += 1
            else:
                if row['high'] >= sl:
                    balance -= (sl - entry_price) * trade_volume
                    in_trade = False
                    total_trades += 1
                elif row['low'] <= tp:
                    balance += (entry_price - tp) * trade_volume
                    in_trade = False
                    total_trades += 1
                    wins += 1
                    
        if balance > max_balance:
            max_balance = balance

    print("=========================================================")
    print(f"Starting Equity: $10,750.00 (₹9 Lakh INR)")
    print(f"Ending Equity:   ${balance:.2f}")
    print(f"Total Profit:    ${balance - 10750.0:.2f}")
    print(f"Max Equity:      ${max_balance:.2f}")
    print(f"Total Sweeps:    {total_trades}")
    if total_trades > 0:
        print(f"Sniper Win Rate: {(wins/total_trades)*100:.1f}%")
    print("=========================================================")

if __name__ == "__main__":
    run_backtest()
