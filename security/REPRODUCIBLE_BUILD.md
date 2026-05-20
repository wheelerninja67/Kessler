# VERIFYING THE ORACLE

Project Kessler guarantees bit-for-bit reproducible builds. 

To verify that the binary you are running has not been tampered with:
1. Clone the repository.
2. Run `scripts/build_release.sh`.
3. Hash the output: `sha256sum zig-out/bin/kessler`.
4. Compare this hash against the signed release manifest in `.github/releases`.

If the hashes differ, the compiler environment has been compromised. **Do not trust the telemetry.**
