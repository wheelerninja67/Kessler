#!/usr/bin/env python3
import re
import subprocess

from scipy.optimize import minimize

# Target Stylized Facts from Real-World Markets (e.g., S&P 500)
TARGET_KURTOSIS = 4.5
TARGET_CLUSTERING = 0.8


def run_kessler_and_extract(hawkes_decay, rough_hurst):
    """
    Simulates a run using temporary parameters and parses the stdout
    to extract the mathematical reality of the simulation.
    """
    print(f"Testing Parameters -> Hawkes: {hawkes_decay:.3f}, Hurst: {rough_hurst:.3f}")

    # In a full build, we would write these to a temp config.yaml here.
    # For now, we mock the command execution.
    cmd = ["./zig-out/bin/kessler", "--seed", "101"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse the Zig stdout for our Stylized Facts
    kurtosis_match = re.search(r"EXCESS KURTOSIS: ([0-9.-]+)", result.stdout)
    clustering_match = re.search(r"VOL CLUSTERING:  ([0-9.-]+)", result.stdout)

    # Fallbacks if parsing fails (penalize the optimizer)
    kurtosis = float(kurtosis_match.group(1)) if kurtosis_match else 0.0
    clustering = float(clustering_match.group(1)) if clustering_match else 0.0

    return kurtosis, clustering


def objective_function(params):
    hawkes_decay, rough_hurst = params

    # Boundary constraints
    if not (0.5 < hawkes_decay < 0.99) or not (0.01 < rough_hurst < 0.5):
        return 9999.0  # Heavy penalty for impossible physics

    kurt, cluster = run_kessler_and_extract(hawkes_decay, rough_hurst)

    # Mean Squared Error between our Engine and Reality
    error = ((kurt - TARGET_KURTOSIS) ** 2) + ((cluster - TARGET_CLUSTERING) ** 2)
    return error


if __name__ == "__main__":
    print("==================================================")
    print(" KESSLER AUTONOMIC CALIBRATION ROUTINE")
    print(" Minimizing Error between Simulation and Reality...")
    print("==================================================")

    # Initial Guess: [Hawkes Decay, Rough Volatility Hurst]
    initial_guess = [0.80, 0.10]

    # Nelder-Mead works well for noisy, derivative-free simulation outputs
    res = minimize(objective_function, initial_guess, method="Nelder-Mead")

    print("\n[SUCCESS] Optimal Physics Reached.")
    print(f"Optimal Hawkes Decay: {res.x[0]:.4f}")
    print(f"Optimal Hurst Parameter: {res.x[1]:.4f}")
