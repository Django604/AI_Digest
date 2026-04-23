param(
  [string]$TaskNamePrefix = "AI_Digest_Daily_Update",
  [string]$Time = "09:00",
  [int]$SilentDelayMinutes = 1,
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
$culture = [System.Globalization.CultureInfo]::InvariantCulture

function Resolve-DailyTime {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Value
  )

  try {
    return [datetime]::ParseExact($Value, "HH:mm", $culture)
  } catch {
    throw "Time must use HH:mm format, for example 09:00."
  }
}

$interactiveRunTime = Resolve-DailyTime -Value $Time
$silentRunTime = $interactiveRunTime.AddMinutes($SilentDelayMinutes)
$interactiveTaskName = "${TaskNamePrefix}_Interactive"
$silentTaskName = "${TaskNamePrefix}_Silent"
$legacyTaskName = $TaskNamePrefix

$interactiveAction = New-ScheduledTaskAction -Execute $pythonExe -Argument ('"{0}" --mode interactive' -f $runnerScript) -WorkingDirectory $projectRoot
$silentAction = New-ScheduledTaskAction -Execute $pythonExe -Argument ('"{0}" --mode silent' -f $runnerScript) -WorkingDirectory $projectRoot
$interactiveTrigger = New-ScheduledTaskTrigger -Daily -At $interactiveRunTime.ToString("HH:mm")
$silentTrigger = New-ScheduledTaskTrigger -Daily -At $silentRunTime.ToString("HH:mm")
$interactivePrincipal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
$silentPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$interactiveSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$silentSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

if ($legacyTaskName -ne $interactiveTaskName -and $legacyTaskName -ne $silentTaskName) {
  Unregister-ScheduledTask -TaskName $legacyTaskName -Confirm:$false -ErrorAction SilentlyContinue
}

Register-ScheduledTask -TaskName $interactiveTaskName -Action $interactiveAction -Trigger $interactiveTrigger -Principal $interactivePrincipal -Settings $interactiveSettings -Force | Out-Null
Register-ScheduledTask -TaskName $silentTaskName -Action $silentAction -Trigger $silentTrigger -Principal $silentPrincipal -Settings $silentSettings -Force | Out-Null

Write-Host "Scheduled tasks registered successfully." -ForegroundColor Green
Write-Host "Interactive task: $interactiveTaskName"
Write-Host "Interactive time: daily at $($interactiveRunTime.ToString("HH:mm"))"
Write-Host "Silent fallback task: $silentTaskName"
Write-Host "Silent time: daily at $($silentRunTime.ToString("HH:mm"))"
Write-Host "Silent delay minutes: $SilentDelayMinutes"
Write-Host "Python: $pythonExe"
Write-Host "Runner: $runnerScript"
