import ctypes
import sys

print("=========================================================")
print("      [KESSLER CRUCIBLE] ADVERSARIAL STRESS TEST         ")
print("=========================================================")

try:
    ml_lib = ctypes.CDLL("./ml.dll")
    ml_lib.evaluate_macro_veto.argtypes = [ctypes.c_uint8, ctypes.c_double, ctypes.c_double]
    ml_lib.evaluate_macro_veto.restype = ctypes.c_uint8
except OSError:
    print("[!] Failed to load ml.dll. Crucible aborted.")
    sys.exit(1)

# Test Scenarios: (Scenario Name, Raw AI Action, US10Y Velocity, Liquidity Velocity, Expected Result)
scenarios = [
    ("The Standard Grind (Stable Market)", 1, 0.01, 10.0, 1),
    ("The Repo Crisis (Liquidity Vanishes)", 1, 0.05, -500.0, 0),
    ("The Inflation Panic (Yields Spike)", 1, 0.50, -10.0, 0),
    ("The Flash Crash (Yields Spike + Liquidity Drops)", 1, 0.75, -1000.0, 0),
    ("The Easy Money Era (Rates Drop, Money Printer Brr)", 1, -0.20, 200.0, 1)
]

passed_tests = 0

for name, raw_action, us10y, liquidity, expected in scenarios:
    print(f"\n[*] Testing Scenario: {name}")
    print(f"    Input  -> AI: {'BUY' if raw_action==1 else 'SELL'}, Yield Vel: {us10y}, Liq Vel: {liquidity}")
    
    result = ml_lib.evaluate_macro_veto(raw_action, us10y, liquidity)
    str_result = "BUY" if result == 1 else "VETO"
    str_expected = "BUY" if expected == 1 else "VETO"
    
    if result == expected:
        print(f"    [PASS] Engine correctly output: {str_result}")
        passed_tests += 1
    else:
        print(f"    [FAIL] Engine output {str_result}, but expected {str_expected}!")

print("\n=========================================================")
print(f"CRUCIBLE RESULT: {passed_tests}/{len(scenarios)} PASSED")
print("=========================================================")

if passed_tests < len(scenarios):
    sys.exit(1)
