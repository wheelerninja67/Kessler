import yfinance as yf
import pandas as pd

print("=========================================================")
print(" [INSTITUTIONAL PIPELINE] DOWNLOADING REAL M5 GOLD DATA ")
print("=========================================================")

# Yahoo finance restricts 5-minute data to the last few days
symbol = "GC=F" # Gold Futures
interval = "5m"
period = "59d"

print(f"[*] Fetching real market data from Wall Street servers...")
print(f"[*] Symbol: {symbol} | Interval: {interval} | Period: {period}")

data = yf.download(symbol, period=period, interval=interval, progress=False)

if data.empty:
    print("[!] Failed to fetch data from Yahoo Finance.")
    exit(1)

data = data.reset_index()

# Yfinance returns columns like 'Datetime', 'Open', 'High', etc.
# We will just force rename the first 6 columns
data.columns = ['time', 'open', 'high', 'low', 'close', 'adj_close', 'volume'][:len(data.columns)]

filename = "XAUUSD_Real_M5.csv"
try:
    data[['time', 'open', 'high', 'low', 'close', 'volume']].to_csv(filename, index=False)
except KeyError:
    # If adj_close is missing
    data.columns = ['time', 'open', 'high', 'low', 'close', 'volume'][:len(data.columns)]
    data[['time', 'open', 'high', 'low', 'close', 'volume']].to_csv(filename, index=False)

print(f"[*] SUCCESS! Downloaded {len(data)} REAL 5-minute candles.")
print(f"[*] Saved to {filename}")
print("=========================================================")
