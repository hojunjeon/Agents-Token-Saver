import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from codex_token_saver.hook import compact_post_tool_use_payload
from codex_token_saver.store import ContextStore


ROOT = Path(__file__).resolve().parents[1]


class CodexHookTests(unittest.TestCase):
    def test_post_tool_use_hook_passes_through_small_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "hook_event_name": "PostToolUse",
                "tool_name": "functions.shell_command",
                "tool_input": {"command": "git status"},
                "tool_response": "short output",
            }

            result = compact_post_tool_use_payload(
                payload,
                ContextStore(Path(tmp) / "ctx.sqlite"),
                threshold_bytes=1000,
            )

            self.assertIsNone(result)

    def test_post_tool_use_hook_captures_large_output_and_returns_codex_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = "\n".join(
                [
                    "============================= test session starts =============================",
                    *[f"tests/test_many_{i}.py ." for i in range(180)],
                    "================================== FAILURES ===================================",
                    "______________________ test_rejects_expired_token ______________________",
                    "tests/test_auth.py:42: AssertionError",
                    "E       assert 200 == 401",
                    "==================== 1 failed, 179 passed in 9.87s ====================",
                ]
            )
            store = ContextStore(Path(tmp) / "ctx.sqlite")

            result = compact_post_tool_use_payload(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "functions.shell_command",
                    "tool_input": {"command": "python -m pytest -vv"},
                    "tool_response": raw,
                },
                store,
                threshold_bytes=1000,
            )

            self.assertIsNotNone(result)
            assert result is not None
            output = result["hookSpecificOutput"]["additionalContext"]
            self.assertFalse(result["continue"])
            self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PostToolUse")
            self.assertIn("_codex_token_saver_hook", output)
            self.assertIn("tests/test_auth.py:42", output)
            self.assertIn("assert 200 == 401", output)
            self.assertIn("ctx://capture/", output)
            self.assertLess(len(output), len(raw) // 2)
            capture_id = int(output.split("ctx://capture/", 1)[1].split()[0])
            self.assertEqual(store.get(capture_id).text, raw)

    def test_post_tool_use_hook_redacts_secret_shaped_values_from_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = "\n".join(
                [
                    "ERROR authorization: Bearer abcdefghijklmnop",
                    "WARNING api_key: sk-super-secret-value-123456",
                    *[f"noise {i}" for i in range(300)],
                ]
            )

            result = compact_post_tool_use_payload(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "functions.shell_command",
                    "tool_input": {"command": "npm run build"},
                    "tool_response": raw,
                },
                ContextStore(Path(tmp) / "ctx.sqlite"),
                threshold_bytes=1000,
            )

            self.assertIsNotNone(result)
            assert result is not None
            output = result["hookSpecificOutput"]["additionalContext"]
            self.assertIn("[REDACTED]", output)
            self.assertNotIn("abcdefghijklmnop", output)
            self.assertNotIn("sk-super-secret-value", output)

    def test_hook_cli_emits_codex_json_for_large_post_tool_use_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = "ERROR failing test\n" + ("line of noise\n" * 2000)
            payload = {
                "hook_event_name": "PostToolUse",
                "tool_name": "functions.shell_command",
                "tool_input": {"command": "python -m pytest -vv"},
                "tool_response": raw,
            }

            proc = subprocess.run(
                [sys.executable, "-m", "codex_token_saver", "hook", "post-tool-use", "--db", str(Path(tmp) / "ctx.sqlite"), "--threshold-bytes", "1000"],
                cwd=ROOT,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=True,
            )

            emitted = json.loads(proc.stdout)
            self.assertFalse(emitted["continue"])
            self.assertIn("_codex_token_saver_hook", emitted["stopReason"])

    def test_hook_cli_fails_open_when_error_logging_path_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = "ERROR failing test\n" + ("line of noise\n" * 2000)
            payload = {
                "hook_event_name": "PostToolUse",
                "tool_name": "functions.shell_command",
                "tool_input": {"command": "python -m pytest -vv"},
                "tool_response": raw,
            }
            unusable_parent = Path(tmp) / "not-a-directory"
            unusable_parent.write_text("file blocks directory creation", encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "codex_token_saver",
                    "hook",
                    "post-tool-use",
                    "--db",
                    str(unusable_parent / "ctx.sqlite"),
                    "--threshold-bytes",
                    "1000",
                ],
                cwd=ROOT,
                input=json.dumps(payload),
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")

    def test_install_hook_writes_windows_shim_and_preserves_existing_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            hooks_json = codex_home / "hooks.json"
            hooks_json.parent.mkdir()
            hooks_json.write_text(
                json.dumps({"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "existing"}]}]}}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, "-m", "codex_token_saver", "install-hook", "--codex-home", str(codex_home), "--db", str(Path(tmp) / "ctx.sqlite")],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            shim = codex_home / "hooks" / "codex-token-saver-post-tool-use.ps1"
            data = json.loads(hooks_json.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for entry in data["hooks"]["PostToolUse"]
                for hook in entry["hooks"]
            ]
            self.assertTrue(shim.exists())
            self.assertIn("hook post-tool-use", shim.read_text(encoding="utf-8"))
            self.assertTrue(any("codex-token-saver-post-tool-use.ps1" in command for command in commands))
            self.assertIn("existing", commands)
            self.assertIn("Installed Codex Token Saver PostToolUse hook", proc.stdout)

    def test_install_hook_writes_codex_trust_state_for_automatic_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            hooks_json = codex_home / "hooks.json"

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "codex_token_saver",
                    "install-hook",
                    "--codex-home",
                    str(codex_home),
                    "--db",
                    str(Path(tmp) / "ctx.sqlite"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            data = json.loads(hooks_json.read_text(encoding="utf-8"))
            key = f"{hooks_json}:post_tool_use:0:0"
            hook = data["hooks"]["PostToolUse"][0]["hooks"][0]
            identity = {
                "event_name": "post_tool_use",
                "hooks": [
                    {
                        "async": False,
                        "command": hook["command"],
                        "statusMessage": hook["statusMessage"],
                        "timeout": hook["timeout"],
                        "type": "command",
                    }
                ],
            }
            expected_hash = "sha256:" + hashlib.sha256(
                json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

            self.assertEqual(data["state"][key]["trusted_hash"], expected_hash)
            config = (codex_home / "config.toml").read_text(encoding="utf-8")
            self.assertIn(f'trusted_hash = "{expected_hash}"', config)
            self.assertIn("post_tool_use:0:0", config)

    def test_windows_installer_registers_hook_from_any_working_directory(self):
        if os.name != "nt":
            self.skipTest("Windows installer regression")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex_home = tmp_path / "codex-home"
            install_root = tmp_path / "install-root"
            foreign_cwd = tmp_path / "foreign-cwd"
            foreign_cwd.mkdir()
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)
            env.pop("PYTHONPATH", None)

            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "install.ps1"),
                    "-InstallRoot",
                    str(install_root),
                ],
                cwd=foreign_cwd,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue((codex_home / "hooks.json").exists())
            self.assertTrue((codex_home / "hooks" / "codex-token-saver-post-tool-use.ps1").exists())


if __name__ == "__main__":
    unittest.main()
