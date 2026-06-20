#!/usr/bin/env python3
"""
Kessler V2 — Hyperparameter Sweep Manager
Runs parallel training permutations on 50-year synthetic data,
evaluates each on real 60-day data, picks the winner.

Usage: python3 scripts/sweep.py [--cores 4] [--steps 15000000]
"""
# pip install numpy subprocess

import os
import sys
import subprocess
import time
import json
import re
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
DATA_DIR = PROJECT_DIR / "data"
WEIGHTS_DIR = PROJECT_DIR / "weights"
RESULTS_DIR = PROJECT_DIR / "results"
SWEEP_DIR = PROJECT_DIR / "sweep"

# ═══════════════════════════════════════════════════════════════
#  HYPERPARAMETER GRID
# ═══════════════════════════════════════════════════════════════

GRID = {
    "sl_tp": [
        (30.0, 60.0),    # tight
        (40.0, 80.0),    # medium-tight
        (50.0, 100.0),   # baseline
        (60.0, 120.0),   # wide
    ],
    "ent_coef": [
        0.005,
        0.01,
        0.02,
    ],
    "lr": [
        1e-4,
        3e-4,
        5e-4,
    ],
}


def get_max_cores():
    """Detect usable cores."""
    # Since each process spawns 8 threads natively in Zig, 
    # we limit python parallel processes to avoid thrashing.
    try:
        n = os.cpu_count() or 4
        return max(1, n // 8)
    except:
        return 1


def generate_permutations():
    """Generate all hyperparameter combinations."""
    perms = []
    idx = 0
    for sl, tp in GRID["sl_tp"]:
        for ent in GRID["ent_coef"]:
            for lr in GRID["lr"]:
                perms.append({
                    "id": idx,
                    "name": f"sl{int(sl)}_tp{int(tp)}_ent{ent}_lr{lr}",
                    "sl": sl,
                    "tp": tp,
                    "ent_coef": ent,
                    "lr": lr,
                })
                idx += 1
    return perms


def patch_and_compile(perm, data_file, steps):
    """Patch source files, compile a unique binary for this permutation."""
    variant_dir = SWEEP_DIR / perm["name"]
    variant_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy source files to variant directory
    src_variant = variant_dir / "src"
    src_variant.mkdir(parents=True, exist_ok=True)
    
    # Read original env.zig
    env_src = (SRC_DIR / "env.zig").read_text()
    
    # Patch SL_POINTS and TP_POINTS
    env_src = re.sub(
        r'pub const SL_POINTS: f32 = [\d.]+;',
        f'pub const SL_POINTS: f32 = {perm["sl"]:.1f};',
        env_src
    )
    env_src = re.sub(
        r'pub const TP_POINTS: f32 = [\d.]+;',
        f'pub const TP_POINTS: f32 = {perm["tp"]:.1f};',
        env_src
    )
    
    # Write patched env.zig
    (src_variant / "env.zig").write_text(env_src)
    
    # Read original train.zig
    train_src = (SRC_DIR / "train.zig").read_text()
    
    # Patch ENT_COEF
    train_src = re.sub(
        r'const ENT_COEF: f32 = [\d.e-]+;',
        f'const ENT_COEF: f32 = {perm["ent_coef"]};',
        train_src
    )
    
    # Patch LR
    train_src = re.sub(
        r'const LR: f32 = [\d.e-]+;',
        f'const LR: f32 = {perm["lr"]};',
        train_src
    )
    
    # Patch TOTAL_STEPS
    train_src = re.sub(
        r'const TOTAL_STEPS: u64 = [\d_]+;',
        f'const TOTAL_STEPS: u64 = {steps};',
        train_src
    )
    
    # Patch data file path
    train_src = train_src.replace(
        '"data/nas100_5m.bin"',
        f'"{data_file}"'
    )
    
    # Patch output weights filename
    weight_file = f"sweep/{perm['name']}/weights.bin"
    train_src = train_src.replace(
        '"kessler_v2_weights.bin"',
        f'"{weight_file}"'
    )
    
    # Patch checkpoint directory 
    # Find checkpoint save pattern and redirect
    train_src = re.sub(
        r'"weights/kessler_v2_',
        f'"sweep/{perm["name"]}/ckpt_',
        train_src
    )
    
    # Write patched train.zig
    (src_variant / "train.zig").write_text(train_src)
    
    # Compile
    binary_name = variant_dir / "kessler"
    compile_cmd = [
        "zig", "build-exe",
        str(src_variant / "train.zig"),
        "-O", "ReleaseFast",
        "-mcpu=native",
        "-lc",
        f"-femit-bin={binary_name}",
    ]
    
    result = subprocess.run(
        compile_cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        timeout=120,
    )
    
    if result.returncode != 0:
        return None, f"Compile failed: {result.stderr[:500]}"
    
    return str(binary_name), None


def run_training(binary_path, perm):
    """Run a single training binary and capture output."""
    start = time.time()
    
    result = subprocess.run(
        [binary_path],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        timeout=28800,  # 8 hour max
    )
    
    elapsed = time.time() - start
    
    # Parse output for key metrics
    output = result.stdout + result.stderr
    metrics = {
        "name": perm["name"],
        "sl": perm["sl"],
        "tp": perm["tp"],
        "ent_coef": perm["ent_coef"],
        "lr": perm["lr"],
        "elapsed_sec": round(elapsed, 1),
        "exit_code": result.returncode,
    }
    
    # Extract final training metrics
    for line in output.split('\n'):
        if 'Final balance' in line:
            m = re.search(r'\$([\d.]+)', line)
            if m:
                metrics["final_balance"] = float(m.group(1))
        if 'Total trades' in line:
            m = re.search(r'(\d+)', line.split(':')[-1])
            if m:
                metrics["total_trades"] = int(m.group(1))
        if 'Win rate' in line:
            m = re.search(r'([\d.]+)%', line)
            if m:
                metrics["winrate"] = float(m.group(1))
    
    # Save full output log
    log_file = SWEEP_DIR / perm["name"] / "training.log"
    log_file.write_text(output)
    
    return metrics


def run_evaluation(perm):
    """Run evaluation on REAL 60-day data using this permutation's weights."""
    weight_file = SWEEP_DIR / perm["name"] / "weights.bin"
    
    if not weight_file.exists():
        return {"name": perm["name"], "error": "No weights file found"}
    
    # Run evaluate.py with specific SL/TP override
    # We need to pass the SL/TP to the evaluator
    eval_cmd = [
        "python3", str(PROJECT_DIR / "scripts" / "evaluate.py"),
        str(weight_file),
        "--sl", str(perm["sl"]),
        "--tp", str(perm["tp"]),
    ]
    
    result = subprocess.run(
        eval_cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        timeout=300,
    )
    
    output = result.stdout + result.stderr
    eval_metrics = {"name": perm["name"]}
    
    # Parse scorecard
    for line in output.split('\n'):
        if 'Total trades' in line and ':' in line:
            m = re.search(r'(\d+)', line.split(':')[-1])
            if m:
                eval_metrics["eval_trades"] = int(m.group(1))
        if 'Win rate' in line:
            m = re.search(r'([\d.]+)%', line)
            if m:
                eval_metrics["eval_winrate"] = float(m.group(1))
        if 'Profit factor' in line:
            m = re.search(r'([\d.]+)', line.split(':')[-1])
            if m:
                eval_metrics["eval_pf"] = float(m.group(1))
        if 'Sharpe ratio' in line:
            m = re.search(r'(-?[\d.]+)', line.split(':')[-1])
            if m:
                eval_metrics["eval_sharpe"] = float(m.group(1))
        if 'Total PnL' in line:
            m = re.search(r'\$([\d,.]+)', line)
            if m:
                eval_metrics["eval_pnl"] = float(m.group(1).replace(',', ''))
        if 'Max drawdown' in line:
            m = re.search(r'([\d.]+)%', line)
            if m:
                eval_metrics["eval_max_dd"] = float(m.group(1))
        if 'Account return' in line:
            m = re.search(r'([\d.]+)%', line)
            if m:
                eval_metrics["eval_return"] = float(m.group(1))
    
    # Save eval log
    eval_log = SWEEP_DIR / perm["name"] / "evaluation.log"
    eval_log.write_text(output)
    
    return eval_metrics


def run_single_permutation(args):
    """Run a single permutation end-to-end: compile, train, evaluate."""
    perm, data_file, steps = args
    
    print(f"  [{perm['id']:2d}] Starting: {perm['name']}")
    
    # 1. Patch and compile
    binary, err = patch_and_compile(perm, data_file, steps)
    if err:
        print(f"  [{perm['id']:2d}] ✗ Compile error: {err[:100]}")
        return {"name": perm["name"], "error": err}
    
    # 2. Train
    print(f"  [{perm['id']:2d}] Training {perm['name']} ...")
    train_metrics = run_training(binary, perm)
    
    if train_metrics.get("exit_code", 1) != 0:
        print(f"  [{perm['id']:2d}] ✗ Training failed")
        return train_metrics
    
    print(f"  [{perm['id']:2d}] ✓ Trained in {train_metrics.get('elapsed_sec', '?')}s "
          f"| trades={train_metrics.get('total_trades', '?')} "
          f"| wr={train_metrics.get('winrate', '?')}%")
    
    # 3. Evaluate on real data
    eval_metrics = run_evaluation(perm)
    
    # Merge
    combined = {**train_metrics, **eval_metrics}
    
    print(f"  [{perm['id']:2d}] ✓ Eval: PnL=${combined.get('eval_pnl', '?')} "
          f"| Sharpe={combined.get('eval_sharpe', '?')} "
          f"| PF={combined.get('eval_pf', '?')}")
    
    return combined


def print_results_table(all_results):
    """Print a formatted comparison table and pick the winner."""
    print("\n" + "═" * 100)
    print("  KESSLER V2 — HYPERPARAMETER SWEEP RESULTS")
    print("═" * 100)
    
    # Header
    print(f"  {'Name':<30s} {'SL/TP':>8s} {'Ent':>6s} {'Trades':>7s} "
          f"{'WR%':>6s} {'PF':>6s} {'Sharpe':>7s} {'PnL':>12s} {'DD%':>6s} {'Time':>7s}")
    print("  " + "-" * 96)
    
    valid = []
    for r in all_results:
        if "error" in r:
            print(f"  {r['name']:<30s} ERROR: {r['error'][:60]}")
            continue
        
        name = r.get("name", "?")
        sl_tp = f"{r.get('sl', '?'):.0f}/{r.get('tp', '?'):.0f}"
        ent = f"{r.get('ent_coef', '?')}"
        trades = f"{r.get('eval_trades', r.get('total_trades', '?'))}"
        wr = f"{r.get('eval_winrate', r.get('winrate', 0)):.1f}"
        pf = f"{r.get('eval_pf', 0):.2f}"
        sharpe = f"{r.get('eval_sharpe', 0):.2f}"
        pnl = f"${r.get('eval_pnl', 0):,.0f}"
        dd = f"{r.get('eval_max_dd', 0):.1f}"
        elapsed = f"{r.get('elapsed_sec', 0):.0f}s"
        
        print(f"  {name:<30s} {sl_tp:>8s} {ent:>6s} {trades:>7s} "
              f"{wr:>6s} {pf:>6s} {sharpe:>7s} {pnl:>12s} {dd:>6s} {elapsed:>7s}")
        
        valid.append(r)
    
    # Pick winner by Sharpe ratio (primary) with PnL as tiebreaker
    if valid:
        winner = max(valid, key=lambda x: (
            x.get("eval_sharpe", 0),
            x.get("eval_pnl", 0),
        ))
        
        print("\n" + "═" * 100)
        print(f"  🏆 WINNER: {winner['name']}")
        print(f"     SL/TP: {winner.get('sl', '?'):.0f}/{winner.get('tp', '?'):.0f}")
        print(f"     Entropy: {winner.get('ent_coef', '?')}")
        print(f"     Sharpe: {winner.get('eval_sharpe', 0):.2f}")
        print(f"     PnL: ${winner.get('eval_pnl', 0):,.0f}")
        print(f"     Win Rate: {winner.get('eval_winrate', 0):.1f}%")
        print(f"     Profit Factor: {winner.get('eval_pf', 0):.2f}")
        print(f"     Max DD: {winner.get('eval_max_dd', 0):.1f}%")
        print("═" * 100)
        
        # Copy winner weights to main directory
        winner_weights = SWEEP_DIR / winner["name"] / "weights.bin"
        if winner_weights.exists():
            dest = PROJECT_DIR / "kessler_v2_best_weights.bin"
            shutil.copy2(str(winner_weights), str(dest))
            print(f"\n  Winner weights copied to: {dest}")
        
        # Save results JSON
        results_file = SWEEP_DIR / "sweep_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "winner": winner["name"],
                "all_results": all_results,
            }, f, indent=2, default=str)
        print(f"  Full results saved to: {results_file}")
    
    return winner if valid else None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kessler V2 Hyperparameter Sweep")
    parser.add_argument("--cores", type=int, default=None,
                        help="Max parallel training runs (default: auto-detect)")
    parser.add_argument("--steps", type=int, default=15_000_000,
                        help="Training steps per run (default: 15M)")
    parser.add_argument("--data", type=str, default="data/nas100_50yr_5m.bin",
                        help="Training data file")
    args = parser.parse_args()
    
    max_cores = args.cores or get_max_cores()
    data_file = args.data
    steps = args.steps
    
    # Check data file exists
    data_path = PROJECT_DIR / data_file
    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}")
        print("Run: python3 scripts/generate_synthetic_50yr.py first")
        sys.exit(1)
    
    # Create sweep directory
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate permutations
    perms = generate_permutations()
    
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   KESSLER V2 — HYPERPARAMETER SWEEP                    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Permutations  : {len(perms)}")
    print(f"  Parallel cores: {max_cores}")
    print(f"  Steps per run : {steps:,}")
    print(f"  Data file     : {data_file}")
    print(f"  Batches       : {(len(perms) + max_cores - 1) // max_cores}")
    print()
    
    for p in perms:
        print(f"    [{p['id']:2d}] {p['name']}")
    print()
    
    # Run permutations in parallel
    start_time = time.time()
    all_results = []
    
    # Process in batches to control parallelism
    batch_size = max_cores
    for batch_start in range(0, len(perms), batch_size):
        batch = perms[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(perms) + batch_size - 1) // batch_size
        
        print(f"\n── Batch {batch_num}/{total_batches} "
              f"({len(batch)} runs) ──")
        
        with ProcessPoolExecutor(max_workers=len(batch)) as executor:
            futures = {
                executor.submit(run_single_permutation, (p, data_file, steps)): p
                for p in batch
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=28800)
                    all_results.append(result)
                except Exception as e:
                    perm = futures[future]
                    print(f"  [{perm['id']:2d}] ✗ Exception: {e}")
                    all_results.append({"name": perm["name"], "error": str(e)})
    
    total_time = time.time() - start_time
    
    # Print results
    winner = print_results_table(all_results)
    
    print(f"\n  Total sweep time: {total_time/60:.1f} minutes")
    print(f"  Completed: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
