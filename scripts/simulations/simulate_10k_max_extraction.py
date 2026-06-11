import random
import time

def simulate_10k_max_extraction():
    print("===================================================================")
    print("      [KESSLER V9 MAXIMUM EXTRACTION STRESS TEST : MONTH 1]        ")
    print("===================================================================\n")
    print("[*] Starting Capital: $10,000 (Live Funded Account)")
    print("[*] Optimized Risk: 2.0% per trade (Fractional Kelly)")
    print("[*] Sniper Threshold: 90.0% Win Rate")
    print("[*] Risk/Reward Ratio: 1:2.0")
    print("[*] Simulating 20 Trading Days (1 Month)...\n")

    equity = 10000.0
    high_water_mark = 10000.0
    wins = 0
    losses = 0

    # 20 trading days in a month (skipping weekends/Fridays as per our rule, so maybe 16 active days)
    # Let's say the 90% threshold yields exactly 1 setup per active day.
    trading_days = 16 

    for day in range(1, trading_days + 1):
        # 2% Risk on current equity
        risk_amount = equity * 0.02 
        
        # 90% Probability
        if random.random() <= 0.90:
            profit = risk_amount * 2.0
            equity += profit
            wins += 1
            result_str = f"WIN  (+${profit:,.2f})"
        else:
            loss = risk_amount
            equity -= loss
            losses += 1
            result_str = f"LOSS (-${loss:,.2f})"
            
        if equity > high_water_mark:
            high_water_mark = equity
            
        drawdown_pct = ((high_water_mark - equity) / high_water_mark) * 100
        
        print(f"[Day {day:02d}] Engine Result: {result_str} | Current Equity: ${equity:,.2f} | Max DD: {drawdown_pct:.1f}%")
        time.sleep(0.1)

    print("\n===================================================================")
    print("                      MONTH 1 RESULTS                              ")
    print("===================================================================")
    gross_profit = equity - 10000.0
    roi = (gross_profit / 10000.0) * 100
    payout = gross_profit * 0.90 # Funding Pips 90% Split
    
    print(f"Total Trades Taken: {wins + losses}")
    print(f"Wins: {wins} | Losses: {losses}")
    print(f"Final Account Equity: ${equity:,.2f}")
    print(f"Gross Profit (ROI):   +${gross_profit:,.2f} (+{roi:.1f}%)")
    print(f"MAXIMUM CASH PAYOUT:  +${payout:,.2f} (After 90/10 Firm Split)")
    print("===================================================================")

if __name__ == "__main__":
    simulate_10k_max_extraction()
