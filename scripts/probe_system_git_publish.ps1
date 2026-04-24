param(
  [string]$TaskName = "",
  [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$defaultOutputDir = Join-Path $projectRoot ".runtime\\system_git_probe"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$resolvedOutputPath = if ($OutputPath) { $OutputPath } else { Join-Path $defaultOutputDir "$timestamp.json" }
$outputDir = Split-Path -Parent $resolvedOutputPath

if (-not (Test-Path -LiteralPath $outputDir)) {
  New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

function Invoke-GitProbe {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  $result = @{
    name = $Name
    arguments = $Arguments
    exitCode = 0
    output = ""
    success = $false
  }

  try {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git"
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $quotedArguments = $Arguments | ForEach-Object {
      if ($_ -match '[\s"]') {
        '"' + ($_ -replace '"', '\"') + '"'
      } else {
        $_
      }
    }
    $startInfo.Arguments = ($quotedArguments -join " ")

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $combined = (@($stdout.Trim(), $stderr.Trim()) | Where-Object { $_ }) -join [Environment]::NewLine
    $result.output = $combined
    $result.exitCode = $process.ExitCode
    $result.success = ($process.ExitCode -eq 0)
  } catch {
    $result.output = ($_ | Out-String).Trim()
    $result.exitCode = 1
    $result.success = $false
  }

  return $result
}

$steps = @(
  @{ name = "system-safe-directory"; arguments = @("config", "--system", "--get-all", "safe.directory") },
  @{ name = "remote-origin-url"; arguments = @("-C", $projectRoot, "config", "--get", "remote.origin.url") },
  @{ name = "repo-ssh-command"; arguments = @("-C", $projectRoot, "config", "--get", "core.sshCommand") },
  @{ name = "ls-remote-origin"; arguments = @("-C", $projectRoot, "ls-remote", "origin") },
  @{ name = "push-dry-run-main"; arguments = @("-C", $projectRoot, "push", "--dry-run", "origin", "HEAD:main") }
)

$probeResults = @()
$overallSuccess = $true
$startedAt = Get-Date

try {
  foreach ($step in $steps) {
    $stepResult = Invoke-GitProbe -Name $step.name -Arguments $step.arguments
    $probeResults += $stepResult
    if (-not $stepResult.success) {
      $overallSuccess = $false
      break
    }
  }
} finally {
  $finishedAt = Get-Date
  $payload = @{
    startedAt = $startedAt.ToString("s")
    finishedAt = $finishedAt.ToString("s")
    projectRoot = $projectRoot
    taskName = $TaskName
    overallSuccess = $overallSuccess
    results = $probeResults
  } | ConvertTo-Json -Depth 6
  $payload | Set-Content -LiteralPath $resolvedOutputPath -Encoding utf8

  if ($TaskName) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
  }
}

if (-not $overallSuccess) {
  exit 1
}

exit 0
