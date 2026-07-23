param()
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Ea = Join-Path $Root "mt4\CHECK.mq4"
if (!(Test-Path $Ea)) { throw "Missing $Ea" }
$TerminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
if (!(Test-Path $TerminalRoot)) { throw "No MetaQuotes Terminal under APPDATA" }
$n = 0
Get-ChildItem $TerminalRoot -Directory | ForEach-Object {
  $experts = Join-Path $_.FullName "MQL4\Experts"
  if (!(Test-Path (Join-Path $_.FullName "MQL4"))) { return }
  New-Item -ItemType Directory -Force -Path $experts | Out-Null
  Copy-Item $Ea (Join-Path $experts "CHECK.mq4") -Force
  Write-Host "OK -> $experts"
  $n++
}
if ($n -eq 0) { throw "No MQL4 terminals found" }
Write-Host "Deployed CHECK.mq4 to $n terminal(s). Compile in MetaEditor (F7)."
