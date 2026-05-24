$ErrorActionPreference = 'Stop'

$WorkspaceRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$UserHome = [Environment]::GetFolderPath('UserProfile')
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $UserHome '.codex' }
$VaultRoot = if ($env:CODEX_TOKEN_VAULT_DIR) { $env:CODEX_TOKEN_VAULT_DIR } else { Join-Path $UserHome '.omx\token-vault-codex' }
$VaultBin = Join-Path $VaultRoot 'bin'
$CodexHooksDir = Join-Path $CodexHome 'hooks'
$HookScript = Join-Path $VaultBin 'codex-token-vault-hook.mjs'
$CoreScript = Join-Path $VaultBin 'token-vault-core.mjs'
$StatusHookScript = Join-Path $VaultBin 'codex-status-hook.mjs'
$StatusCoreScript = Join-Path $VaultBin 'codex-status-core.mjs'
$ShimScript = Join-Path $CodexHooksDir 'codex-token-vault-windows-shim.ps1'
$StatusShimScript = Join-Path $CodexHooksDir 'codex-status-windows-shim.ps1'
$HooksJson = Join-Path $CodexHome 'hooks.json'
$NodePath = (Get-Command node).Source
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

New-Item -ItemType Directory -Force -Path $VaultBin, (Join-Path $VaultRoot 'artifacts'), $CodexHooksDir | Out-Null

Copy-Item -LiteralPath (Join-Path $WorkspaceRoot 'src\codex-token-vault-hook.mjs') -Destination $HookScript -Force
Copy-Item -LiteralPath (Join-Path $WorkspaceRoot 'src\token-vault-core.mjs') -Destination $CoreScript -Force
Copy-Item -LiteralPath (Join-Path $WorkspaceRoot 'src\codex-status-hook.mjs') -Destination $StatusHookScript -Force
Copy-Item -LiteralPath (Join-Path $WorkspaceRoot 'src\codex-status-core.mjs') -Destination $StatusCoreScript -Force

