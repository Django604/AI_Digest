param(
  [string]$Remote = "origin",
  [string]$Branch = "main",
  [string]$CommitMessage = "",
  [switch]$SkipRebuild,
  [switch]$AllowExistingStaged
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$publishScript = Join-Path $PSScriptRoot "dashboard_publish.py"
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
$pythonArgs += $publishScript
$pythonArgs += "--remote", $Remote
$pythonArgs += "--branch", $Branch
if ($CommitMessage) {
  $pythonArgs += "--commit-message", $CommitMessage
}
if ($SkipRebuild) {
  $pythonArgs += "--skip-rebuild"
}
if ($AllowExistingStaged) {
  $pythonArgs += "--allow-existing-staged"
}

Write-Host "Publishing dashboard data..." -ForegroundColor Cyan
Write-Host "Remote: $Remote"
Write-Host "Branch: $Branch"
Write-Host "Skip rebuild: $([bool]$SkipRebuild)"
Write-Host "Allow existing staged: $([bool]$AllowExistingStaged)"

Push-Location $repoRoot
try {
  & $pythonCommand.Source @pythonArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Dashboard publish failed with exit code $LASTEXITCODE."
  }
} finally {
  Pop-Location
}
