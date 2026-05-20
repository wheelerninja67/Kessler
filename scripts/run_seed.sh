#!/usr/bin/env bash
# Project Kessler: Deterministic Execution Wrapper

if [ -z "$1" ]; then
    echo "Usage: ./run_seed.sh <SEED_NUMBER>"
    echo "Example: ./run_seed.sh 42"
    exit 1
fi

SEED=$1
OUT_DIR="output/seed_${SEED}"
mkdir -p "$OUT_DIR"

echo "=================================================="
echo " IGNITING PROJECT KESSLER | SEED: $SEED"
echo "=================================================="

# 1. Compile the optimized release binary if it doesn't exist
if [ ! -f "zig-out/bin/kessler" ]; then
    echo "[*] Building bare-metal release binary..."
    zig build -Doptimize=ReleaseFast
fi

# 2. Run the simulation, pass the seed, pipe output to log
echo "[*] Executing Gai-Kapadia Tick Loop..."
./zig-out/bin/kessler --seed "$SEED" > "${OUT_DIR}/terminal_stdout.log"

# Assume the Zig binary dumps to 'kessler_telemetry.csv' by default
if [ -f "kessler_telemetry.csv" ]; then
    mv kessler_telemetry.csv "${OUT_DIR}/"
    echo "[+] Telemetry secured."

    # 3. Trigger the Python visualizer
    echo "[*] Generating dashboard..."
    python3 scripts/visualize.py "${OUT_DIR}/kessler_telemetry.csv"
else
    echo "[!] ERROR: Telemetry CSV not found. Did the engine crash?"
fi

echo "[+] Simulation Complete. Artifacts saved to: ${OUT_DIR}/"
