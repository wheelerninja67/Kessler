import pandas as pd
import numpy as np
import struct

DATA_FILE = "data/SOLUSDT_5m_historical.csv"
ROLLING_WINDOW = 20

print("[*] Generating binary physics file for Zig MEV Engine...")
df = pd.read_csv(DATA_FILE)
df['Mean_20'] = df['close'].rolling(window=ROLLING_WINDOW).mean()
df['Std_20'] = df['close'].rolling(window=ROLLING_WINDOW).std()
df['Z_Score'] = (df['close'] - df['Mean_20']) / df['Std_20']
df.dropna(inplace=True)

# Write to a raw binary file for instant Zig parsing
# Format: [f32 close, f32 z_score] sequentially
with open("data/physics.bin", "wb") as f:
    for _, row in df.iterrows():
        f.write(struct.pack('<ff', float(row['close']), float(row['Z_Score'])))
        
print("[*] physics.bin successfully generated. Ready for Zig.")
