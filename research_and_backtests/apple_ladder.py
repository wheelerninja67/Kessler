import random
import time
import sys

def print_slow(text, delay=0.02):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def simulate_apple_ladder():
    print_slow("\n=========================================================")
    print_slow(" [KESSLER MD] THE APPLE LOADOUT LADDER SIMULATOR ")
    print_slow("=========================================================\n")
    print_slow("[*] Target Acquisition: The ₹12,82,200 Apple Bag")
    print_slow("[*] Exchange Rate: $1 USD = ₹83.00 INR")
    print_slow("[*] Ultimate Target: $15,450 USD in Withdrawable Profits\n")
    
    print_slow("[*] Ingesting Kessler V1.1 ULTIMATE Parameters...")
    print_slow("  > Edge: 4-Hour Momentum Breakout (200 EMA Filter)")
    print_slow("  > Win Rate: 33.3%")
    print_slow("  > Risk/Reward: 1:3")
    print_slow("  > Risk Per Trade: 1.5% (Aggressive Compounding)")
    print_slow("  > Execution Velocity: Lever 2 (Avg 1.15 Trades/Day)\n")
    
    base_win_rate = 0.333
    reward = 3.0
    risk_pct = 0.015
    trades_per_day = 1.15
    
    trades_passed = 0
    
    # ---------------------------------------------------------
    # PHASE 1: $10k EVALUATION
    # ---------------------------------------------------------
    balance = 10000.0
    target = 10800.0
    print_slow(">>> STAGE 1: $10,000 Funding Pips Evaluation (8% Target)")
    while balance < target:
        trades_passed += 1
        if random.random() < base_win_rate: balance += (balance * risk_pct * reward)
        else: balance -= (balance * risk_pct)
    print_slow(f"[+] Passed Phase 1 in {int(trades_passed / trades_per_day)} days.")
    
    target = 10500.0
    balance = 10000.0 # reset for phase 2
    trades_this_phase = 0
    while balance < target:
        trades_passed += 1
        trades_this_phase += 1
        if random.random() < base_win_rate: balance += (balance * risk_pct * reward)
        else: balance -= (balance * risk_pct)
    print_slow(f"[+] Passed Phase 2 in {int(trades_this_phase / trades_per_day)} days. TOTAL DAYS: {int(trades_passed / trades_per_day)}")
    print_slow("[!] $10,000 FUNDED ACCOUNT UNLOCKED.\n")
    time.sleep(1)
    
    # ---------------------------------------------------------
    # PHASE 2: GRINDING THE $100K CHALLENGE FEE ($399) + BUFFER
    # ---------------------------------------------------------
    balance = 10000.0
    target = 11000.0 # Need $1000 profit (80% split = $800, enough for $100k challenge)
    trades_this_phase = 0
    print_slow(">>> STAGE 2: Compounding $10k Live for the $100k Master Challenge ($399 fee)")
    while balance < target:
        trades_passed += 1
        trades_this_phase += 1
        if random.random() < base_win_rate: balance += (balance * risk_pct * reward)
        else: balance -= (balance * risk_pct)
    print_slow(f"[+] Banked $1,000 profit in {int(trades_this_phase / trades_per_day)} days. TOTAL DAYS: {int(trades_passed / trades_per_day)}")
    print_slow("[!] WITHDRAWAL SUCCESS. BUYING $100,000 CHALLENGE.\n")
    time.sleep(1)
    
    # ---------------------------------------------------------
    # PHASE 3: $100k EVALUATION
    # ---------------------------------------------------------
    balance = 100000.0
    target = 108000.0
    trades_this_phase = 0
    print_slow(">>> STAGE 3: $100,000 Funding Pips Evaluation")
    while balance < target:
        trades_passed += 1
        trades_this_phase += 1
        if random.random() < base_win_rate: balance += (balance * risk_pct * reward)
        else: balance -= (balance * risk_pct)
    print_slow(f"[+] Passed $100k Phase 1 in {int(trades_this_phase / trades_per_day)} days.")
    
    target = 105000.0
    balance = 100000.0 
    trades_this_phase = 0
    while balance < target:
        trades_passed += 1
        trades_this_phase += 1
        if random.random() < base_win_rate: balance += (balance * risk_pct * reward)
        else: balance -= (balance * risk_pct)
    print_slow(f"[+] Passed $100k Phase 2 in {int(trades_this_phase / trades_per_day)} days. TOTAL DAYS: {int(trades_passed / trades_per_day)}")
    print_slow("[!!!] $100,000 MASTER FUNDED ACCOUNT UNLOCKED.\n")
    time.sleep(1)
    
    # ---------------------------------------------------------
    # PHASE 4: THE ₹12.9 LAKH MACBOOK & APPLE WATCH ULTRA RUN
    # ---------------------------------------------------------
    balance = 100000.0
    # To get $15,450 withdrawable post-split (80%), we need $19,312 gross profit.
    target = 119312.0 
    trades_this_phase = 0
    print_slow(">>> STAGE 4: The Final Push for the ₹12,82,200 Apple Bag")
    
    while balance < target:
        trades_passed += 1
        trades_this_phase += 1
        if random.random() < base_win_rate: balance += (balance * risk_pct * reward)
        else: balance -= (balance * risk_pct)
        
    total_days = int(trades_passed / trades_per_day)
    print_slow(f"[+] Target Hit! Gross Profit: ${balance - 100000.0:,.2f} in {int(trades_this_phase / trades_per_day)} days.")
    print_slow("[!] FINAL WITHDRAWAL SECURED.\n")
    
    print_slow("=========================================================")
    print_slow(" [KESSLER MD] TIMELINE REPORT ")
    print_slow("=========================================================")
    print_slow(f"Total Trading Days Required: {total_days}")
    months = total_days / 21 # 21 trading days in a month
    print_slow(f"Total Calendar Time: ~{months:.1f} Months")
    print_slow(f"End Result: 14-inch M5 Max Space Black MacBook Pro, iPhone 17 Pro Max,")
    print_slow(f"Apple Watch Ultra 3, AirPods Max 2 fully paid in cash.")
    print_slow("=========================================================\n")

if __name__ == "__main__":
    simulate_apple_ladder()
