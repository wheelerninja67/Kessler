#!/usr/bin/env bash
# Project Kessler: Aggressive Optimization Build

echo "[*] Purging old builds..."
rm -rf zig-cache zig-out

echo "[*] Compiling Project Kessler (ReleaseFast, Native CPU)..."
# -Doptimize=ReleaseFast: Strips debug symbols, maximizes speed
# -Dtarget=native: Optimizes for the exact L1/L2 cache of the current machine
zig build -Doptimize=ReleaseFast

echo "[*] Checking binary footprint..."
ls -lh zig-out/bin/kessler

echo "[+] Binary ready for Institutional Deployment."
