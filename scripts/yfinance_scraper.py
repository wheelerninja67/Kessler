import yfinance as yf
import pandas as pd
import os

def fetch_20_year_history():
    print("[*] Igniting YFinance 20-Year Macro Scraper...")
    
    symbols = {
        "GOLD": "GC=F",
        "USDX": "DX-Y.NYB",
        "US10Y": "^TNX",
        "NASDAQ": "^IXIC",
        "BTC": "BTC-USD"
    }
    
    os.makedirs("data/macro", exist_ok=True)
    
    for name, ticker in symbols.items():
        print(f"[*] Scraping 20-Year History for {name} ({ticker})...")
        try:
            data = yf.download(ticker, period="max", interval="1d", progress=False)
            if data.empty:
                print(f"[!] Warning: No data found for {name}")
                continue
                
            # Filter to last 20 years if available
            data = data[data.index >= '2004-01-01']
            
            filepath = f"data/macro/{name}_20yr.csv"
            data.to_csv(filepath)
            print(f"[+] Saved {len(data)} daily candles to {filepath}")
        except Exception as e:
            print(f"[!] Error fetching {name}: {e}")

if __name__ == "__main__":
    fetch_20_year_history()
