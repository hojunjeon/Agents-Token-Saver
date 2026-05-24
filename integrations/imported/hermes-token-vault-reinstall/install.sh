#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/token-vault"
CONFIG="$HERMES_HOME/config.yaml"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$HERMES_HOME/plugins" "$HERMES_HOME/token-vault/artifacts"
if [ -e "$PLUGIN_DIR" ]; then cp -a "$PLUGIN_DIR" "$PLUGIN_DIR.bak-$STAMP"; fi
rm -rf "$PLUGIN_DIR"
cp -a "$ROOT/files/token-vault" "$PLUGIN_DIR"
python3 - <<'PY'
import os, pathlib, sys
try:
    import yaml
except Exception as e:
    print('PyYAML is required to edit Hermes config:', e, file=sys.stderr); sys.exit(1)
config = pathlib.Path(os.environ.get('HERMES_HOME', pathlib.Path.home()/'.hermes'))/'config.yaml'
if config.exists():
    data = yaml.safe_load(config.read_text()) or {}
else:
    data = {}
plugins = data.setdefault('plugins', {})
enabled = plugins.setdefault('enabled', [])
if not isinstance(enabled, list):
    enabled = plugins['enabled'] = []
if 'token-vault' not in enabled:
    enabled.append('token-vault')
config.parent.mkdir(parents=True, exist_ok=True)
config.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding='utf-8')
PY
python3 -m py_compile "$PLUGIN_DIR/__init__.py"
echo "Installed Hermes Token Vault at $PLUGIN_DIR"
echo "Restart Hermes/gateway or start a new session to load it."
