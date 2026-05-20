param([string]$Seed)
if ([string]::IsNullOrWhiteSpace($Seed)) {
    Write-Host "Usage: .\scripts\run_seed.ps1 <SEED>"
    exit
}
Write-Host "=================================================="
Write-Host " IGNITING PROJECT KESSLER | SEED: $Seed"
Write-Host "=================================================="
zig build -Doptimize=ReleaseFast
.\zig-out\bin\kessler.exe --seed $Seed
# If you have python installed:
# python scripts\visualize.py kessler_telemetry.csv
