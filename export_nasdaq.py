import yfinance as yf
import pandas as pd
import struct
import numpy as np

print("[*] Fetching 60 Days of Nasdaq (NQ=F) 5-Minute Data from Yahoo Finance...")
ticker = yf.Ticker("NQ=F")
df = ticker.history(period="60d", interval="5m")
df.dropna(inplace=True)

print(f"[*] Fetched {len(df)} 5-minute Nasdaq candles.")
print("[*] Calculating Core Physics (ATR, EMAs, Breakouts)...")

# Calculate EMAs
df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
df['EMA_100'] = df['Close'].ewm(span=100, adjust=False).mean()

# Calculate ATR
df['H-L'] = df['High'] - df['Low']
df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
df['ATR_14'] = df['TR'].rolling(window=14).mean()
df['Avg_ATR_Daily'] = df['ATR_14'].rolling(window=288).mean() 

df.dropna(inplace=True)

print("[*] Dumping native Nasdaq Physics to binary struct for C Engine...")
# We will pass: [Open, High, Low, Close, EMA_50, EMA_100, ATR_14, Avg_ATR_Daily]
with open("data/nasdaq_physics.bin", "wb") as f:
    for _, row in df.iterrows():
        f.write(struct.pack('<ffffffff', 
                            float(row['Open']), float(row['High']), 
                            float(row['Low']), float(row['Close']),
                            float(row['EMA_50']), float(row['EMA_100']),
                            float(row['ATR_14']), float(row['Avg_ATR_Daily'])))

print("[*] nasdaq_physics.bin successfully generated. Ready for OpenMP C Engine.")
