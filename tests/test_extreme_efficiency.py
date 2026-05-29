import shutil
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

from codex_token_saver.ab_test import run_ab_test
from codex_token_saver.packer import ContextPacker
from codex_token_saver.store import ContextStore
from codex_token_saver.watchdog import RequirementWatchdog


ROOT = Path(__file__).resolve().parents[1]


class ExtremeEfficiencyTests(unittest.TestCase):
    def test_symbol_pack_has_no_dead_header_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "auth.py").write_text(
                textwrap.dedent(
                    """
                    class TokenVerifier:
                        def accepts(self, token):
                            return token.expires_at > now()

                    def reject_expired_token(response):
                        if response.status_code != 401:
                            raise AssertionError("expired token accepted")
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text("# sample\n" + "filler\n" * 300, encoding="utf-8")

            store = ContextStore(root / ".codex-token-saver" / "ctx.sqlite")
            pack = ContextPacker(root, store).build_pack("reject expired token", token_budget=220)

            self.assertIn("reject expired token", pack.text)
            self.assertIn("ctx://capture/", pack.text)
            self.assertIn("reject_expired_token", pack.text)
            self.assertNotIn("# CTS", pack.text)
            self.assertNotIn("symbols:", pack.text)
            self.assertLessEqual(pack.optimized_tokens, 37)
            self.assertEqual(pack.anchor_recall, 1.0)
            self.assertIn("reject_expired_token", store.get(pack.raw_refs[0].capture_id).text)

    def test_symbol_pack_recall_ignores_echoed_query_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "math.py").write_text(
                textwrap.dedent(
                    """
                    def compute_total(items):
                        return sum(items)
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            store = ContextStore(root / ".codex-token-saver" / "ctx.sqlite")
            pack = ContextPacker(root, store).build_pack("reject expired token", token_budget=120)

            self.assertIn("q reject expired token", pack.text)
            self.assertIn("compute_total", pack.text)
            self.assertLess(pack.anchor_recall, 1.0)

    def test_fixture_ab_result_beats_previous_extreme_gate(self):
        metrics = run_ab_test(ROOT / "benchmarks" / "fixtures")
        cases = {case["name"]: case for case in metrics["cases"]}

        self.assertGreaterEqual(metrics["overall_saving_ratio"], 0.94)
        self.assertEqual(metrics["anchor_recall"], 1.0)
        self.assertLessEqual(cases["symbol-pack"]["optimized_tokens"], 37)
        self.assertGreaterEqual(cases["git_status_verbose"]["saving_ratio"], 0.50)
        self.assertGreaterEqual(cases["pytest_failure"]["saving_ratio"], 0.85)

    def test_watchdog_enforces_new_extreme_saving_gate(self):
        metrics = run_ab_test(ROOT / "benchmarks" / "fixtures")
        metrics = dict(metrics)
        metrics["overall_saving_ratio"] = 0.939

        report = RequirementWatchdog(ROOT).evaluate(metrics=metrics)
        failed = {gate.name: gate.evidence for gate in report.gates if gate.status == "FAIL"}

        self.assertIn("A/B token saving without anchor loss", failed)
        self.assertIn("94", failed["A/B token saving without anchor loss"])

    def test_watchdog_rejects_anchor_recall_loss(self):
        metrics = run_ab_test(ROOT / "benchmarks" / "fixtures")
        metrics = dict(metrics)
        metrics["anchor_recall"] = 0.99

        report = RequirementWatchdog(ROOT).evaluate(metrics=metrics)
        failed = {gate.name for gate in report.gates if gate.status == "FAIL"}

        self.assertIn("A/B token saving without anchor loss", failed)

    def test_watchdog_rejects_per_case_floor_regressions(self):
        metrics = run_ab_test(ROOT / "benchmarks" / "fixtures")
        metrics = dict(metrics)
        cases = [dict(case) for case in metrics["cases"]]
        cases[0]["saving_ratio"] = 0.49
        metrics["cases"] = cases

        report = RequirementWatchdog(ROOT).evaluate(metrics=metrics)
        failed = {gate.name: gate.evidence for gate in report.gates if gate.status == "FAIL"}

        self.assertIn("per-case Codex savings floors", failed)
        self.assertIn("git_status_verbose", failed["per-case Codex savings floors"])

    def test_watchdog_rejects_ab_runtime_regression(self):
        metrics = run_ab_test(ROOT / "benchmarks" / "fixtures")
        metrics = dict(metrics)
        metrics["elapsed_ms"] = 1001

        report = RequirementWatchdog(ROOT).evaluate(metrics=metrics)
        failed = {gate.name: gate.evidence for gate in report.gates if gate.status == "FAIL"}

        self.assertIn("A/B benchmark runtime", failed)
        self.assertIn("<=1000ms", failed["A/B benchmark runtime"])

    def test_deliverable_omits_research_corpus_from_runtime_package(self):
        self.assertFalse((ROOT / "research").exists())
        self.assertFalse((ROOT / ".context").exists())
        self.assertTrue((ROOT / "codex_token_saver").is_dir())
        self.assertTrue((ROOT / "skill" / "codex-token-saver" / "SKILL.md").exists())
        self.assertTrue((ROOT / "benchmarks" / "fixtures").is_dir())

    def test_windows_zip_omits_generated_and_research_payloads(self):
        zip_path = ROOT / "dist" / "codex-token-saver-windows.zip"

        with zipfile.ZipFile(zip_path) as archive:
            entries = archive.namelist()

        forbidden = ["__pycache__", ".ab/", ".codex-token-saver", ".context", "research/"]
        self.assertFalse(
            [entry for entry in entries if any(term in entry for term in forbidden)],
            "portable zip should only contain source deliverables",
        )


if __name__ == "__main__":
    unittest.main()
