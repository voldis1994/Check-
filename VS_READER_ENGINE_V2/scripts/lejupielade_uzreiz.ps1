# Lejupielādē VISU SYSTEM projektu uzreiz (PowerShell — viena komanda)
# Nokopējiet un ielīmējiet PowerShell logā, nospiediet Enter.

Set-ExecutionPolicy Bypass -Scope Process -Force
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$InstallPath = "C:\SYSTEM"
$Branch = "main"
$ZipUrl = "https://github.com/voldis1994/VS_READER_ENGINE_V2/archive/refs/heads/$([uri]::EscapeDataString($Branch)).zip"
$Temp = Join-Path $env:TEMP ("system-dl-" + [guid]::NewGuid().ToString("N"))
$ZipFile = Join-Path $Temp "repo.zip"

Write-Host "==> Lejupielade no GitHub..." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $Temp -Force | Out-Null
Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipFile -UseBasicParsing
Expand-Archive -LiteralPath $ZipFile -DestinationPath $Temp -Force

$SystemSrc = Get-ChildItem -Path $Temp -Directory -Recurse |
    Where-Object { $_.Name -eq "SYSTEM" -and (Test-Path (Join-Path $_.FullName "engine")) } |
    Select-Object -First 1

if (-not $SystemSrc) { throw "SYSTEM mape nav atrasta ZIP arhiva" }

Write-Host "==> Kopē uz $InstallPath ..." -ForegroundColor Cyan
if (Test-Path $InstallPath) { Remove-Item $InstallPath -Recurse -Force }
New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
Copy-Item -Path (Join-Path $SystemSrc.FullName "*") -Destination $InstallPath -Recurse -Force

$config = Join-Path $InstallPath "config\system.json"
$json = Get-Content $config -Raw | ConvertFrom-Json
$json.system.root_path = $InstallPath.Replace("\", "\\")
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

Remove-Item $Temp -Recurse -Force

Write-Host ""
Write-Host "GATAVS!  $InstallPath" -ForegroundColor Green
Write-Host "Config:   $config"
Write-Host "Palaid:   $InstallPath\.venv\Scripts\activate"
Write-Host "          python $InstallPath\run_live.py"
