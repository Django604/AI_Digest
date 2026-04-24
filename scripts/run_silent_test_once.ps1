param(
  [string]$TaskName = "",
  [switch]$AutoPublish,
  [string]$PublishRemote = "origin",
  [string]$PublishBranch = "main",
  [string]$PublishCommitMessage = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runnerScript = Join-Path $PSScriptRoot "scheduled_update_runner.py"
$pythonExe = "C:\Users\sj-liangcg\AppData\Local\Programs\Python\Python314\python.exe"
$exitCode = 1

if (-not (Test-Path $runnerScript)) {
  throw "Scheduled update runner was not found: $runnerScript"
}

if (-not (Test-Path $pythonExe)) {
  throw "Python executable was not found: $pythonExe"
}

try {
  Set-Location -LiteralPath $projectRoot
  $runnerArgs = @(
    $runnerScript,
    "--mode",
    "silent",
    "--keep-runtime"
  )
  if ($AutoPublish) {
    $runnerArgs += @(
      "--auto-publish",
      "--publish-remote",
      $PublishRemote,
      "--publish-branch",
      $PublishBranch
    )
    if ($PublishCommitMessage) {
      $runnerArgs += @(
        "--publish-commit-message",
        $PublishCommitMessage
      )
    }
  }
  & $pythonExe @runnerArgs
  $exitCode = $LASTEXITCODE
} finally {
  if ($TaskName) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
  }
}

exit $exitCode
