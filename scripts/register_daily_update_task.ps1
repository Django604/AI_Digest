param(
  [string]$TaskName = "AI_Digest_Daily_Update",
  [string]$Time = "09:00",
  [string]$PythonPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runnerScript = Join-Path $PSScriptRoot "scheduled_update_runner.py"

if (-not (Test-Path $runnerScript)) {
  throw "Scheduled update runner was not found: $runnerScript"
}

function Resolve-PythonExecutable {
  param(
    [string]$ExplicitPath
  )

  if ($ExplicitPath) {
    if (-not (Test-Path $ExplicitPath)) {
      throw "The specified Python path does not exist: $ExplicitPath"
    }
    return (Resolve-Path $ExplicitPath).Path
  }

  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if (-not $pythonCommand) {
    throw "Python was not found. Install Python first or pass -PythonPath."
  }

  $resolvedPath = $pythonCommand.Source
  $pythonwCandidate = Join-Path (Split-Path -Parent $resolvedPath) "pythonw.exe"
  if (Test-Path $pythonwCandidate) {
    return $pythonwCandidate
  }

  return $resolvedPath
}

$pythonExe = Resolve-PythonExecutable -ExplicitPath $PythonPath
$currentUser = "$env:USERDOMAIN\$env:USERNAME"

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument ('"{0}"' -f $runnerScript) -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Scheduled task registered successfully." -ForegroundColor Green
Write-Host "Task name: $TaskName"
Write-Host "Time: daily at $Time"
Write-Host "Python: $pythonExe"
Write-Host "Runner: $runnerScript"
