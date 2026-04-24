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
$rebuildScript = Join-Path $PSScriptRoot "rebuild_dashboard.ps1"
$publishTargets = @(
  "data/source/NEV+ICE_xsai.xlsm",
  "data/source/NEV+ICE_ldai.xlsx",
  "docs/data/dashboard.json",
  "docs/data/dashboard.summary.json"
)

function Invoke-GitProcess {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = "git"
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.WorkingDirectory = $repoRoot
  $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

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

  $combinedOutput = @($stdout.Trim(), $stderr.Trim()) | Where-Object { $_ }
  return @{
    ExitCode = $process.ExitCode
    Stdout = $stdout
    Stderr = $stderr
    Output = $combinedOutput
  }
}

function Invoke-Git {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  $result = Invoke-GitProcess -Arguments $Arguments
  if ($result.ExitCode -ne 0) {
    $details = ($result.Output | Out-String).Trim()
    $message = "Git command failed: git $($Arguments -join ' ')"
    if ($details) {
      $message += "`n$details"
    }

    $joinedArgs = $Arguments -join ' '
    if ($joinedArgs -like "push *") {
      $message += "`n`nPush troubleshooting hints:"
      $message += "`n- Check whether this environment can reach GitHub over HTTPS (port 443)."
      $message += "`n- Check whether your Git credentials still have permission to push to the target repository."
      $message += "`n- Check whether the target branch is protected and rejects direct pushes."
    }

    throw $message
  }

  if ($result.Output) {
    $result.Output | ForEach-Object { Write-Host $_ }
  }
}

function Get-GitOutput {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  $result = Invoke-GitProcess -Arguments $Arguments
  if ($result.ExitCode -ne 0) {
    $details = ($result.Output | Out-String).Trim()
    throw "Git command failed: git $($Arguments -join ' ')`n$details"
  }
  return ($result.Output | Out-String).Trim()
}

Push-Location $repoRoot
try {
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not available in PATH."
  }

  $gitMarker = Join-Path $repoRoot ".git"
  if (-not (Test-Path $gitMarker)) {
    throw "This folder is not a Git repository yet. Run 'git init' here or clone the GitHub repository first."
  }

  $null = Get-GitOutput -Arguments @("rev-parse", "--show-toplevel")

  $currentBranch = Get-GitOutput -Arguments @("branch", "--show-current")
  if (-not $currentBranch) {
    throw "Current branch could not be determined. Please check out a branch before publishing."
  }

  $remoteUrl = Get-GitOutput -Arguments @("remote", "get-url", $Remote)
  if (-not $remoteUrl) {
    throw "Remote '$Remote' is not configured."
  }

  if (-not $AllowExistingStaged) {
    $stagedOutput = Get-GitOutput -Arguments @("diff", "--cached", "--name-only")
    $stagedFiles = @($stagedOutput -split "\r?\n" | Where-Object { $_ })
    if ($stagedFiles.Count -gt 0) {
      $allowedSet = New-Object "System.Collections.Generic.HashSet[string]" ([System.StringComparer]::OrdinalIgnoreCase)
      foreach ($item in $publishTargets) {
        [void]$allowedSet.Add($item)
      }
      $unexpectedStaged = @($stagedFiles | Where-Object { -not $allowedSet.Contains($_) })
      if ($unexpectedStaged.Count -gt 0) {
        throw "There are already staged files outside the publish scope: $($unexpectedStaged -join ', '). Use -AllowExistingStaged only if you are sure."
      }
    }
  }

  if (-not $SkipRebuild) {
    Write-Host "Step 1/4: rebuilding dashboard outputs..." -ForegroundColor Cyan
    & powershell -ExecutionPolicy Bypass -File $rebuildScript
    if ($LASTEXITCODE -ne 0) {
      throw "Rebuild script failed with exit code $LASTEXITCODE."
    }
  } else {
    Write-Host "Step 1/4: rebuild skipped by flag." -ForegroundColor Yellow
  }

  Write-Host "Step 2/4: staging dashboard publish files..." -ForegroundColor Cyan
  $gitAddArgs = @("add", "--") + $publishTargets
  Invoke-Git -Arguments $gitAddArgs

  $gitDiffArgs = @("diff", "--cached", "--name-only", "--") + $publishTargets
  $changedOutput = Get-GitOutput -Arguments $gitDiffArgs
  $changedTargets = @($changedOutput -split "\r?\n" | Where-Object { $_ })
  if ($changedTargets.Count -eq 0) {
    Write-Host "No publishable changes detected. Nothing to commit." -ForegroundColor Yellow
    return
  }

  if (-not $CommitMessage) {
    $CommitMessage = "Update dashboard data " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
  }

  Write-Host "Step 3/4: committing staged publish files..." -ForegroundColor Cyan
  Invoke-Git -Arguments @("commit", "-m", $CommitMessage)

  Write-Host "Step 4/4: pushing to $Remote/$Branch..." -ForegroundColor Cyan
  Invoke-Git -Arguments @("push", $Remote, "HEAD:$Branch")

  Write-Host ""
  Write-Host "Dashboard publish completed successfully." -ForegroundColor Green
  Write-Host "Remote: $Remote" -ForegroundColor DarkGray
  Write-Host "Branch: $Branch" -ForegroundColor DarkGray
  Write-Host "Current branch: $currentBranch" -ForegroundColor DarkGray
  Write-Host "Remote URL: $remoteUrl" -ForegroundColor DarkGray
  Write-Host "Committed files:" -ForegroundColor DarkGray
  foreach ($item in $changedTargets) {
    Write-Host "  - $item" -ForegroundColor DarkGray
  }
} finally {
  Pop-Location
}