@"
`$ErrorActionPreference = 'Stop'
`$stdinPayload = [Console]::In.ReadToEnd()
`$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
`$startInfo.FileName = '$NodePath'
`$startInfo.UseShellExecute = `$false
`$startInfo.RedirectStandardInput = `$true
`$startInfo.RedirectStandardOutput = `$true
`$startInfo.RedirectStandardError = `$true
`$startInfo.Arguments = '"$HookScript"'
if (-not `$env:CODEX_TOKEN_VAULT_DIR) { `$startInfo.Environment['CODEX_TOKEN_VAULT_DIR'] = '$VaultRoot' }
`$startInfo.Environment['NODE_NO_WARNINGS'] = '1'
`$process = [System.Diagnostics.Process]::new()
`$process.StartInfo = `$startInfo
`$null = `$process.Start()
`$stdoutTask = `$process.StandardOutput.ReadToEndAsync()
`$stderrTask = `$process.StandardError.ReadToEndAsync()
`$process.StandardInput.Write(`$stdinPayload)
`$process.StandardInput.Close()
`$process.WaitForExit()
[Console]::Out.Write(`$stdoutTask.Result)
[Console]::Error.Write(`$stderrTask.Result)
exit `$process.ExitCode
"@ | Set-Content -LiteralPath $ShimScript -Encoding UTF8

@"
`$ErrorActionPreference = 'Stop'
`$stdinPayload = [Console]::In.ReadToEnd()
`$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
`$startInfo.FileName = '$NodePath'
`$startInfo.UseShellExecute = `$false
`$startInfo.RedirectStandardInput = `$true
`$startInfo.RedirectStandardOutput = `$true
`$startInfo.RedirectStandardError = `$true
`$startInfo.Arguments = '"$StatusHookScript"'
if (-not `$env:CODEX_HOME) { `$startInfo.Environment['CODEX_HOME'] = '$CodexHome' }
`$startInfo.Environment['NODE_NO_WARNINGS'] = '1'
`$process = [System.Diagnostics.Process]::new()
`$process.StartInfo = `$startInfo
`$null = `$process.Start()
`$stdoutTask = `$process.StandardOutput.ReadToEndAsync()
`$stderrTask = `$process.StandardError.ReadToEndAsync()
`$process.StandardInput.Write(`$stdinPayload)
`$process.StandardInput.Close()
`$process.WaitForExit()
[Console]::Out.Write(`$stdoutTask.Result)
[Console]::Error.Write(`$stderrTask.Result)
exit `$process.ExitCode
"@ | Set-Content -LiteralPath $StatusShimScript -Encoding UTF8

if (Test-Path -LiteralPath $HooksJson) {
  Copy-Item -LiteralPath $HooksJson -Destination "$HooksJson.bak-token-vault-$Stamp" -Force
  $data = Get-Content -LiteralPath $HooksJson -Raw | ConvertFrom-Json
} else {
  $data = [pscustomobject]@{}
}

if (-not $data.PSObject.Properties['hooks']) {
  $data | Add-Member -NotePropertyName hooks -NotePropertyValue ([pscustomobject]@{})
}
if (-not $data.hooks.PSObject.Properties['PostToolUse']) {
  $data.hooks | Add-Member -NotePropertyName PostToolUse -NotePropertyValue @()
}
if (-not $data.hooks.PSObject.Properties['UserPromptSubmit']) {
  $data.hooks | Add-Member -NotePropertyName UserPromptSubmit -NotePropertyValue @()
}

$command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ShimScript`""
$statusCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$StatusShimScript`""
$newEntry = [pscustomobject]@{
  hooks = @([pscustomobject]@{
    type = 'command'
    command = $command
    timeout = 30
    statusMessage = 'Compacting large tool output'
  })
}
$newStatusEntry = [pscustomobject]@{
  hooks = @([pscustomobject]@{
    type = 'command'
    command = $statusCommand
    timeout = 5
    statusMessage = 'Reading token status'
  })
}

$filtered = @()
foreach ($entry in @($data.hooks.PostToolUse)) {
  $json = $entry | ConvertTo-Json -Depth 100 -Compress
  if ($json -notmatch 'codex-token-vault-hook\.mjs|codex-token-vault-windows-shim\.ps1') {
    $filtered += $entry
  }
}
$data.hooks.PostToolUse = @($newEntry) + $filtered

$statusFiltered = @()
foreach ($entry in @($data.hooks.UserPromptSubmit)) {
  $json = $entry | ConvertTo-Json -Depth 100 -Compress
  if ($json -notmatch 'codex-status-hook\.mjs|codex-status-windows-shim\.ps1') {
    $statusFiltered += $entry
  }
}
$data.hooks.UserPromptSubmit = @($newStatusEntry) + $statusFiltered

if (-not $data.PSObject.Properties['state']) {
  $data | Add-Member -NotePropertyName state -NotePropertyValue ([pscustomobject]@{})
}

$allHookTemp = [System.IO.Path]::GetTempFileName()
try {
  @{
    post_tool_use = @($data.hooks.PostToolUse)
    user_prompt_submit = @($data.hooks.UserPromptSubmit)
  } | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $allHookTemp -Encoding UTF8
  $env:CODEX_HOOKS_JSON_PATH = $HooksJson
  $env:ALL_HOOK_TEMP = $allHookTemp
  $hashRowsJson = & node -e @'
const fs = require('fs');
const { createHash } = require('crypto');
const hooksPath = process.env.CODEX_HOOKS_JSON_PATH;
const entriesByEvent = JSON.parse(fs.readFileSync(process.env.ALL_HOOK_TEMP, 'utf8').replace(/^\uFEFF/, ''));
function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalJson(value[key])]));
  }
  return value;
}
function hash(value) {
  return 'sha256:' + createHash('sha256').update(JSON.stringify(canonicalJson(value))).digest('hex');
}
const rows = [];
for (const [eventName, entries] of Object.entries(entriesByEvent)) {
  entries.forEach((entry, groupIndex) => {
    (entry.hooks || []).forEach((hook, handlerIndex) => {
      if (hook.type !== 'command') return;
      const identity = {
        event_name: eventName,
        ...(entry.matcher ? { matcher: entry.matcher } : {}),
        hooks: [{
          type: 'command',
          command: hook.command,
          timeout: Math.max(1, hook.timeout ?? 600),
          async: false,
          ...(hook.statusMessage ? { statusMessage: hook.statusMessage } : {}),
        }],
      };
      rows.push({ key: `${hooksPath}:${eventName}:${groupIndex}:${handlerIndex}`, trusted_hash: hash(identity) });
    });
  });
}
process.stdout.write(JSON.stringify(rows));
'@ 
  $hashRows = $hashRowsJson | ConvertFrom-Json
  foreach ($row in @($hashRows)) {
    if ($data.state.PSObject.Properties[$row.key]) {
      $data.state.($row.key).trusted_hash = $row.trusted_hash
    } else {
      $data.state | Add-Member -NotePropertyName $row.key -NotePropertyValue ([pscustomobject]@{ trusted_hash = $row.trusted_hash })
    }
  }
} finally {
  Remove-Item -LiteralPath $allHookTemp -Force -ErrorAction SilentlyContinue
}
$data | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $HooksJson -Encoding UTF8

$ConfigToml = Join-Path $CodexHome 'config.toml'
if (Test-Path -LiteralPath $ConfigToml) {
  Copy-Item -LiteralPath $ConfigToml -Destination "$ConfigToml.bak-token-vault-trust-$Stamp" -Force
  $configText = Get-Content -LiteralPath $ConfigToml -Raw
  foreach ($prop in $data.state.PSObject.Properties) {
    if ($prop.Name -notmatch 'post_tool_use|user_prompt_submit') { continue }
    $escapedKey = $prop.Name.Replace('\', '\\')
    $section = "[hooks.state.`"$escapedKey`"]"
    $block = "$section`r`ntrusted_hash = `"$($prop.Value.trusted_hash)`""
    $pattern = [regex]::Escape($section) + '\s*trusted_hash = "[^"]+"'
    if ([regex]::IsMatch($configText, $pattern)) {
      $configText = [regex]::Replace($configText, $pattern, $block, 1)
    } else {
      $configText += "`r`n$block`r`n"
    }
  }
  Set-Content -LiteralPath $ConfigToml -Value $configText -Encoding UTF8
}

node --check $HookScript | Out-Null
node --check $StatusHookScript | Out-Null
Write-Output "Installed Codex Token Vault hook:"
Write-Output "  hook: $HookScript"
Write-Output "  status hook: $StatusHookScript"
Write-Output "  shim: $ShimScript"
Write-Output "  status shim: $StatusShimScript"
Write-Output "  vault: $VaultRoot"
Write-Output "  hooks.json: $HooksJson"
Write-Output "Restart Codex Desktop sessions to guarantee hook reload; current session may keep old hook state."
