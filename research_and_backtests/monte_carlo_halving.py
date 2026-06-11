import random

def run_simulation(years, initial_balance):
    trades_per_year = 80 # Assuming 80 high-probability sweeps per year
    total_trades = int(years * trades_per_year)
    
    balance = initial_balance
    max_balance = initial_balance
    max_drawdown = 0.0
    wins = 0
    losses = 0
    
    win_rate = 0.40 # 40% win rate
    risk_pct = 0.025 # 2.5% risk
    reward_pct = 0.050 # 5.0% reward (1:2 R/R)
    
    for _ in range(total_trades):
        if balance <= 100: # Liquidated
            break
            
        # Hard cap position sizing at $1,000,000 risk to simulate liquidity constraints
        risk_amount = min(balance * risk_pct, 1000000.0) 
        
        if random.random() < win_rate:
            balance += risk_amount * 2.0
            wins += 1
        else:
            balance -= risk_amount
            losses += 1
            
        if balance > max_balance:
            max_balance = balance
        
        drawdown = (max_balance - balance) / max_balance
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            
    return {
        "years": years,
        "trades": total_trades,
        "final_balance": balance,
        "max_drawdown": max_drawdown * 100,
        "wins": wins,
        "losses": losses
    }

def main():
    halvings = [100.0, 50.0, 25.0, 12.5, 6.25, 3.125, 1.5625, 0.78125, 0.390625, 0.1953125, 0.09765625]
    initial = 10750.0 # 9 Lakh INR
    
    print("=========================================================")
    print("   [KESSLER] MONTE CARLO FRACTIONAL KELLY HALVING        ")
    print("=========================================================")
    for y in halvings:
        res = run_simulation(y, initial)
        print(f"[{y:7.3f} Years] Trades: {res['trades']:4d} | Final Equity: ${res['final_balance']:15,.2f} | Max DD: {res['max_drawdown']:5.1f}% | W: {res['wins']} L: {res['losses']}")
    print("=========================================================")

if __name__ == "__main__":
    main()
