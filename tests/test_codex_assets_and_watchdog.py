import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_token_saver.ab_test import run_ab_test
from codex_token_saver.watchdog import RequirementWatchdog


ROOT = Path(__file__).resolve().parents[1]


class CodexAssetsAndWatchdogTests(unittest.TestCase):
    def test_codex_skill_and_one_click_installer_assets_exist(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (ROOT / "skill" / "codex-token-saver" / "SKILL.md").read_text(encoding="utf-8")
        agent = ROOT / "skill" / "codex-token-saver" / "agents" / "requirement-watchdog.md"
        agent_text = agent.read_text(encoding="utf-8") if agent.exists() else ""

        self.assertIn("One-click Windows install", readme)
        self.assertIn("install.bat", readme)
        self.assertIn("AGENTS.md", readme)
        self.assertIn("name: codex-token-saver", skill)
        self.assertIn("Codex", skill)
        self.assertIn("requirement-watchdog.md", skill)
        self.assertIn("cts watchdog --run-tests --until-pass", agent_text)
        self.assertIn("94%", agent_text)
        self.assertIn("anchor recall 100%", agent_text)
        self.assertTrue((ROOT / "install.bat").exists())
        self.assertTrue((ROOT / "install.ps1").exists())

    def test_cli_ab_test_outputs_machine_readable_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ab.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "codex_token_saver",
                    "ab-test",
                    "--fixtures",
                    str(ROOT / "benchmarks" / "fixtures"),
                    "--json",
                    str(out),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )

            metrics = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("overall_saving_ratio", metrics)
            self.assertGreaterEqual(metrics["overall_saving_ratio"], 0.94)
            self.assertEqual(metrics["anchor_recall"], 1.0)
            floors = {case["name"]: case["saving_ratio"] for case in metrics["cases"]}
            self.assertGreaterEqual(floors["git_status_verbose"], 0.50)
            self.assertGreaterEqual(floors["pytest_failure"], 0.85)
            self.assertGreaterEqual(floors["symbol-pack"], 0.95)
            self.assertIn("PASS", proc.stdout)

    def test_requirement_watchdog_passes_release_gates(self):
        metrics = run_ab_test(ROOT / "benchmarks" / "fixtures")
        report = RequirementWatchdog(ROOT).evaluate(metrics=metrics)

        failed = [gate for gate in report.gates if gate.status != "PASS"]
        self.assertEqual([], failed, report.to_markdown())
        self.assertIn("Codex", report.to_markdown())
        self.assertIn("A/B", report.to_markdown())
        self.assertIn("per-case Codex savings floors", report.to_markdown())
        self.assertIn("requirement watchdog subagent", report.to_markdown())


if __name__ == "__main__":
    unittest.main()
