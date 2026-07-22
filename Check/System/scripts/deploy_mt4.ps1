param(
  [string]$TerminalRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExpertsSource = Join-Path $Root "mt4\Experts\CHECK_SYSTEM_V3.mq4"
$IncludeNames = @(
  "CHECK_V3_Protocol.mqh",
  "CHECK_V3_Bridge.mqh",
  "CHECK_V3_Market.mqh",
  "CHECK_V3_Execution.mqh"
)

if (!(Test-Path $ExpertsSource)) {
  throw "Missing EA source: $ExpertsSource"
}

foreach ($Name in $IncludeNames) {
  $Src = Join-Path $Root "mt4\Include\$Name"
  if (!(Test-Path $Src)) {
    throw "Missing include source: $Src"
  }
}

if ($TerminalRoot -eq "") {
  if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
    throw "APPDATA is not set. Provide -TerminalRoot."
  }
  $TerminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
}

if (!(Test-Path $TerminalRoot)) {
  throw "Terminal root not found: $TerminalRoot"
}

$Terminals = @(Get-ChildItem -Path $TerminalRoot -Directory -ErrorAction Stop)
if ($Terminals.Count -eq 0) {
  throw "No MT4 terminal directories found under $TerminalRoot"
}

$Deployed = 0
foreach ($Terminal in $Terminals) {
  $Mql4 = Join-Path $Terminal.FullName "MQL4"
  if (!(Test-Path $Mql4)) {
    continue
  }

  $ExpertsDest = Join-Path $Mql4 "Experts"
  $IncludesDest = Join-Path $Mql4 "Include"
  New-Item -ItemType Directory -Force -Path $ExpertsDest | Out-Null
  New-Item -ItemType Directory -Force -Path $IncludesDest | Out-Null

  Copy-Item -LiteralPath $ExpertsSource -Destination (Join-Path $ExpertsDest "CHECK_SYSTEM_V3.mq4") -Force

  foreach ($Name in $IncludeNames) {
    $Src = Join-Path $Root "mt4\Include\$Name"
    # Angle-bracket includes: MQL4\Include\
    Copy-Item -LiteralPath $Src -Destination (Join-Path $IncludesDest $Name) -Force
    # Quoted includes next to EA: MQL4\Experts\
    Copy-Item -LiteralPath $Src -Destination (Join-Path $ExpertsDest $Name) -Force

    if (!(Test-Path (Join-Path $IncludesDest $Name))) {
      throw "Deploy failed: missing after copy $IncludesDest\$Name"
    }
    if (!(Test-Path (Join-Path $ExpertsDest $Name))) {
      throw "Deploy failed: missing after copy $ExpertsDest\$Name"
    }
  }

  Write-Host "OK Experts+Include -> $Mql4"
  $Deployed++
}

if ($Deployed -eq 0) {
  throw "No MQL4 folders found under $TerminalRoot"
}

Write-Host ""
Write-Host "Deployed to $Deployed terminal data folder(s)."
Write-Host "NEXT: MetaEditor open MQL4\Experts\CHECK_SYSTEM_V3.mq4 -> F7 (0 errors)"
Write-Host "Verify Include files exist next to the EA and under MQL4\Include\"
