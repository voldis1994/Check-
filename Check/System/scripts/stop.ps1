# CHECK SYSTEM v2 — stop / kill switch
# Usage: .\scripts\stop.ps1 [-KillProcess]
param(
    [switch]$KillProcess
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$runtime = Join-Path $Root "runtime"
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$stopFile = Join-Path $runtime "STOP_TRADING"
Set-Content -Path $stopFile -Value "stopped $(Get-Date -Format o)`n" -Encoding utf8
Write-Host "Kill switch engaged: runtime\STOP_TRADING" -ForegroundColor Yellow

if ($KillProcess) {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -match "checktrader") }
    foreach ($p in $procs) {
        Write-Host "Stopping PID $($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Done. Remove STOP_TRADING when ready to trade again."
