#!/bin/bash
echo "[*] INITIATING KESSLER V1.1 ULTIMATE DEPLOYMENT SEQUENCE"
echo "[*] Target Timeline: 2.3 Months (52-Day MacBook Ladder)"
echo "[*] Risk Parameters: 2.5% Kamikaze Mode"
echo "[*] AI Volume Filter: ONLINE"

# Loop to ensure the engine is unkillable
while true; do
    echo "[!] Launching Kessler Engine..."
    
    # Run the engine via wine python
    WINEPREFIX=~/.wine_mt5 wine python scripts/kessler_v1_1_engine.py
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[X] Kessler Engine crashed or disconnected. Restarting in 10 seconds..."
        sleep 10
    else
        echo "[+] Kessler Engine completed execution cleanly. Sleeping until next NY Session..."
        # If it exited cleanly (e.g., end of trading day), sleep for a while before restarting
        sleep 3600
    fi
done
