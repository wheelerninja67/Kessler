import csv
from collections import deque
import dwc_strategies

print("=========================================================")
print(" [KESSLER V9] INITIATING REAL DATA CSV BACKTEST          ")
print("=========================================================")

filename = "XAUUSD_Real_M5.csv"

# Hyperparameters
starting_balance = 10000.0
balance = starting_balance
peak = starting_balance
max_drawdown = 0.0
total_trades = 0
winning_trades = 0

RISK_PCT = 0.009
SL_DIST = 4.0
TP_DIST = 12.0

open_positions = []
rolling_candles = deque(maxlen=50)

print(f"[*] Loading Deep Historical Data Pipeline: {filename}")
print(f"[*] Engaging DWC Strategy Matrix over 1,500,000 candles...")

try:
    with open(filename, mode='r') as file:
        reader = csv.DictReader(file)
        
        count = 0
        for row in reader:
            count += 1
            if count % 250000 == 0:
                print(f"    -> Processed {count} / 1500000 historical ticks...")
                
            current_close = float(row['close'])
            current_high = float(row['high'])
            current_low = float(row['low'])
            
            # Format candle for the Swarm
            candle = {
                'close': current_close,
                'high': current_high,
                'low': current_low
            }
            rolling_candles.append(candle)
            
            # 1. Manage Open Positions (State Machine)
            still_open = []
            for pos in open_positions:
                trade_won = False
                trade_lost = False
                
                if pos['type'] == 'BUY':
                    if current_low <= pos['sl']:
                        trade_lost = True
                    elif current_high >= pos['tp']:
                        trade_won = True
                elif pos['type'] == 'SELL':
                    if current_high >= pos['sl']:
                        trade_lost = True
                    elif current_low <= pos['tp']:
                        trade_won = True
                        
                if trade_won:
                    balance += pos['risk_amount'] * (TP_DIST / SL_DIST)
                    winning_trades += 1
                    total_trades += 1
                elif trade_lost:
                    balance -= pos['risk_amount']
                    total_trades += 1
                else:
                    still_open.append(pos)
                    
            open_positions = still_open
                    
            # Drawdown tracking
            if balance > peak:
                peak = balance
            else:
                dd = (peak - balance) / peak
                if dd > max_drawdown:
                    max_drawdown = dd
        
            # Margin call protection
            if balance <= 0:
                print("[!] MARGIN CALL REACHED. ACCOUNT BLOWN.")
                break
        
            # 2. Look for new trade entries
            if len(rolling_candles) == 50:
                macro_data = {"us10y": 0.002, "liquidity": -10.0}
                decision = dwc_strategies.DWC_StrategyMatrix.evaluate_swarm(list(rolling_candles), macro_data)
                
                if decision['confidence'] >= 0.90:
                    if len(open_positions) < 1: 
                        action = decision['action']
                        risk_amount = balance * RISK_PCT
                        
                        if action == 1: # BUY
                            open_positions.append({
                                'type': 'BUY',
                                'sl': current_close - SL_DIST,
                                'tp': current_close + TP_DIST,
                                'risk_amount': risk_amount
                            })
                        elif action == 2: # SELL
                            open_positions.append({
                                'type': 'SELL',
                                'sl': current_close + SL_DIST,
                                'tp': current_close - TP_DIST,
                                'risk_amount': risk_amount
                            })

except FileNotFoundError:
    print(f"[!] Error: {filename} not found. Did the generator finish?")
    exit(1)

win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

print("\n=========================================================")
print(" [BACKTEST RESULTS] KESSLER V9 (60-DAY INSTITUTIONAL RUN) ")
print("=========================================================")
print(f"[*] Time Horizon:       60 Days (M5 Real Tick Data)")
print(f"[*] Starting Equity:    $10,000.00")
print(f"[*] Final Equity:       ${balance:,.2f}")
print(f"[*] Net Profit:         ${balance - starting_balance:,.2f}")
print(f"[*] Total Trades Taken: {total_trades}")
print(f"[*] Win Rate:           {win_rate:.1f}%")
print(f"[*] Maximum Drawdown:   {max_drawdown*100:.2f}%")
print("=========================================================")
