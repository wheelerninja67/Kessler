import os
import time
from datetime import datetime
import dwc_strategies

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] MetaTrader5 not found. Please run via WINE.")
    exit(1)

print("=========================================================")
print(" [KESSLER V9] INITIATING HISTORICAL BACKTEST             ")
print("=========================================================")

if not mt5.initialize():
    print("[!] MT5 initialize() failed")
    exit(1)

symbol = "XAUUSD"
timeframe = mt5.TIMEFRAME_M5
num_candles = 1500000  # Requesting roughly 20 years of M5 data

print(f"[*] Requesting {num_candles} historical M5 candles for {symbol} from MT5 Servers...")
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)

if rates is None or len(rates) == 0:
    print("[!] Failed to fetch historical data from broker.")
    mt5.shutdown()
    exit(1)

actual_downloaded = len(rates)
print(f"[*] SUCCESS: Broker returned {actual_downloaded} historical M5 candles.")
if actual_downloaded < num_candles:
    print(f"[!] Note: Your broker only stores {actual_downloaded} M5 candles on their servers. You cannot go further back in time on this timeframe.")

print("[*] Historical data loaded. Engaging DWC Strategy Matrix...")

starting_balance = 10000.0
balance = starting_balance
peak = starting_balance
max_drawdown = 0.0

total_trades = 0
winning_trades = 0

# Perfected Parameters
RISK_PCT = 0.007
SL_DIST = 4.0
TP_DIST = 12.0

open_positions = []

# In a true backtest, we iterate candle by candle
for i in range(50, len(rates)):
    current_close = rates[i]['close']
    current_high = rates[i]['high']
    current_low = rates[i]['low']
    
    # 1. Manage Open Positions
    # We check if the current candle hit the SL or TP of any open trades
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
            still_open.append(pos) # Keep it open for the next candle
            
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
        break

    # 2. Look for new trade entries
    rolling_candles = rates[i-50:i+1]
    macro_data = {"us10y": 0.002, "liquidity": -10.0}
    decision = dwc_strategies.DWC_StrategyMatrix.evaluate_swarm(rolling_candles, macro_data)
    
    if decision['confidence'] >= 0.90:
        # We enforce a maximum of 1 open position at a time (Sniper Rules)
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

mt5.shutdown()

win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

print("=========================================================")
print(" [BACKTEST RESULTS] KESSLER V9 + DWC MATRIX              ")
print("=========================================================")
print(f"[*] Time Horizon:       {num_candles} M5 Candles (~1 Year)")
print(f"[*] Starting Equity:    ${starting_balance:,.2f}")
print(f"[*] Final Equity:       ${balance:,.2f}")
print(f"[*] Net Profit:         ${balance - starting_balance:,.2f}")
print(f"[*] Total Trades Taken: {total_trades}")
print(f"[*] Win Rate:           {win_rate:.1f}%")
print(f"[*] Maximum Drawdown:   {max_drawdown*100:.2f}%")
print("=========================================================")
