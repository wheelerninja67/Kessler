import random
import matplotlib.pyplot as plt

def run_100_dollar_stress_test():
    print("===================================================================")
    print("      [KESSLER STATISTICAL MATRIX: $100 -> 1 YEAR STRESS TEST]     ")
    print("===================================================================")
    
    initial_balance = 100.0
    balance = initial_balance
    trading_days = 252 # 1 Year
    trades_per_day_avg = 1.15
    total_trades = int(trading_days * trades_per_day_avg)
    
    # Win Rate: 58%
    # Risk/Reward: 1:3
    
    peak_balance = initial_balance
    max_drawdown_pct = 0.0
    balance_history = [initial_balance]
    
    print(f"[*] Initial Capital: ${initial_balance}")
    print(f"[*] Total Trading Days: {trading_days} (1 Year)")
    print(f"[*] Total Projected Strikes: {total_trades}")
    print(f"[*] Statistical Edge: 58% Win Rate | 1:3 Payout")
    print("-------------------------------------------------------------------")
    
    for i in range(total_trades):
        # Determine Matrix Confidence for this trade
        confidence_roll = random.random()
        
        # Uncapped Kelly Sizing for Personal $100 Account
        if confidence_roll < 0.15: 
            # Top 15% of setups: >85% Confidence
            risk_pct = 0.050 # 5% Kamikaze Risk (Allowed because no prop firm limit)
        elif confidence_roll < 0.45:
            # Next 30% of setups: 70-85% Confidence
            risk_pct = 0.030 # 3% Aggressive
        else:
            # Bottom 55% of setups: 58-70% Confidence
            risk_pct = 0.015 # 1.5% Base
            
        risk_amount = balance * risk_pct
        
        # Did the trade win? (58% chance)
        if random.random() <= 0.58:
            # WIN (1:3 Payout)
            profit = risk_amount * 3.0
            balance += profit
        else:
            # LOSS (1 R)
            balance -= risk_amount
            
        # Track Drawdown
        if balance > peak_balance:
            peak_balance = balance
        else:
            drawdown = (peak_balance - balance) / peak_balance
            if drawdown > max_drawdown_pct:
                max_drawdown_pct = drawdown
                
        balance_history.append(balance)
        
    print(f"[!] 1 YEAR SIMULATION COMPLETE")
    print(f"    > Final Balance:   ${balance:,.2f}")
    print(f"    > Net Profit:      {((balance - initial_balance) / initial_balance) * 100:,.0f}%")
    print(f"    > Max Drawdown:    {max_drawdown_pct*100:.2f}%")
    print("===================================================================")
    
if __name__ == "__main__":
    # Run 5 simulations to show variance
    for x in range(5):
        run_100_dollar_stress_test()
