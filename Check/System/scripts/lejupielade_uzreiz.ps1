
Set-ExecutionPolicy Bypass -Scope Process -Force
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$InstallPath = "C:\Check\System"
$Branch = "main"
$ZipUrl = "https://github.com/voldis1994/Check-/archive/refs/heads/$([uri]::EscapeDataString($Branch)).zip"
$Temp = Join-Path $env:TEMP ("system-dl-" + [guid]::NewGuid().ToString("N"))
$ZipFile = Join-Path $Temp "repo.zip"

Write-Host "==> Lejupielade no GitHub..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $Temp -Force | Out-Null
Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipFile -UseBasicParsing
Expand-Archive -LiteralPath $ZipFile -DestinationPath $Temp -Force

$SystemSrc = Get-ChildItem -Path $Temp -Directory -Recurse |
    Where-Object { ($_.Name -ieq "System" -or $_.Name -ieq "SYSTEM") -and (Test-Path (Join-Path $_.FullName "engine")) -and (Test-Path (Join-Path $_.FullName "run_live.py")) } |
    Select-Object -First 1

if (-not $SystemSrc) { throw "System mape nav atrasta ZIP arhiva" }

Write-Host "==> Kopē uz $InstallPath ..." -ForegroundColor Cyan
if (Test-Path $InstallPath) { Remove-Item $InstallPath -Recurse -Force }
New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
Copy-Item -Path (Join-Path $SystemSrc.FullName "*") -Destination $InstallPath -Recurse -Force

$config = Join-Path $InstallPath "config\system.json"
$json = Get-Content $config -Raw | ConvertFrom-Json
# ConvertTo-Json escapes backslashes; do not pre-escape the path.
$json.system.root_path = $InstallPath
$json | ConvertTo-Json -Depth 20 | Set-Content $config -Encoding UTF8

foreach ($dir in @("data\clients","data\logs","data\cache","data\history","data\universe")) {
    New-Item -ItemType Directory -Path (Join-Path $InstallPath $dir) -Force | Out-Null
}

$python = $null
foreach ($cmd in @("python", "py")) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }
    try {
        $versionText = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if (-not $versionText) { continue }
        $parts = $versionText.Trim().Split(".")
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) {
            $python = $cmd
            break
        }
    } catch {
        continue
    }
}
if (-not $python) { throw "Instalējiet Python 3.11+ no https://www.python.org/downloads/ (ar Add to PATH)" }

Write-Host "==> Python vide un atkarības..." -ForegroundColor Cyan
& $python -m venv (Join-Path $InstallPath ".venv")
$venvPy = Join-Path $InstallPath ".venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip -q
& $venvPy -m pip install -r (Join-Path $InstallPath "requirements.txt") -q

Write-Host "==> Sinhronize celus..." -ForegroundColor Cyan
& $venvPy (Join-Path $InstallPath "scripts\sync_paths.py") --root $InstallPath
if ($LASTEXITCODE -ne 0) { throw "sync_paths neizdevas" }

Remove-Item $Temp -Recurse -Force

Write-Host ""
Write-Host "GATAVS!  $InstallPath" -ForegroundColor Green
Write-Host "Config:   $config"
Write-Host "1) FIX_MT4.bat   (kopē Experts+Include uz MT4)"
Write-Host "2) MetaEditor F7 Compile SYSTEM_EA.mq4"
Write-Host "3) PALAID.bat"
Write-Host "4) DASHBOARD.bat"
