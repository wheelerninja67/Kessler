import random

def run_stress_test(days=50000, initial_balance=10000.0):
    balance = initial_balance
    max_equity = initial_balance
    watermark = initial_balance
    
    wins = 0
    losses = 0
    blown_accounts = 0
    
    # We use the raw edge found by the grid optimizer
    base_win_rate = 0.358 # 35.8% win rate from grid optimizer
    base_reward = 3.0
def test_risk(risk_pct):
    balance = 10000.0
    max_equity = 10000.0
    watermark = 10000.0
    days = 50000
    
    wins = 0
    losses = 0
    blown_accounts = 0
    
    base_win_rate = 0.358
    base_reward = 3.0
    
    for day in range(days):
        if balance <= 0:
            blown_accounts += 1
            break
            
        daily_start_balance = balance
        risk_amount = balance * risk_pct
        
        actual_win_rate = base_win_rate - random.uniform(0.01, 0.03) 
        actual_reward = base_reward - random.uniform(0.1, 0.4)
        
        if random.random() < actual_win_rate:
            balance += risk_amount * actual_reward
            wins += 1
        else:
            actual_loss = risk_amount * random.uniform(1.0, 1.1)
            balance -= actual_loss
            losses += 1
            
        if balance > watermark:
            watermark = balance
            
        # DRACONIAN RULE #1: Max Trailing Drawdown (2.0%)
        trailing_drawdown = (watermark - balance) / watermark
        if trailing_drawdown >= 0.02:
            blown_accounts += 1
            balance = 10000.0
            watermark = 10000.0
            continue
            
        # DRACONIAN RULE #2: Max Daily Drawdown (1.5%)
        daily_drawdown = (daily_start_balance - balance) / daily_start_balance
        if daily_drawdown >= 0.015:
            blown_accounts += 1
            balance = 10000.0
            watermark = 10000.0
            continue
            
        if balance > max_equity:
            max_equity = balance

    print(f"Risk: {risk_pct*100:.2f}% | Blown Accounts: {blown_accounts:,} | Final Equity: ${balance:,.2f} | Peak: ${max_equity:,.2f}")

if __name__ == "__main__":
    print("[*] INITIATING 50,000-DAY DRACONIAN STRESS TEST")
    print("[*] Rules: 1.5% Daily Loss Limit | 2.0% Max Trailing Drawdown\n")
    for r in [0.005, 0.0025, 0.001]: # 0.5%, 0.25%, 0.1% risk
        test_risk(r)
    print("\n=========================================================\n")
