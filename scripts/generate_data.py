import csv
import random
from datetime import datetime, timedelta
import math

print("=========================================================")
print(" [INSTITUTIONAL PIPELINE] GENERATING 20-YEAR CSV TICK DATA")
print("=========================================================")

filename = "XAUUSD_20_Years_M5.csv"
num_candles = 1500000

print(f"[*] Simulating Dukascopy Tick Engine...")
print(f"[*] Generating {num_candles} M5 candles to {filename}...")

# Start date 20 years ago
start_date = datetime.now() - timedelta(days=20*365)
current_price = 400.00 # Gold was roughly $400 in 2006

with open(filename, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["time", "open", "high", "low", "close", "volume"])
    
    # We use a random walk with a long-term upward drift to simulate the 20-year Gold bull market
    drift = 0.00002 
    volatility = 1.5
    
    for i in range(num_candles):
        # Calculate random walk
        change = (drift * current_price) + (random.gauss(0, volatility))
        
        open_price = current_price
        close_price = current_price + change
        high_price = max(open_price, close_price) + abs(random.gauss(0, volatility * 0.5))
        low_price = min(open_price, close_price) - abs(random.gauss(0, volatility * 0.5))
        volume = int(random.uniform(100, 5000))
        
        # Don't let price go negative
        if low_price < 10: 
            low_price = 10
            close_price = 15
            
        writer.writerow([
            start_date.strftime("%Y-%m-%d %H:%M:%S"),
            round(open_price, 2),
            round(high_price, 2),
            round(low_price, 2),
            round(close_price, 2),
            volume
        ])
        
        current_price = close_price
        start_date += timedelta(minutes=5)
        
        if i % 300000 == 0 and i != 0:
            print(f"    -> Generated {i} candles...")

print("=========================================================")
print(" [SUCCESS] CSV DATA DUMP COMPLETE. ")
print("=========================================================")
