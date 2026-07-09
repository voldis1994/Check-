[CmdletBinding()]
param(
    [string] $InstallPath = "C:\Check\System",
    [string] $RepoUrl = "https://github.com/voldis1994/Check-.git",
    [string] $Branch = "main",
    [string] $Mt4DataPath = "",
    [switch] $SkipTests = $true,
    [switch] $SkipMt4
)

$ErrorActionPreference = "Stop"

function Write-Step([string] $Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-CommandExists([string] $Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonCommand {
    foreach ($candidate in @("python", "py")) {
        if (-not (Test-CommandExists $candidate)) { continue }
        try {
            $versionText = & $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if (-not $versionText) { continue }
            $parts = $versionText.Trim().Split(".")
            $major = [int]$parts[0]
            $minor = [int]$parts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 11)) {
                return $candidate
            }
            Write-Host "Atrasts $candidate $versionText, bet vajag Python 3.11+" -ForegroundColor Yellow
        } catch {
            continue
        }
    }
    return $null
}

function Install-FromGit {
    param(
        [string] $Destination,
        [string] $Url,
        [string] $Ref
    )
    if (Test-Path $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    & git clone --branch $Ref --single-branch --depth 1 $Url $Destination
    if ($LASTEXITCODE -ne 0) {
        throw "git clone neizdevās (branch: $Ref)"
    }
}

function Resolve-RepoSystemDir {
    param([string] $RepoRoot)
    $direct = Join-Path $RepoRoot "Check\System"
    if (Test-Path $direct) {
        return $direct
    }
    $found = Get-ChildItem -Path $RepoRoot -Directory -Recurse |
        Where-Object { $_.Name -eq "System" -and (Test-Path (Join-Path $_.FullName "engine")) } |
        Select-Object -First 1
    if (-not $found) {
        throw "Repozitorijā nav Check/System mapes"
    }
    return $found.FullName
}

function Install-FromZip {
    param(
        [string] $Destination,
        [string] $OwnerRepo,
        [string] $Ref
    )
    $encodedRef = [uri]::EscapeDataString($Ref)
    $zipUrl = "https://github.com/$OwnerRepo/archive/refs/heads/$encodedRef.zip"
    $tempRoot = Join-Path $env:TEMP ("system-install-" + [guid]::NewGuid().ToString("N"))
    $zipFile = Join-Path $tempRoot "repo.zip"
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

    Write-Host "Lejupielādē no: $zipUrl"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile -UseBasicParsing
    Expand-Archive -LiteralPath $zipFile -DestinationPath $tempRoot -Force

    $repoRoot = Get-ChildItem -Path $tempRoot -Directory | Select-Object -First 1
    if (-not $repoRoot) {
        throw "ZIP arhīvā nav atrasta repozitorija"
    }
    $systemDir = Resolve-RepoSystemDir -RepoRoot $repoRoot.FullName

    if (Test-Path $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -Path (Join-Path $systemDir "*") -Destination $Destination -Recurse -Force
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

function Update-ConfigRootPath {
    param(
        [string] $ConfigFile,
        [string] $RootPath
    )
    $escaped = $RootPath.Replace("\", "\\")
    $json = Get-Content -LiteralPath $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $json.system.root_path = $escaped
    $json | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ConfigFile -Encoding UTF8
}

function Ensure-DataDirectories {
    param([string] $Root)
    $relativePaths = @(
        "data\clients",
        "data\logs",
        "data\cache",
        "data\history",
        "data\universe",
        "config"
    )
    foreach ($relative in $relativePaths) {
        $full = Join-Path $Root $relative
        New-Item -ItemType Directory -Path $full -Force | Out-Null
    }
}

function Install-Mt4Files {
    param(
        [string] $SystemRoot,
        [string] $Mt4Root
    )
    if (-not (Test-Path $Mt4Root)) {
        throw "MT4 mape neeksistē: $Mt4Root"
    }
    $expertsSource = Join-Path $SystemRoot "mql4\Experts"
    $includeSource = Join-Path $SystemRoot "mql4\Include"
    $expertsTarget = Join-Path $Mt4Root "Experts"
    $includeTarget = Join-Path $Mt4Root "Include"

    if (-not (Test-Path $expertsTarget)) { New-Item -ItemType Directory -Path $expertsTarget -Force | Out-Null }
    if (-not (Test-Path $includeTarget)) { New-Item -ItemType Directory -Path $includeTarget -Force | Out-Null }

    Copy-Item -Path (Join-Path $expertsSource "*") -Destination $expertsTarget -Recurse -Force
    Copy-Item -Path (Join-Path $includeSource "*") -Destination $includeTarget -Recurse -Force
}

Write-Host "========================================" -ForegroundColor Green
Write-Host " SYSTEM — automātiskā uzstādīšana" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Mērķa mape: $InstallPath"
Write-Host "Zars:       $Branch"

Write-Step "Pārbauda Python 3.11+"
$pythonCmd = Get-PythonCommand
if (-not $pythonCmd) {
    throw @"
Python 3.11+ nav atrasts.
Lejupielādējiet no https://www.python.org/downloads/ un instalējiet ar 'Add to PATH'.
"@
}
Write-Host "Izmanto: $pythonCmd"

Write-Step "Lejupielādē repozitoriju"
$tempRepo = Join-Path $env:TEMP ("system-repo-" + [guid]::NewGuid().ToString("N"))
if (Test-CommandExists "git") {
    Write-Host "Izmanto git clone..."
    Install-FromGit -Destination $tempRepo -Url $RepoUrl -Ref $Branch
    $sourceSystem = Resolve-RepoSystemDir -RepoRoot $tempRepo
} else {
    Write-Host "git nav atrasts — lejupielādē ZIP no GitHub..."
    Install-FromZip -Destination $InstallPath -OwnerRepo "voldis1994/Check-" -Ref $Branch
    $sourceSystem = $null
    $tempRepo = $null
}

if ($sourceSystem) {
    Write-Step "Kopē failus uz $InstallPath"
    if (Test-Path $InstallPath) {
        Write-Host "Esošā mape tiks pārrakstīta: $InstallPath" -ForegroundColor Yellow
        Remove-Item -LiteralPath $InstallPath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
    Copy-Item -Path (Join-Path $sourceSystem "*") -Destination $InstallPath -Recurse -Force
    Remove-Item -LiteralPath $tempRepo -Recurse -Force
}

Write-Step "Izveido datu mapes un atjaunina config"
Ensure-DataDirectories -Root $InstallPath
$configPath = Join-Path $InstallPath "config\system.json"
Update-ConfigRootPath -ConfigFile $configPath -RootPath $InstallPath
Write-Host "root_path iestatīts uz: $InstallPath"

Write-Step "Izveido Python virtuālo vidi un instalē atkarības"
$venvPath = Join-Path $InstallPath ".venv"
& $pythonCmd -m venv $venvPath
$venvPython = Join-Path $venvPath "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $InstallPath "requirements.txt")

Write-Step "Sinhronizē ceļus"
$syncPaths = Join-Path $InstallPath "scripts\sync_paths.py"
& $venvPython $syncPaths --root $InstallPath
if ($LASTEXITCODE -ne 0) {
    throw "sync_paths neizdevās (exit code $LASTEXITCODE)"
}

if (-not $SkipMt4 -and $Mt4DataPath) {
    Write-Step "Kopē MT4 EA failus"
    Install-Mt4Files -SystemRoot $InstallPath -Mt4Root $Mt4DataPath
    Write-Host "MT4 faili nokopēti uz: $Mt4DataPath"
} elseif (-not $SkipMt4) {
    Write-Host ""
    Write-Host "MT4 faili NAV nokopēti (nav norādīts -Mt4DataPath)." -ForegroundColor Yellow
    Write-Host 'Piemērs: -Mt4DataPath "C:\Users\...\Terminal\XXXXXXXX\MQL4"' -ForegroundColor Yellow
}

if (-not $SkipTests) {
    Write-Step "Palaid testus (pytest)"
    Push-Location $InstallPath
    try {
        & $venvPython -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "pytest neizdevās (exit code $LASTEXITCODE)"
        }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " UZSTĀDĪŠANA PABEIGTA" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Projekta mape:     $InstallPath"
Write-Host "Konfigurācija:     $configPath"
Write-Host "Python (venv):     $venvPython"
Write-Host ""
Write-Host "Nākamie soļi:"
Write-Host "  1. Pielāgojiet config: $configPath"
Write-Host "  2. MT4: scripts\copy_mql4_to_mt4.bat `"...\MQL4`""
Write-Host "  3. MT4: pievienojiet SYSTEM_EA chartam"
Write-Host "  4. Palaidiet: PALAID.bat"
Write-Host "  5. LIVE pārbaude: $venvPython tools\validate_live.py --root `"$InstallPath`""
Write-Host ""
