import os
import time
import threading

# We import the live engine
import kessler_v9_engine

print("=========================================================")
print(" [CHAOS MONKEY] INJECTING FATAL NETWORK CORRUPTION       ")
print("=========================================================")

# 1. We mock the MT5 module entirely
class MockMT5:
    def initialize(self): return True
    def account_info(self):
        class MockInfo:
            trade_mode = 0 # Demo
            equity = 10000.0
        return MockInfo()
        
    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        # FATAL INJECTION: Instead of returning an array of dicts with floats, 
        # we simulate a corrupted JSON response from a dropped network packet.
        # We inject a String where a Float should be.
        print("[CHAOS MONKEY] Injecting Type Corruption (String instead of Float)")
        return [{'close': "CORRUPTED_STRING_DATA"}]

# Replace the live MT5 bridge with our Chaos Monkey
kessler_v9_engine.mt5 = MockMT5()

# Override the loop so it only runs once
def run_once():
    try:
        kessler_v9_engine.run_v9_engine()
    except Exception as e:
        print("\n=========================================================")
        print(f" [!!!] CHAOS MONKEY SUCCESS. ENGINE CRASHED. ")
        print(f" [!!!] FATAL ERROR: {e}")
        print("=========================================================")

# Run the corrupted engine
run_once()
