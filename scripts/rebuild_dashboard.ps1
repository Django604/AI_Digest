param(
  [string]$Workbook = "",
  [string]$ArrivalWorkbook = "",
  [string]$Out = "",
  [string]$SummaryOut = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$leadsWorkbook = if ($Workbook) { $Workbook } else { Join-Path $repoRoot "data/source/NEV+ICE_xsai.xlsm" }
$arrivalWorkbook = if ($ArrivalWorkbook) { $ArrivalWorkbook } else { Join-Path $repoRoot "data/source/NEV+ICE_ldai.xlsx" }
$outputJson = if ($Out) { $Out } else { Join-Path $repoRoot "docs/data/dashboard.json" }
$summaryJson = if ($SummaryOut) { $SummaryOut } else { Join-Path (Split-Path -Parent $outputJson) "dashboard.summary.json" }
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonCommand) {
  $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $pythonCommand) {
  throw "Python is not installed or not available in PATH."
}

$pythonArgs = @()
if ($pythonCommand.Name -ieq "py") {
  $pythonArgs += "-3"
}
$pythonArgs += (Join-Path $repoRoot "scripts/build_dashboard.py")
$pythonArgs += "--workbook", $leadsWorkbook
$pythonArgs += "--arrival-workbook", $arrivalWorkbook
$pythonArgs += "--out", $outputJson
$pythonArgs += "--summary-out", $summaryJson

Write-Host "Rebuilding dashboard data from local Excel sources..." -ForegroundColor Cyan
Write-Host "Leads workbook:   $leadsWorkbook"
Write-Host "Arrival workbook: $arrivalWorkbook"
Write-Host "Output JSON:      $outputJson"
Write-Host "Summary JSON:     $summaryJson"

& $pythonCommand.Source @pythonArgs

if ($LASTEXITCODE -ne 0) {
  throw "Dashboard rebuild failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "dashboard.json rebuilt successfully." -ForegroundColor Green
Write-Host "Next step: commit and push the changed Excel files plus docs/data/dashboard.json and docs/data/dashboard.summary.json to GitHub." -ForegroundColor Yellow
