import argparse
import subprocess
import csv
import os
import concurrent.futures
from pathlib import Path
import time
import random

def run_simulation(args):
    exe_path, scenario_path, seed, run_id = args
    cmd = [
        exe_path,
        "--scenario", scenario_path,
        "--seed", str(seed)
    ]

    try:
        start_time = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = time.time() - start_time
        
        # Parse the last line of stdout which should be CSV metrics
        metrics_line = res.stdout.strip().split('\n')[-1]
        metrics = [float(x) for x in metrics_line.split(',')]
        return run_id, seed, metrics, duration, None
    except subprocess.CalledProcessError as e:
        return run_id, seed, None, 0, e.stderr
    except Exception as e:
        return run_id, seed, None, 0, str(e)

def main():
    parser = argparse.ArgumentParser(description="Run Kessler in batch mode for Monte Carlo stress tests.")
    parser.add_argument("--scenario", type=str, required=True, help="Path to the YAML scenario file.")
    parser.add_argument("--runs", type=int, default=100, help="Number of Monte Carlo simulations to run.")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent workers.")
    parser.add_argument("--output", type=str, default="data/monte_carlo_results.csv", help="Output CSV file.")
    
    args = parser.parse_args()
    
    exe_path = "zig-out/bin/kessler.exe" if os.name == "nt" else "./zig-out/bin/kessler"
    if not os.path.exists(exe_path):
        print(f"Error: Could not find compiled binary at {exe_path}. Run 'zig build -Doptimize=ReleaseFast' first.")
        return

    scenario_path = args.scenario
    if not os.path.exists(scenario_path):
        print(f"Error: Scenario file not found at {scenario_path}")
        return

    output_csv = Path(args.output)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    headers = ["run_id", "seed", "max_drawdown", "excess_kurtosis", "vol_clustering", "cascade_depth", "duration_sec"]
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

    print(f"Starting Monte Carlo batch mode: {args.runs} runs for scenario '{scenario_path}'.")
    
    # Generate deterministic but varied seeds for the Monte Carlo sweep
    base_seed = hash(scenario_path) & 0xFFFFFFFF
    seeds = [base_seed + i * 997 for i in range(args.runs)]
    
    tasks = [(exe_path, scenario_path, seeds[i], i) for i in range(args.runs)]
    completed = 0
    
    with open(output_csv, "a", newline="") as f:
        writer = csv.writer(f)
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(run_simulation, task) for task in tasks]
            
            for future in concurrent.futures.as_completed(futures):
                run_id, seed, metrics, duration, error = future.result()
                completed += 1
                
                if error is None:
                    row = [run_id, seed] + metrics + [round(duration, 4)]
                    writer.writerow(row)
                    f.flush()
                    
                    if completed % max(1, (args.runs // 10)) == 0 or completed == args.runs:
                        print(f"Progress: {completed}/{args.runs} | Last DD: {metrics[0]:.2f}% | Seed: {seed}")
                else:
                    print(f"Error running simulation {run_id} (Seed {seed}): {error}")

    print(f"Monte Carlo batch run complete. Results saved to {output_csv}")

if __name__ == "__main__":
    main()
