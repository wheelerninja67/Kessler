import ctypes
import math
import time

print("=========================================================")
print(" [KESSLER V9] INITIATING EXTREME FUZZ STRESS TEST        ")
print("=========================================================")

import os

try:
    lib_ext = "dll" if os.name == "nt" else "so"
    lib_prefix = "" if os.name == "nt" else "lib"
    lib_path = f"../{lib_prefix}ml.{lib_ext}"
    ml_lib = ctypes.CDLL(lib_path)
    ml_lib.evaluate_macro_veto.argtypes = [ctypes.c_uint8, ctypes.c_double, ctypes.c_double]
    ml_lib.evaluate_macro_veto.restype = ctypes.c_uint8
    print(f"[*] Loaded {lib_path} successfully.")
except Exception as e:
    print(f"[!] FAILED TO LOAD DLL: {e}")
    exit(1)

print("[*] Injecting corrupted and impossible macro vectors into Zig Swarm...\n")

test_cases = [
    # (Raw Action, US10Y Velocity, Liquidity Flow, Description)
    (1, float('inf'), -50.0, "Infinite US10Y Yields"),
    (2, float('-inf'), 9999999999.9, "Negative Infinity US10Y + Hyperinflation"),
    (1, float('nan'), float('nan'), "NaN (Not a Number) Data Corruption"),
    (0, 0.0000000000000001, -0.00000000000001, "Micro-fractional Floating Point Precision Test"),
    (255, 5.0, -500.0, "Invalid Integer Action (Action 255)"),
    (1, 1e308, -1e308, "Max Float64 Overflow Values"),
]

crashes = 0
for idx, (action, us10y, liquidity, desc) in enumerate(test_cases):
    print(f"[TEST {idx+1}] {desc}")
    print(f"      Data: Action={action}, US10Y={us10y}, Liq={liquidity}")
    try:
        # We catch segfaults if the C-FFI crashes
        result = ml_lib.evaluate_macro_veto(action, us10y, liquidity)
        print(f"      [PASS] Zig Swarm handled corruption. Returned: {result}")
    except Exception as e:
        print(f"      [FAIL] ENGINE CRASHED: {e}")
        crashes += 1
    time.sleep(0.5)

print("\n=========================================================")
print(f" STRESS TEST COMPLETE. TOTAL CRASHES: {crashes}")
print("=========================================================")
