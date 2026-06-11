import random
import numpy as np

# --- 300x MONTE CARLO MASTER SIMULATION ---

NUM_SIMULATIONS = 300
WIN_RATE = 0.333
REWARD = 3.0
RISK_PCT = 0.005 # 0.5% Sniper Risk
TRADES_PER_DAY = 1.15

# Constraints
MAX_TOTAL_DD = 0.09 # 9% max total drawdown buffer (FundingPips gives 10%)

def run_phase(start_balance, target_pct, risk_pct):
    balance = start_balance
    high_water_mark = start_balance
    target = start_balance * (1.0 + target_pct)
    trades = 0
    
    while balance < target:
        trades += 1
        risk_amount = balance * risk_pct
        
        if random.random() < WIN_RATE:
            balance += (risk_amount * REWARD)
            if balance > high_water_mark:
                high_water_mark = balance
        else:
            balance -= risk_amount
            
        if (high_water_mark - balance) / high_water_mark > MAX_TOTAL_DD:
            return False, trades 
            
    return True, trades

def simulate_full_ladder():
    total_trades = 0
    
    # --- PHASE 1: $10K GRIND (KAMIKAZE RISK: 2.45%) ---
    passed, t = run_phase(10000.0, 0.08, 0.0245)
    total_trades += t
    if not passed: return False, total_trades
    
    passed, t = run_phase(10000.0, 0.05, 0.0245)
    total_trades += t
    if not passed: return False, total_trades
    
    passed, t = run_phase(10000.0, 0.12, 0.0245)
    total_trades += t
    if not passed: return False, total_trades
    
    # --- PHASE 2: $200K MASTER (SNIPER RISK: 0.5%) ---
    passed, t = run_phase(200000.0, 0.08, 0.005)
    total_trades += t
    if not passed: return False, total_trades
    
    passed, t = run_phase(200000.0, 0.05, 0.005)
    total_trades += t
    if not passed: return False, total_trades
    
    # 9.225% Target on $200k = $18,450
    passed, t = run_phase(200000.0, 0.09225, 0.005)
    total_trades += t
    if not passed: return False, total_trades
    
    return True, total_trades

def main():
    print("=========================================================")
    print(f" [KESSLER V1.1] RUNNING {NUM_SIMULATIONS}x MONTE CARLO SIMULATIONS")
    print("=========================================================")
    
    successes = 0
    days_to_success = []
    
    for i in range(NUM_SIMULATIONS):
        passed, trades = simulate_full_ladder()
        if passed:
            successes += 1
            days_to_success.append(trades / TRADES_PER_DAY)
            
    win_rate = (successes / NUM_SIMULATIONS) * 100
    
    print(f"\n[*] Total Iterations: {NUM_SIMULATIONS}")
    print(f"[*] Successful Apple Bag Extractions: {successes}")
    print(f"[*] Statistical Survival Probability: {win_rate:.2f}%")
    
    if successes > 0:
        avg_days = np.mean(days_to_success)
        min_days = np.min(days_to_success)
        max_days = np.max(days_to_success)
        print(f"\n[*] Time to $23,112 (Apple Bag) Target:")
        print(f"    - Average Time: {avg_days:.1f} Trading Days")
        print(f"    - Fastest Run:  {min_days:.1f} Trading Days")
        print(f"    - Slowest Run:  {max_days:.1f} Trading Days")
        
    print("\n=========================================================")
    if win_rate > 90:
        print(" [!] MATHEMATICAL EDGE VERIFIED. CLEAR FOR DEPLOYMENT.")
    else:
        print(" [X] SURVIVAL PROBABILITY TOO LOW. ADJUST RISK PARAMETERS.")
    print("=========================================================\n")

if __name__ == "__main__":
    main()
