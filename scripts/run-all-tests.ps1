param(
  [switch]$InstallDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Step {
  param(
    [string]$Label,
    [scriptblock]$Action
  )

  Write-Host "==> $Label"
  & $Action
  if ($LASTEXITCODE -ne 0) {
    throw "Step failed: $Label"
  }
}

function Assert-Command {
  param([string]$Name)

  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $Name"
  }
}

function Invoke-Npm {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
  )

  $npmCmd = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
  if (-not $npmCmd) {
    throw 'Required command not found: npm.cmd'
  }

  & $npmCmd.Source @Arguments
}

$ScriptsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptsDir
$BackendDir = Join-Path $RepoRoot 'services\quant-engine'
$DesktopDir = Join-Path $RepoRoot 'apps\desktop'
$GeneratorPath = Join-Path $BackendDir 'app\scripts\export_ib2026_dashboard_golden.py'

Assert-Command 'python'
Assert-Command 'npm.cmd'

if (-not (Test-Path $GeneratorPath)) {
  throw "Missing generator script: $GeneratorPath"
}

if ($InstallDeps) {
  Invoke-Step 'Install backend dependencies' {
    python -m pip install -r (Join-Path $BackendDir 'requirements.txt')
  }

  Invoke-Step 'Install desktop dependencies' {
    Invoke-Npm install --prefix $DesktopDir
  }
}

Push-Location $BackendDir
try {
  Invoke-Step 'Generate IB2026 golden fixture' {
    python -m app.scripts.export_ib2026_dashboard_golden
  }

  Invoke-Step 'Run backend tests' {
    python -m pytest
  }
}
finally {
  Pop-Location
}

Push-Location $DesktopDir
try {
  Invoke-Step 'Run desktop tests' {
    Invoke-Npm test
  }
}
finally {
  Pop-Location
}

Write-Host 'All tests passed.'
