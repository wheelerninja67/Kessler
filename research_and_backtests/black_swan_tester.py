import random

def run_black_swan_test(days=10000, risk_pct=0.005, trailing_sl=False):
    balance = 10000.0
    watermark = 10000.0
    
    wins = 0
    losses = 0
    black_swans_hit = 0
    blown_accounts = 0
    
    base_win_rate = 0.358 
    
    for day in range(days):
        if balance <= 0:
            blown_accounts += 1
            break
            
        daily_start_balance = balance
        risk_amount = balance * risk_pct
        
        # In a trailing SL system, win rate usually goes down but R/R expands massively when it catches a trend.
        if trailing_sl:
            actual_win_rate = base_win_rate - 0.10 # 25.8% win rate
            actual_reward = random.uniform(2.0, 10.0) # Reward can be massive (2R to 10R)
        else:
            actual_win_rate = base_win_rate - random.uniform(0.01, 0.03) 
            actual_reward = 3.0 - random.uniform(0.1, 0.4)
        
        # BLACK SWAN EVENT: 1 in 500 chance of massive institutional gap (NFP / CPI spike)
        is_black_swan = random.randint(1, 500) == 1
        
        if random.random() < actual_win_rate:
            balance += risk_amount * actual_reward
            wins += 1
        else:
            if is_black_swan:
                # Black Swan Slippage: Stop Loss is completely skipped. You lose 5x to 10x your risk.
                actual_loss = risk_amount * random.uniform(5.0, 10.0)
                black_swans_hit += 1
            else:
                actual_loss = risk_amount * random.uniform(1.0, 1.1)
                
            balance -= actual_loss
            losses += 1
            
        if balance > watermark:
            watermark = balance
            
        # 6% Max Trailing Drawdown
        if (watermark - balance) / watermark >= 0.06:
            blown_accounts += 1
            balance = 10000.0
            watermark = 10000.0
            continue
            
        # 3% Max Daily Drawdown
        if (daily_start_balance - balance) / daily_start_balance >= 0.03:
            blown_accounts += 1
            balance = 10000.0
            watermark = 10000.0
            continue

    return blown_accounts, balance, black_swans_hit

if __name__ == "__main__":
    print("[*] INITIATING BLACK SWAN STRESS TESTS (10,000 Days | 6% Max DD | 3% Daily DD)")
    print("\n--- TEST 1: Fixed 1:3 R/R with Black Swan Injections ---")
    blown, final_bal, swans = run_black_swan_test(10000, 0.005, trailing_sl=False)
    print(f"Risk: 0.5% | Black Swans Survived: {swans} | Accounts Blown: {blown} | Final Equity: ${final_bal:,.2f}")
    
    print("\n--- TEST 2: Trailing Stop-Loss (Infinite R/R) with Black Swan Injections ---")
    blown2, final_bal2, swans2 = run_black_swan_test(10000, 0.005, trailing_sl=True)
    print(f"Risk: 0.5% | Black Swans Survived: {swans2} | Accounts Blown: {blown2} | Final Equity: ${final_bal2:,.2f}")
    
    print("\n=========================================================\n")
