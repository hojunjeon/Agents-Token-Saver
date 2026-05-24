#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMX_HOME="${OMX_HOME:-$HOME/.omx}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
HOOK="$OMX_HOME/token-vault/bin/omx-token-vault-hook.mjs"
HOOKS_JSON="$CODEX_HOME/hooks.json"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$(dirname "$HOOK")" "$OMX_HOME/token-vault/artifacts" "$CODEX_HOME"
[ -e "$HOOK" ] && cp -a "$HOOK" "$HOOK.bak-$STAMP"
cp "$ROOT/files/omx-token-vault-hook.mjs" "$HOOK"
chmod +x "$HOOK"
node --check "$HOOK"
python3 - <<'PY'
import json, os, pathlib, shutil
home = pathlib.Path.home()
omx_home = pathlib.Path(os.environ.get('OMX_HOME', home/'.omx'))
codex_home = pathlib.Path(os.environ.get('CODEX_HOME', home/'.codex'))
hook = omx_home/'token-vault/bin/omx-token-vault-hook.mjs'
hooks_json = codex_home/'hooks.json'
if hooks_json.exists():
    data = json.loads(hooks_json.read_text())
    shutil.copy2(hooks_json, str(hooks_json)+'.bak-token-vault')
else:
    data = {}
hooks = data.setdefault('hooks', {})
entries = hooks.setdefault('PostToolUse', [])
cmd = f'"/usr/bin/node" "{hook}"'
new_entry = {'hooks':[{'type':'command','command':cmd,'timeout':30,'statusMessage':'Compacting large tool output'}]}
# remove duplicate token-vault entries, then put ours first
filtered=[]
for e in entries:
    if 'omx-token-vault-hook.mjs' not in json.dumps(e):
        filtered.append(e)
hooks['PostToolUse'] = [new_entry] + filtered
hooks_json.write_text(json.dumps(data, indent=2), encoding='utf-8')
print(f'Updated {hooks_json}')
PY
echo "Installed OMX Token Vault hook at $HOOK"
echo "If Codex prompts about hook trust, approve it once, or run your next automation with --dangerously-bypass-hook-trust."
echo "Start a new OMX/Codex session to load the updated hooks."
