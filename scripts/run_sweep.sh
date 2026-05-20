#!/usr/bin/env bash
# Project Kessler: Monte Carlo Parameter Sweep
# Scours random seeds to find maximum contagion events.

ITERATIONS=100
CRITICAL_THRESHOLD=500 # Alert if defaults exceed this

echo "=================================================="
echo " INITIATING KESSLER SWEEP: $ITERATIONS ITERATIONS"
echo "=================================================="

mkdir -p output/sweep_results
echo "Seed,Max_Defaults,Cascade_Depth" > output/sweep_results/summary.csv

# Ensure optimized build
zig build -Doptimize=ReleaseFast

for i in $(seq 1 $ITERATIONS); do
    # Generate a random 6-digit seed
    SEED=$(od -An -N4 -tu4 < /dev/urandom | tr -d ' ')

    echo -n "[*] Running Seed: $SEED... "

    # Run the engine, grab the final stats using tail and awk
    ./zig-out/bin/kessler --seed "$SEED" > output/sweep_results/run_${SEED}.log

    # Extract the final defaults from the log (assuming standard diary output)
    FINAL_DEFAULTS=$(grep "DEFAULTS" output/sweep_results/run_${SEED}.log | tail -n 1 | awk '{print $7}')

    echo "Defaults: $FINAL_DEFAULTS"

    # Log to summary
    echo "$SEED,$FINAL_DEFAULTS,N/A" >> output/sweep_results/summary.csv

    if [ "$FINAL_DEFAULTS" -gt "$CRITICAL_THRESHOLD" ]; then
        echo "   [!] CRITICAL PHASE TRANSITION DETECTED (Seed: $SEED)"
        # Save the specific bad run for visual analysis later
        cp kessler_telemetry.csv output/sweep_results/CRITICAL_${SEED}.csv 2>/dev/null
    fi
done

echo "[+] Sweep complete. Summary saved to output/sweep_results/summary.csv"
