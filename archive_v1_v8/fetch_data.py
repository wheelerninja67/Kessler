import os
import MetaTrader5 as mt5
from datetime import datetime, timedelta

def main():
    print("[*] Bridging to MT5 via Python to fetch pure tick data...")
    if not mt5.initialize():
        print("[!] MT5 Init failed")
        return
        
    mt5.login(20073104, password="EVoDLj0>E", server="FundingPips-SIM1")
    
    utc_to = datetime.utcnow()
    utc_from = utc_to - timedelta(days=60)
    
    rates = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M5, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print("[!] Failed to get rates")
        mt5.shutdown()
        return
        
    print(f"[*] Pulled {len(rates)} raw M5 candles. Writing to pure CSV for Zig Engine...")
    with open("xauusd_clean.csv", "w") as f:
        for r in rates:
            f.write(f"{r['time']},{r['open']},{r['high']},{r['low']},{r['close']}\n")
            
    mt5.shutdown()
    os.system("wineserver -k")
    print("[*] MT5 killed. Data pipeline complete.")

if __name__ == "__main__":
    main()
