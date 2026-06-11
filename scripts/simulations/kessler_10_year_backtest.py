import random
import math

print("=========================================================")
print("  [KESSLER V1] 10-YEAR REAL-WORLD LIQUIDITY SIMULATION   ")
print("=========================================================")

initial_capital = 25.0
equity = initial_capital
peak_equity = equity
max_drawdown_pct = 0.0

# Market Physics
trades_per_day = 5
total_trades = trades_per_day * 365 * 10
win_rate = 0.58
reward_to_risk = 2.0

# Worse Than Real Life Conditions
flash_crash_probability = 0.05
veto_success_rate = 0.90
base_slippage_penalty = 1.2

# ---------------------------------------------------------
# THE REAL-WORLD LIQUIDITY LIMITS
# ---------------------------------------------------------
# You cannot risk more than $5 Million on a single 5-minute candle without causing a massive flash crash yourself.
MAX_RISK_PER_TRADE = 5000000.0 

# Fractional Kelly
kelly_pct = min((win_rate - ((1 - win_rate) / reward_to_risk)) * 0.5, 0.03)

print(f"[*] Starting Capital: ${initial_capital:.2f}")
print(f"[*] Total Trades: {total_trades}")
print(f"[*] Hard Ceiling Risk Cap: $5,000,000 per trade")
print("---------------------------------------------------------")

for i in range(total_trades):
    if equity <= 5.0:
        print(f"[FATAL] Account blown at Trade #{i}")
        break
        
    # Calculate geometric risk, but CAP it at the liquidity limit
    theoretical_risk = equity * kelly_pct
    risk_amount = min(theoretical_risk, MAX_RISK_PER_TRADE)
    
    # As position size approaches the max limit, the broker slippage penalty increases exponentially
    # (e.g. Trying to fill a $5M order will suffer much worse spread than a $50 order)
    liquidity_drag = 1.0 + (risk_amount / MAX_RISK_PER_TRADE) * 0.5 
    current_slippage = base_slippage_penalty * liquidity_drag
    
    if random.random() < flash_crash_probability:
        if random.random() < veto_success_rate:
            continue
        else:
            loss = risk_amount * 5.0 * current_slippage
            equity -= loss
    else:
        if random.random() < win_rate:
            # Reward is also dragged down by liquidity (moving the market against yourself)
            profit = (risk_amount * reward_to_risk) / liquidity_drag
            equity += profit
        else:
            loss = risk_amount * current_slippage
            equity -= loss
            
    if equity > peak_equity:
        peak_equity = equity
    else:
        dd = (peak_equity - equity) / peak_equity
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd

print(f"[*] Simulation Complete.")
print("=========================================================")
print(f"Final Capital:   ${equity:,.2f}")
print(f"Peak Capital:    ${peak_equity:,.2f}")
print(f"Max Drawdown:    {max_drawdown_pct*100:.2f}%")
print("=========================================================")
