# OpenClaw Tokenjuice Vault reinstall package

Re-applies the OpenClaw Tokenjuice Vault patches and enables `plugins.entries.tokenjuice` in `~/.openclaw/openclaw.json`.

```bash
tar -xzf openclaw-tokenjuice-vault-reinstall.tar.gz
cd openclaw-tokenjuice-vault-reinstall
./install.sh
```

If OpenClaw source is not at `~/openclaw`, set:

```bash
OPENCLAW_ROOT=/path/to/openclaw ./install.sh
```

Effect: large OpenClaw shell/tool results are stored under `~/.openclaw/token-vault/artifacts/` and compact summaries enter context.
