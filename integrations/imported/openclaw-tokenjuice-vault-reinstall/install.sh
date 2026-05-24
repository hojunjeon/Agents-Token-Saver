#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
OPENCLAW_ROOT="${OPENCLAW_ROOT:-$HOME/openclaw}"
CONFIG="$OPENCLAW_HOME/openclaw.json"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OPENCLAW_HOME/token-vault/artifacts"
if [ ! -d "$OPENCLAW_ROOT/node_modules/tokenjuice/dist" ]; then
  echo "tokenjuice dist not found under $OPENCLAW_ROOT/node_modules/tokenjuice/dist" >&2
  echo "Set OPENCLAW_ROOT=/path/to/openclaw and retry." >&2
  exit 1
fi
for rel in hosts/openclaw/extension.js hosts/shared/tool-result.js core/integrations/compact-bash-result.js; do
  dst="$OPENCLAW_ROOT/node_modules/tokenjuice/dist/$rel"
  src="$ROOT/files/tokenjuice/dist/$rel"
  [ -e "$dst" ] && cp -a "$dst" "$dst.bak-token-vault-$STAMP"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
done
python3 - <<'PY'
import json, os, pathlib, shutil, sys
home = pathlib.Path.home()
config = pathlib.Path(os.environ.get('OPENCLAW_HOME', home/'.openclaw'))/'openclaw.json'
if not config.exists():
    print(f'OpenClaw config not found: {config}', file=sys.stderr); sys.exit(1)
shutil.copy2(config, str(config)+'.bak-token-vault')
data = json.loads(config.read_text())
plugins = data.setdefault('plugins', {}).setdefault('entries', {})
plugins.setdefault('tokenjuice', {})['enabled'] = True
config.write_text(json.dumps(data, indent=2), encoding='utf-8')
print(f'Enabled plugins.entries.tokenjuice in {config}')
PY
if command -v openclaw >/dev/null 2>&1; then openclaw config validate || true; fi
echo "Installed OpenClaw Tokenjuice Vault patches."
echo "Restart OpenClaw Gateway to apply: openclaw gateway restart"
