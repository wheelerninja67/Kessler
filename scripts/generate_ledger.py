import csv
import random
from datetime import datetime, timedelta
import os

def generate_track_record():
    desktop_path = os.path.expanduser("~/Desktop/Kessler_V9_Simulated_Track_Record.csv")
    
    # Create Desktop dir if it doesn't exist just in case
    os.makedirs(os.path.dirname(desktop_path), exist_ok=True)

    balance = 10000.0
    trades = []

    # Start date a month ago
    current_date = datetime(2026, 5, 1, 8, 15) 

    for i in range(1, 35): # 34 trades to show a solid history
        # Skip weekends (Prop firm rule)
        while current_date.weekday() >= 4: # Skip Friday and Weekends to simulate the Kill-Switch
            current_date += timedelta(days=1)
            
        risk_amount = balance * 0.02
        is_win = random.random() < 0.90
        trade_type = random.choice(["BUY", "SELL"])
        
        # Fake entry price for Gold in 2026
        entry_price = round(random.uniform(2350.0, 2450.0), 2)
        
        # Calculate volume based on $3 stop loss distance
        volume = round(risk_amount / 300.0, 2)
        if volume < 0.01: volume = 0.01
        
        if is_win:
            profit = risk_amount * 2.0
            balance += profit
            exit_price = entry_price + 6.0 if trade_type == "BUY" else entry_price - 6.0
            pnl = profit
        else:
            loss = risk_amount
            balance -= loss
            exit_price = entry_price - 3.0 if trade_type == "BUY" else entry_price + 3.0
            pnl = -loss
            
        trades.append({
            "Ticket": 849200 + i,
            "Open Time": current_date.strftime("%Y.%m.%d %H:%M:%S"),
            "Close Time": (current_date + timedelta(minutes=random.randint(15, 120))).strftime("%Y.%m.%d %H:%M:%S"),
            "Symbol": "XAUUSD",
            "Type": trade_type,
            "Volume": f"{volume:.2f}",
            "Open Price": f"{entry_price:.2f}",
            "S/L": f"{(entry_price - 3.0 if trade_type == 'BUY' else entry_price + 3.0):.2f}",
            "T/P": f"{(entry_price + 6.0 if trade_type == 'BUY' else entry_price - 6.0):.2f}",
            "Close Price": f"{exit_price:.2f}",
            "Commission": "-$0.00",
            "Swap": "$0.00",
            "Profit": f"{pnl:.2f}",
            "Balance": f"{balance:.2f}"
        })
        
        # Advance time to next setup
        current_date += timedelta(hours=random.randint(6, 48))

    with open(desktop_path, "w", newline="") as f:
        fieldnames = ["Ticket", "Open Time", "Close Time", "Symbol", "Type", "Volume", "Open Price", "S/L", "T/P", "Close Price", "Commission", "Swap", "Profit", "Balance"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trades)

    print(f"[*] Successfully generated MT5 format track record at: {desktop_path}")

if __name__ == "__main__":
    generate_track_record()
