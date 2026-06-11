import os
import csv
import ctypes

def main():
    print("=========================================================")
    print("[*] KESSLER V3: BACKPROPAGATION ENGINE ENGAGED")
    print("=========================================================")
    
    # Load C FFI
    try:
        kessler_ai = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "..", "libkessler.so"))
        kessler_ai.init_kessler_ai()
        kessler_ai.train_kessler_ai.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_uint8]
        kessler_ai.train_kessler_ai.restype = None
        print("[*] C-Shared Library loaded. Memory Matrix Online.")
    except Exception as e:
        print(f"[!] FFI Load Error: {e}")
        return

    journal_path = os.path.join(os.path.dirname(__file__), "..", "logs", "trade_journal.csv")
    
    if not os.path.exists(journal_path):
        print("[!] No trade journal found. Cannot train.")
        return
        
    print(f"[*] Reading memory banks: {journal_path}")
    
    trades = []
    with open(journal_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trades.append(row)
            
    if len(trades) < 2:
        print("[!] Not enough trades to calculate mathematical gradients. Let the engine run longer.")
        return
        
    print(f"[*] Analyzing {len(trades)} execution vectors...")
    
    # ---------------------------------------------------------
    # SUPERVISED HINDSIGHT TRAINING LOOP
    # ---------------------------------------------------------
    # We iterate through history. We look at Trade N, and then peek at Trade N+1.
    # If the price went UP at N+1, the purely mathematical correct choice at N was BUY (1).
    # If the price went DOWN at N+1, the correct choice at N was SELL (2).
    # We push this data into the Zig backend to compute the exact Cross-Entropy loss 
    # and backpropagate the gradients through the Matrix.
    
    epochs = 100 # Multi-pass optimization
    print(f"[*] Executing SGD Backpropagation across {epochs} Epochs...")
    
    for epoch in range(epochs):
        for i in range(len(trades) - 1):
            current_trade = trades[i]
            next_trade = trades[i+1]
            
            try:
                current_price = float(current_trade["Price"])
                next_price = float(next_trade["Price"])
            except ValueError:
                continue
                
            spread = 0.00002 # Standard 2 pipette simulated spread
            
            # Pure Physics Optimal Mapping
            if next_price > current_price:
                target_action = 1 # BUY
            elif next_price < current_price:
                target_action = 2 # SELL
            else:
                target_action = 0 # HOLD
                
            # Fire the Zig C-Engine
            kessler_ai.train_kessler_ai(current_price, spread, target_action)
            
    print(f"\\n[*] BACKPROPAGATION COMPLETE.")
    print(f"[*] Neural weights successfully updated via Stochastic Gradient Descent.")
    print(f"[*] The Kessler Brain is now mathematically smarter.")

if __name__ == "__main__":
    main()
