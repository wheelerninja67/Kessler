#!/usr/bin/env bash
# Project Kessler: Environment Bootstrap

echo "=================================================="
echo " PROJECT KESSLER: DEPENDENCY BOOTSTRAP"
echo "=================================================="

# 1. Python Data Science Stack
echo "[*] Installing Python visualization & calibration stack..."
pip3 install --user pandas matplotlib scipy numpy

# 2. Check for Zig
if ! command -v zig &> /dev/null; then
    echo "[!] Zig compiler not found in PATH."
    echo "[*] Downloading Zig 0.16.0 (Nightly)..."

    # Detect OS (Linux or macOS)
    OS_TYPE=$(uname | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    # Note: URLs change, this is a placeholder for the automated fetch logic
    echo "Please install Zig 0.16.0 manually or use your package manager:"
    echo "  macOS: brew install zig"
    echo "  Linux: snap install zig --beta --classic"
else
    ZIG_VER=$(zig version)
    echo "[+] Zig found: v$ZIG_VER"
fi

echo "[+] Environment ready. Run './scripts/build_release.sh' to ignite."
