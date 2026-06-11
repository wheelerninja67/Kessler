import MetaTrader5 as mt5
import sys
import time

def test_v5_data():
    print("=========================================================")
    print("[*] KESSLER V5 PROBE: Testing Broker Capabilities")
    print("=========================================================")
    if not mt5.initialize():
        print("[-] Failed to initialize MT5")
        sys.exit(1)
        
    print("[*] MT5 Connection Established. Probing Broker Servers...")
    
    # 1. Probe for DXY (Dollar Index)
    print("\n[*] TEST 1: DXY (US Dollar Index) Macro-Correlation Data")
    dxy_symbols = ["USDX", "DX", "DXY", "US Dollar Index"]
    dxy_found = False
    for sym in dxy_symbols:
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 1)
        if rates is not None and len(rates) > 0:
            print(f"[+] SUCCESS: Found live data for symbol: '{sym}'")
            print(f"    Latest {sym} Close: {rates[0]['close']}")
            dxy_found = True
            break
            
    if not dxy_found:
        print("[-] FAILED: Broker does not provide Dollar Index (DXY) pricing data to retail clients.")
        
    # 2. Probe for Level-2 Order Book Data on XAUUSD
    print("\n[*] TEST 2: Level-2 Market Depth (DOM) on XAUUSD")
    if mt5.market_book_add("XAUUSD"):
        # Give it a second to subscribe and pull the stream
        time.sleep(1)
        book = mt5.market_book_get("XAUUSD")
        if book is not None and len(book) > 0:
            print("[+] SUCCESS: Broker provides raw Level-2 limit order data!")
            buy_orders = [o for o in book if o.type == mt5.BOOK_TYPE_BUY]
            sell_orders = [o for o in book if o.type == mt5.BOOK_TYPE_SELL]
            print(f"    Visible Buy Limit Levels: {len(buy_orders)}")
            print(f"    Visible Sell Limit Levels: {len(sell_orders)}")
        else:
            print("[-] FAILED: Broker allowed subscription but returned an EMPTY order book. (They are hiding liquidity data).")
        mt5.market_book_release("XAUUSD")
    else:
        print("[-] FAILED: Broker explicitly denied the Level-2 market_book_add() request.")
        
    mt5.shutdown()
    print("\n[*] Probe Complete.")

if __name__ == "__main__":
    test_v5_data()
