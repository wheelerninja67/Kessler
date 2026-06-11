import random
import time

def simulate_month(account_size, win_rate=0.90, risk=0.02, rr=2.0, days=16):
    equity = account_size
    wins = 0
    losses = 0
    
    for _ in range(days):
        risk_amount = equity * risk
        if random.random() <= win_rate:
            equity += (risk_amount * rr)
            wins += 1
        else:
            equity -= risk_amount
            losses += 1
            
    gross_profit = equity - account_size
    payout = gross_profit * 0.90 if gross_profit > 0 else 0
    return gross_profit, payout

def run_geometric_scaling():
    print("===================================================================")
    print("      [KESSLER V9: 90-DAY GEOMETRIC SCALING (JUNE - AUG 2026)]     ")
    print("===================================================================\n")
    
    total_bank_balance = 0.0
    
    # MONTH 1: JUNE
    print("[*] MONTH 1: JUNE (The $10k Bootstrap)")
    print("    - Vehicle: $10,000 Funding Pips Account")
    print("    - Initial Cost: $44 (₹4,600)")
    gross, payout = simulate_month(10000.0)
    total_bank_balance += payout
    print(f"    -> Gross Profit: +${gross:,.2f}")
    print(f"    -> Payout (90%): +${payout:,.2f}")
    print(f"    [BANK BALANCE]:  ${total_bank_balance:,.2f}\n")
    time.sleep(0.5)
    
    # Upgrade
    cost_100k = 399.0
    print(f"[!] UPGRADE TRIGGERED: Buying $100,000 Challenge for ${cost_100k}")
    total_bank_balance -= cost_100k
    print(f"    [BANK BALANCE]:  ${total_bank_balance:,.2f}\n")
    time.sleep(0.5)

    # MONTH 2: JULY
    print("[*] MONTH 2: JULY (The $100k Sovereign Scale)")
    print("    - Vehicle: $100,000 Funding Pips Account")
    print("    - Assuming challenge passed in background. Executing funded stage.")
    gross, payout = simulate_month(100000.0)
    total_bank_balance += payout
    print(f"    -> Gross Profit: +${gross:,.2f}")
    print(f"    -> Payout (90%): +${payout:,.2f}")
    print(f"    [BANK BALANCE]:  ${total_bank_balance:,.2f}\n")
    time.sleep(0.5)
    
    # Upgrade
    cost_300k = 998.0
    print(f"[!] UPGRADE TRIGGERED: Buying Max $300,000 PRIME Allocation for ${cost_300k}")
    total_bank_balance -= cost_300k
    print(f"    [BANK BALANCE]:  ${total_bank_balance:,.2f}\n")
    time.sleep(0.5)

    # MONTH 3: AUGUST
    print("[*] MONTH 3: AUGUST (The Ceiling Extraction)")
    print("    - Vehicle: $300,000 Funding Pips PRIME Account")
    print("    - Maximum Prop Firm Scale Reached. Commencing heavy extraction.")
    gross, payout = simulate_month(300000.0)
    total_bank_balance += payout
    print(f"    -> Gross Profit: +${gross:,.2f}")
    print(f"    -> Payout (90%): +${payout:,.2f}")
    print(f"    [BANK BALANCE]:  ${total_bank_balance:,.2f}\n")
    
    print("===================================================================")
    print("                      90-DAY ROADMAP RESULTS                       ")
    print("===================================================================")
    print(f"Total Initial Investment: $44.00 (₹4,600)")
    print(f"Total Liquid Cash in Bank: ${total_bank_balance:,.2f}")
    
    if total_bank_balance > 15000:
        print("[!] SUFFICIENT CAPITAL REACHED TO PURCHASE LENOVO THINKSTATION P8")
        print("[!] INITIATING PHASE 2: CRYPTO HFT PIVOT PREPARATION...")
    print("===================================================================")

if __name__ == "__main__":
    run_geometric_scaling()
