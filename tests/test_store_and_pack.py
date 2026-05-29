import tempfile
import textwrap
import unittest
from pathlib import Path

from codex_token_saver.packer import ContextPacker
from codex_token_saver.store import ContextStore


class StoreAndPackTests(unittest.TestCase):
    def test_capture_round_trips_raw_text_with_preview_and_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ContextStore(Path(tmp) / "ctx.sqlite")
            raw = "\n".join(f"line {i}: payment retry timeout" for i in range(120))

            capture = store.capture("Bash", raw, command="pytest payment")

            self.assertEqual(store.get(capture.id).text, raw)
            self.assertIn("payment retry", store.preview(capture.id, lines=2))
            hits = store.search("retry timeout")
            self.assertEqual(hits[0].id, capture.id)
            self.assertEqual(hits[0].sha256, capture.sha256)

    def test_context_pack_uses_symbols_and_rehydratable_raw_refs(self):
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
            packer = ContextPacker(root, store)

            pack = packer.build_pack(query="reject expired token", token_budget=220)

            self.assertIn("reject_expired_token", pack.text)
            self.assertIn("ctx://", pack.text)
            self.assertNotIn("TokenVerifier", pack.text)
            self.assertLess(pack.optimized_tokens, pack.baseline_tokens)
            self.assertLessEqual(pack.optimized_tokens, 63)
            self.assertGreaterEqual(pack.anchor_recall, 1.0)
            ref = pack.raw_refs[0]
            self.assertIn("reject_expired_token", store.get(ref.capture_id).text)

    def test_context_pack_deduplicates_repeated_raw_captures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text(
                textwrap.dedent(
                    """
                    def reject_expired_token(response):
                        if response.status_code != 401:
                            raise AssertionError("expired token accepted")
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            store = ContextStore(root / ".codex-token-saver" / "ctx.sqlite")
            packer = ContextPacker(root, store)

            first = packer.build_pack(query="reject expired token", token_budget=160)
            second = packer.build_pack(query="reject expired token", token_budget=160)

            self.assertEqual(first.raw_refs[0].capture_id, second.raw_refs[0].capture_id)


if __name__ == "__main__":
    unittest.main()
