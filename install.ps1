param(
  [string]$InstallRoot = "$env:LOCALAPPDATA\CodexTokenSaver"
)

$ErrorActionPreference = "Stop"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$SkillDest = Join-Path $CodexHome "skills\codex-token-saver"
$BinDir = Join-Path $CodexHome "bin"
$CmdPath = Join-Path $BinDir "cts.cmd"

Write-Host "Codex Token Saver installer"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  throw "Python 3 is required. Install Python from https://www.python.org/downloads/windows/ and rerun install.bat."
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
New-Item -ItemType Directory -Force -Path $SkillDest | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $Source "codex_token_saver") $InstallRoot
Copy-Item -Recurse -Force (Join-Path $Source "benchmarks") $InstallRoot
Copy-Item -Recurse -Force (Join-Path $Source "docs") $InstallRoot
Copy-Item -Recurse -Force (Join-Path $Source "skill\codex-token-saver\*") $SkillDest

$cmd = @"
@echo off
set "PYTHONPATH=$InstallRoot;%PYTHONPATH%"
python -m codex_token_saver %*
"@
Set-Content -Path $CmdPath -Value $cmd -Encoding ASCII

$HookScript = Join-Path $CodexHome "hooks\codex-token-saver-post-tool-use.ps1"
$HookDb = Join-Path $InstallRoot "context.sqlite"
$PreviousPythonPath = $env:PYTHONPATH
try {
  if ([string]::IsNullOrEmpty($PreviousPythonPath)) {
    $env:PYTHONPATH = $InstallRoot
  } else {
    $env:PYTHONPATH = "$InstallRoot;$PreviousPythonPath"
  }
  python -m codex_token_saver install-hook --codex-home "$CodexHome" --db "$HookDb" --cts-command "`"$CmdPath`""
  if ($LASTEXITCODE -ne 0) {
    throw "Codex hook installation failed with exit code $LASTEXITCODE."
  }
} finally {
  $env:PYTHONPATH = $PreviousPythonPath
}

Write-Host "Installed cts command: $CmdPath"
Write-Host "Installed Codex skill: $SkillDest"
Write-Host "Installed Codex PostToolUse hook shim: $HookScript"
Write-Host "Add $BinDir to PATH if 'cts' is not found in a new terminal."
Write-Host "Try: cts ab-test --fixtures `"$InstallRoot\benchmarks\fixtures`""
