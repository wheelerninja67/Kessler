#!/usr/bin/env bash
# Project Kessler: Air-Gap Packaging Routine

VERSION="v0.4.0"
BOX_NAME="kessler_box_${VERSION}_$(uname -m)"

echo "[*] Packaging $BOX_NAME for secure deployment..."

# 1. Build the release binary
./scripts/build_release.sh

# 2. Create staging directory
mkdir -p "$BOX_NAME/bin"
mkdir -p "$BOX_NAME/config/scenarios"

# 3. Move critical assets
cp zig-out/bin/kessler "$BOX_NAME/bin/"
cp config/*.yaml "$BOX_NAME/config/" 2>/dev/null
cp config/scenarios/*.yaml "$BOX_NAME/config/scenarios/" 2>/dev/null
cp docs/SECURITY.md "$BOX_NAME/"

# 4. Generate SHA256 Hash for the binary (Proof of Integrity)
if command -v sha256sum &> /dev/null; then
    HASH=$(sha256sum "$BOX_NAME/bin/kessler" | awk '{print $1}')
else
    HASH=$(shasum -a 256 "$BOX_NAME/bin/kessler" | awk '{print $1}')
fi

echo "$HASH  bin/kessler" > "$BOX_NAME/checksum.sha256"

# 5. Compress
tar -czvf "${BOX_NAME}.tar.gz" "$BOX_NAME"

echo "=================================================="
echo "[+] KESSLER BOX SECURED: ${BOX_NAME}.tar.gz"
echo "    BINARY HASH: $HASH"
echo "    Ready for air-gapped institutional transfer."
echo "=================================================="
