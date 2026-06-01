import itertools
import subprocess
import csv
import os
import concurrent.futures
from pathlib import Path

def run_config(args):
    idx, keys, values, exe_path = args
    params = dict(zip(keys, values))

    cmd = [
        exe_path,
        "--leverage-cap", str(params["leverage_cap"]),
        "--base-depth", str(params["base_depth"]),
        "--decay-rate", str(params["decay_rate"]),
        "--freeze-threshold", str(params["freeze_threshold"]),
        "--freeze-duration", str(params["freeze_duration"]),
        "--cb-sensitivity", str(params["cb_sensitivity"]),
        "--value-buy-threshold", str(params["value_buy_threshold"]),
        "--cash-fragility", str(params["cash_fragility"]),
        "--market-maker-resilience", str(params["market_maker_resilience"])
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metrics_line = res.stdout.strip().split('\n')[-1]
        metrics = [float(x) for x in metrics_line.split(',')]
        return idx, values, metrics, None
    except subprocess.CalledProcessError as e:
        return idx, values, None, e.stderr

def main():
    print("Compiling Kessler engine once...")
    subprocess.run(["zig", "build"], check=True)

    exe_path = "zig-out/bin/kessler.exe" if os.name == "nt" else "./zig-out/bin/kessler"
    if not os.path.exists(exe_path):
        print(f"Error: Could not find compiled binary at {exe_path}")
        return

    # EXTREME VULNERABILITY BOUNDS: Leverage up to 75x, Cash fragility down to 0.01
    param_grid = {
        "leverage_cap": [10.0, 40.0, 75.0],
        "base_depth": [200, 1500, 3000],
        "decay_rate": [0.01, 0.05, 0.1],
        "freeze_threshold": [0.3, 0.6, 0.95],
        "freeze_duration": [1, 4, 8],
        "cb_sensitivity": [0.3, 1.4, 2.5],
        "value_buy_threshold": [0.05, 0.20, 0.40],
        "cash_fragility": [0.01, 0.08, 0.15],
        "market_maker_resilience": [0.01, 0.10, 0.20]
    }

    keys = list(param_grid.keys())
    combinations = list(itertools.product(*[param_grid[k] for k in keys]))

    print(f"Starting expanded parameter sweep: {len(combinations)} configurations.")

    output_csv = Path("data/sweep_results.csv")
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    headers = keys + ["max_drawdown", "excess_kurtosis", "vol_clustering", "cascade_depth"]
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

    completed = 0
    total = len(combinations)

    with open(output_csv, "a", newline="") as f:
        writer = csv.writer(f)
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(run_config, (idx, keys, values, exe_path))
                for idx, values in enumerate(combinations)
            ]
            
            for future in concurrent.futures.as_completed(futures):
                idx, values, metrics, error = future.result()
                completed += 1
                
                if error is None:
                    row = list(values) + metrics
                    writer.writerow(row)
                    f.flush()
                    
                    if completed % 500 == 0:
                        print(f"Progress: {completed}/{total} | Latest DD: {metrics[0]:.2f}")
                else:
                    print(f"Error running configuration {idx}: {error}")

    print(f"Sweep complete. Results saved to {output_csv}")

if __name__ == "__main__":
    main()
