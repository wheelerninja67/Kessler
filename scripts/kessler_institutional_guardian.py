import time
import sys
import psutil
from datetime import datetime
import os

try:
    import MetaTrader5 as mt5
except ImportError:
    print("[!] MetaTrader5 library not found.")
    sys.exit(1)

# Institutional Proprietary Firm Constraints
MAX_DAILY_DRAWDOWN_PCT = 2.9 # Hard limit: 2.9% (Funding Pips Two Step Pro bans at 3.0%)
MAX_TOTAL_DRAWDOWN_PCT = 5.9 # Hard limit: 5.9% (Funding Pips Two Step Pro bans at 6.0%)

def kill_kessler_engine():
    print("[!!!] INITIATING EMERGENCY KESSLER ENGINE SHUTDOWN [!!!]")
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline'] and 'kessler_v9_engine.py' in ' '.join(proc.info['cmdline']):
                print(f"[*] Terminating Kessler Engine PID: {proc.info['pid']}")
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def close_all_positions():
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return

    print(f"[!!!] LIQUIDATING {len(positions)} OPEN POSITIONS [!!!]")
    for pos in positions:
        tick = mt5.symbol_info_tick(pos.symbol)
        close_price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": close_price,
            "deviation": 20,
            "magic": 9999,
            "comment": "GUARDIAN LIQUIDATION",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[!] Failed to liquidate ticket {pos.ticket}: {result.comment}")
        else:
            print(f"[*] Position {pos.ticket} successfully liquidated.")

def run_guardian():
    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
        return

    print("=========================================================")
    print("  [KESSLER INSTITUTIONAL GUARDIAN] ACTIVE                ")
    print("=========================================================")
    print(f"[*] Max Daily Drawdown Locked: {MAX_DAILY_DRAWDOWN_PCT}%")
    print(f"[*] Max Total Drawdown Locked: {MAX_TOTAL_DRAWDOWN_PCT}%")
    
    account_info = mt5.account_info()
    if account_info is None:
        print("[!] Failed to get account info")
        return
        
    start_of_day_balance = account_info.balance 
    initial_balance = account_info.balance 
    
    try:
        while True:
            acc = mt5.account_info()
            if acc is None:
                continue
                
            current_equity = acc.equity
            
            # Calculate Drawdowns
            daily_dd_pct = ((start_of_day_balance - current_equity) / start_of_day_balance) * 100
            total_dd_pct = ((initial_balance - current_equity) / initial_balance) * 100
            
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"=========================================================")
            print(f"         [KESSLER INSTITUTIONAL GUARDIAN]                ")
            print(f"=========================================================")
            print(f"[*] Current Equity: ${current_equity:.2f}")
            print(f"[*] Daily Drawdown: {daily_dd_pct:.2f}% (Limit: {MAX_DAILY_DRAWDOWN_PCT}%)")
            print(f"[*] Total Drawdown: {total_dd_pct:.2f}% (Limit: {MAX_TOTAL_DRAWDOWN_PCT}%)")
            print(f"=========================================================")
            
            if daily_dd_pct >= MAX_DAILY_DRAWDOWN_PCT or total_dd_pct >= MAX_TOTAL_DRAWDOWN_PCT:
                print("\n[CRITICAL] INSTITUTIONAL DRAWDOWN LIMIT APPROACHING.")
                close_all_positions()
                kill_kessler_engine()
                print("[*] GUARDIAN PROTOCOL COMPLETE. Account Saved.")
                break
                
            time.sleep(1) # Check every second
            
    except KeyboardInterrupt:
        print("\n[*] Guardian shutting down...")
    finally:
        mt5.shutdown()

if __name__ == '__main__':
    run_guardian()
