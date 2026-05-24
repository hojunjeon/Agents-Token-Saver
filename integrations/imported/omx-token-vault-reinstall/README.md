# OMX Token Vault reinstall package

Installs the OMX/Codex `PostToolUse` token-vault hook and adds it to `~/.codex/hooks.json` without removing existing hooks.

```bash
tar -xzf omx-token-vault-reinstall.tar.gz
cd omx-token-vault-reinstall
./install.sh
```

Effect: large Codex/OMX tool results are stored under `~/.omx/token-vault/artifacts/` and compact summaries enter context.
