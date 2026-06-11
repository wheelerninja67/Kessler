import json
import urllib.request
import time
import os

# Target file for the Kessler Engine
OUTPUT_FILE = "data/scenarios/live_state.yaml"

def fetch_ticker_price(ticker):
    """
    Fetches the latest price for a ticker using Yahoo Finance's undocumented v8 API.
    This avoids needing to install heavy dependencies like yfinance on the terminal.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            meta = data['chart']['result'][0]['meta']
            return float(meta['regularMarketPrice'])
    except Exception as e:
        print(f"[!] Error fetching {ticker}: {e}")
        return 100.0 # Fallback default

def generate_live_scenario():
    print("=== KESSLER LIVE INGESTION PROTOCOL ===")
    
    # MBB is an ETF tracking Mortgage-Backed Securities
    mbs_price = fetch_ticker_price("MBB")
    print(f"[*] Live MBS (MBB) Price: ${mbs_price:.2f}")
    
    # SPY tracks the S&P 500
    spx_price = fetch_ticker_price("SPY")
    print(f"[*] Live SPX (SPY) Price: ${spx_price:.2f}")

    # Generate a live scenario based on the real-world prices
    # If the market is dropping, we amplify the fragility
    leverage_cap = 5.0
    if mbs_price < 90.0:
        print("[!] MBS below threshold. Increasing systemic leverage parameters.")
        leverage_cap = 8.0

    yaml_content = f"""name: Live Market Ingestion [{time.strftime("%Y-%m-%d %H:%M:%S")}]
count: 1000000
leverage_cap: {leverage_cap}
base_depth: 800.0
decay_rate: 0.5
resilience: 0.1
cb_threshold: 0.8
forward_ticks: 500
- tick: 50
  type: forced_liquidation
  magnitude: 0.15
  asset_id: 0
"""

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(yaml_content)

    print(f"[*] Live state successfully written to {OUTPUT_FILE}")
    print("=== READY FOR ENGINE CONTINUATION ===")

if __name__ == "__main__":
    generate_live_scenario()
