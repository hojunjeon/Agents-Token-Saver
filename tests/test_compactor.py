import unittest
from pathlib import Path

from codex_token_saver.compactor import compact_output, estimate_tokens


ROOT = Path(__file__).resolve().parents[1]


class OutputCompactorTests(unittest.TestCase):
    def test_pytest_output_keeps_failure_facts_and_saves_tokens(self):
        raw = "\n".join(
            [
                "============================= test session starts =============================",
                "platform win32 -- Python 3.11.8, pytest-8.2.0",
                "collected 124 items",
                *[f"tests/test_module_{i}.py ." for i in range(90)],
                "tests/test_auth.py F",
                "================================== FAILURES ===================================",
                "______________________ test_rejects_expired_token ______________________",
                "tests/test_auth.py:42: AssertionError",
                "E       assert 200 == 401",
                "E        +  where 200 = response.status_code",
                "Captured stdout call",
                *[f"verbose debug line {i}: user payload and trace data" for i in range(160)],
                "==================== 1 failed, 123 passed in 12.34s ====================",
            ]
        )

        compact = compact_output(raw, command="python -m pytest -vv")

        self.assertIn("pytest", compact.text)
        self.assertIn("tests/test_auth.py:42", compact.text)
        self.assertIn("assert 200 == 401", compact.text)
        self.assertIn("1 failed, 123 passed", compact.text)
        self.assertGreaterEqual(compact.saving_ratio, 0.85)
        self.assertLess(estimate_tokens(compact.text), estimate_tokens(raw))
        self.assertNotIn("debug line", compact.text)
        self.assertNotIn("omitted", compact.text)

    def test_git_status_compaction_keeps_branch_and_changed_files(self):
        raw = "\n".join(
            [
                "On branch feature/token-saver",
                "Your branch is ahead of 'origin/feature/token-saver' by 2 commits.",
                "",
                "Changes not staged for commit:",
                "  modified:   codex_token_saver/compactor.py",
                "  modified:   README.md",
                "",
                "Untracked files:",
                "  tests/test_compactor.py",
                "  docs/AB_TEST_RESULTS.md",
                "",
                "no changes added to commit (use \"git add\" and/or \"git commit -a\")",
            ]
        )

        compact = compact_output(raw, command="git status")

        self.assertIn("feature/token-saver", compact.text)
        self.assertIn("M codex_token_saver/compactor.py", compact.text)
        self.assertIn("?? tests/test_compactor.py", compact.text)
        self.assertNotIn("Your branch is ahead", compact.text)
        self.assertGreaterEqual(compact.saving_ratio, 0.50)

    def test_fixture_compaction_hits_extreme_codex_savings_floor(self):
        git_raw = (ROOT / "benchmarks" / "fixtures" / "git_status_verbose.txt").read_text(encoding="utf-8")
        pytest_raw = (ROOT / "benchmarks" / "fixtures" / "pytest_failure.txt").read_text(encoding="utf-8")

        git_compact = compact_output(git_raw, command="git status")
        pytest_compact = compact_output(pytest_raw, command="python -m pytest -vv")

        self.assertIn("branch feature/codex-token-saver", git_compact.text)
        self.assertIn("ahead+2", git_compact.text)
        self.assertIn("M codex_token_saver/compactor.py", git_compact.text)
        self.assertRegex(git_compact.text, r"(?m)^\?\? .*skill/codex-token-saver/SKILL\.md")
        self.assertGreaterEqual(git_compact.saving_ratio, 0.50)

        self.assertIn("pytest:", pytest_compact.text)
        self.assertIn("tests/test_auth.py:42", pytest_compact.text)
        self.assertIn("assert 200 == 401", pytest_compact.text)
        self.assertIn("1 failed, 63 passed", pytest_compact.text)
        self.assertGreaterEqual(pytest_compact.saving_ratio, 0.85)


if __name__ == "__main__":
    unittest.main()
