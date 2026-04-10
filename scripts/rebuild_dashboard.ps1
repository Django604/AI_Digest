Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$leadsWorkbook = Join-Path $repoRoot "data/source/NEV+ICE_xsai.xlsm"
$arrivalWorkbook = Join-Path $repoRoot "data/source/NEV+ICE_ldai.xlsx"
$outputJson = Join-Path $repoRoot "docs/data/dashboard.json"

Write-Host "Rebuilding dashboard data from local Excel sources..." -ForegroundColor Cyan
Write-Host "Leads workbook:   $leadsWorkbook"
Write-Host "Arrival workbook: $arrivalWorkbook"
Write-Host "Output JSON:      $outputJson"

python (Join-Path $repoRoot "scripts/build_dashboard.py") `
  --workbook $leadsWorkbook `
  --arrival-workbook $arrivalWorkbook `
  --out $outputJson

if ($LASTEXITCODE -ne 0) {
  throw "Dashboard rebuild failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "dashboard.json rebuilt successfully." -ForegroundColor Green
Write-Host "Next step: commit and push the changed Excel files plus docs/data/dashboard.json to GitHub." -ForegroundColor Yellow
