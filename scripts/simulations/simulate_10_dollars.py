import random
import time

def simulate_10_dollar_pure_compounding():
    print("===================================================================")
    print("      [KESSLER PURE GEOMETRIC EXPERIMENT : $10 STARTING CAPITAL]    ")
    print("===================================================================\n")
    
    # Starting conditions
    funded_equity = 10.0 # Literally $10
    
    # 9 Month Timeline
    months = 9
    
    for month in range(1, months + 1):
        print(f"--- MONTH {month} ---")
        
        monthly_profit = 0
        for week in range(4):
            for trade in range(3): # 3 trades a week
                risk_amount = funded_equity * 0.15 # Higher risk tolerance (15%) because it's only $10
                
                # Introduce realistic market variance
                if month == 4 or month == 7:
                    win_prob = 0.40 # Macro drawdown
                else:
                    win_prob = 0.65 # Normal Edge
                    
                if random.random() <= win_prob:
                    profit = risk_amount * 2 # 1:2 RR
                    funded_equity += profit
                    monthly_profit += profit
                else:
                    funded_equity -= risk_amount
                    monthly_profit -= risk_amount

        if monthly_profit > 0:
            print(f"[*] Engine Performance: +${monthly_profit:,.2f}")
        else:
            print(f"[!] Engine Drawdown: ${monthly_profit:,.2f}")
            
        print(f"[*] Total Account Equity: ${funded_equity:,.2f}\n")
        time.sleep(0.3)

    print("===================================================================")
    print("                      SIMULATION COMPLETE                          ")
    print(f"FINAL EQUITY FROM $10 (Age 16.5): ${funded_equity:,.2f}")
    print("===================================================================")

if __name__ == "__main__":
    simulate_10_dollar_pure_compounding()
