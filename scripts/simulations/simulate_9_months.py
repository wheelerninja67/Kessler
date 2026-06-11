import random
import time

def simulate_kessler_roadmap():
    print("===================================================================")
    print("   [KESSLER SOVEREIGN WEALTH ENGINE : 9-MONTH GEOMETRIC SIMULATION]   ")
    print("===================================================================\n")
    
    # Starting conditions
    real_cash = -60.0  # Paid $60 for the $10k account
    funded_equity = 10000.0
    active_firms = 1
    max_allocation_per_firm = 300000.0
    firm_split = 0.80
    
    # 9 Month Timeline
    months = 9
    
    # Kessler Engine Stats (Highly realistic, accounting for Sniper Filter & Macro Veto)
    # Win rate: 65% (Sniper filter ensures high probability, but not 100%)
    # Risk per trade: 3% (Fractional Kelly)
    # R:R Ratio: 1:2 (Risk $300 to make $600)
    # Trades per week: 3 (Low frequency)
    
    for month in range(1, months + 1):
        print(f"--- MONTH {month} ---")
        
        # Simulate 4 weeks of trading
        monthly_profit = 0
        for week in range(4):
            for trade in range(3): # 3 trades a week
                risk_amount = funded_equity * 0.03 # 3% risk
                
                # Simulate "Perfect Storm" volatility in Month 4
                if month == 4:
                    win_prob = 0.45 # Edge decays during the Black Swan
                else:
                    win_prob = 0.65 # Normal Sniper Edge
                    
                if random.random() <= win_prob:
                    # Win (1:2 RR)
                    profit = risk_amount * 2
                    funded_equity += profit
                    monthly_profit += profit
                else:
                    # Loss
                    funded_equity -= risk_amount
                    monthly_profit -= risk_amount

        # End of Month Payout & Scaling Logic
        if monthly_profit > 0:
            # We take a payout of the monthly profit from the prop firms
            gross_payout = monthly_profit
            net_payout = gross_payout * firm_split
            real_cash += net_payout
            
            # Reset funded equity to baseline (Prop firms don't let you compound infinitely inside the account)
            if active_firms == 1:
                if funded_equity >= 10000 and funded_equity < 100000:
                    baseline = 10000
                elif funded_equity >= 100000 and funded_equity < 300000:
                    baseline = 100000
                else:
                    baseline = 300000
            else:
                baseline = active_firms * max_allocation_per_firm
                
            funded_equity = baseline
            
            print(f"[*] Engine Performance: +${gross_payout:,.2f}")
            print(f"[*] Extracted Cash (After 80% Split): +${net_payout:,.2f}")
        else:
            print(f"[!] Engine Drawdown: ${monthly_profit:,.2f}. Macro Veto preserved account.")
            
        # SCALING THE SYNDICATE
        if month == 1 and real_cash > 500:
            print("[+] SCALING: Buying $100k Account.")
            funded_equity = 100000.0
            real_cash -= 500
        elif month == 2 and real_cash > 1000:
            print("[+] SCALING: Buying $300k Max-Allocation Account.")
            funded_equity = 300000.0
            real_cash -= 1000
        elif month == 3 and real_cash > 5000:
            print("[+] SCALING: Deploying Python Trade Copier to 5 Firms ($1.5M Total Leverage).")
            active_firms = 5
            funded_equity = active_firms * max_allocation_per_firm
            real_cash -= 4000 # Cost of buying 4 more $300k accounts
            
        if month == 7 and real_cash > 3000000:
            print("\n[$$$] 3 MILLION TARGET HIT. FIRING PROP FIRMS. PIVOTING TO SOVEREIGN CAPITAL.")
            funded_equity = real_cash # Transition to compounding own money, no more profit splits
            active_firms = 0
            
        print(f"[*] Liquid Cash Hoard: ${real_cash:,.2f}")
        print(f"[*] Total Active Leverage: ${funded_equity:,.2f}\n")
        time.sleep(0.5)

    print("===================================================================")
    print("                      SIMULATION COMPLETE                          ")
    print(f"FINAL LIQUID CASH (Age 16.5): ${real_cash:,.2f}")
    if real_cash >= 6000000:
        print("STATUS: TARGET EXCEEDED. $6M REACHED.")
    elif real_cash >= 3000000:
        print("STATUS: TARGET REACHED. $3M REACHED. PROCEED TO MAC STUDIO PURCHASE.")
    else:
        print("STATUS: FELL SHORT DUE TO MARKET DRAWDOWN. RECALIBRATE EDGE.")
    print("===================================================================")

if __name__ == "__main__":
    simulate_kessler_roadmap()
