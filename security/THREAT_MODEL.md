# KESSLER THREAT MODEL

## 1. Non-Deterministic Drift (The "Phantom Bug")
- **Threat:** OS-level thread scheduling or memory allocator fragmentation causes the same seed to produce different outcomes, rendering the oracle useless.
- **Mitigation:** Zero heap allocations in the `pulse.zig` tick loop. Strict sequential aggregation of `mail.zig` lock-free queues. Bypassing `libc` malloc in favor of the `stash.zig` Arena.

## 2. Configuration Poisoning
- **Threat:** A bad actor alters a YAML scenario file to artificially suppress contagion depth to pass a stress test.
- **Mitigation:** The `diary.zig` telemetry output automatically embeds the SHA-256 hash of the ingested configuration file into the header of the CSV. If the hash doesn't match the baseline, the run is flagged as tainted.

## 3. Side-Channel Attacks
- **Threat:** Monitoring CPU power draw or cache misses to deduce the exact interbank topology of the simulation.
- **Mitigation:** Struct of Arrays (SoA) layout ensures deterministic memory access patterns regardless of agent state. The loop executes in constant time (O(N) per tick) regardless of how many agents default.
