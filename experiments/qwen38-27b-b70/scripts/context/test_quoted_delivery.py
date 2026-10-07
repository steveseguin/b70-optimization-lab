#!/usr/bin/env python3
"""CPU regressions for the staged quoted-delivery patch; never edits live sources.

Run from any directory with Python 3. The test copies the two harness files to a
temporary tree and applies patches/context-quoted-delivery-validation-20261006.patch
there. It needs the standard library, bash and patch, but no model, server, docker,
clm_harness or litellm. All checker state and shell side effects stay in temporary
directories. Pass --baseline to exercise the same tests against unpatched sources
(the safety regressions should fail).

Scope and remaining limitations:
* Rejecting merged items preserves evidence and order by stopping. It cannot recover
  an item the agent has already overwritten; authenticated capture at delivery time
  is needed for safe automatic recovery and complete retention recall.
* Even ordinary tool turns come from an editable mirror. This patch does not prove
  that their contents equal the original delivery; a canonical delivery store would.
* Quote/amount checks do not verify the meaning of an operation, that a quote belongs
  to its named counter, that every change was supplied, or event ordering. Arithmetic
  is exact for accepted events; task comprehension still requires answer grading.
* Requiring quoted heredocs prevents their shell expansions. The wider command guard
  remains a heuristic, not a general shell sandbox or a complete ban on event files.
* Legacy .done markers are recognized, but missing archive text cannot be recreated.
"""

import ast
import contextlib
import io
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]
REL = Path("experiments/qwen38-27b-b70/scripts/context")
PATCH = ROOT / "patches/context-quoted-delivery-validation-20261006.patch"
BASELINE = "--baseline" in sys.argv
if BASELINE:
    sys.argv.remove("--baseline")


class QuotedDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_tmp = tempfile.TemporaryDirectory(prefix="quoted-source-test-")
        cls.addClassCleanup(cls.source_tmp.cleanup)
        tree = Path(cls.source_tmp.name)
        (tree / REL).mkdir(parents=True)
        for name in ("ctxfold.py", "clm_improved.py"):
            shutil.copyfile(ROOT / REL / name, tree / REL / name)
        if not BASELINE:
            result = subprocess.run(
                ["patch", "--batch", "--forward", "-p1", "-i", str(PATCH)],
                cwd=tree, capture_output=True, text=True,
            )
            if result.returncode:
                raise AssertionError("Staged patch did not apply:\n" + result.stdout + result.stderr)
        cls.source = (tree / REL / "ctxfold.py").read_text()
        # Test the actual standalone-command parser without importing model libraries.
        parsed = ast.parse((tree / REL / "clm_improved.py").read_text())
        nodes = [node for node in parsed.body if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_EVENTS_CMD" for t in node.targets)
        ) or (isinstance(node, ast.FunctionDef) and node.name == "_events_cmd_alone")]
        namespace = {"re": re}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "<event-command-guard>", "exec"), namespace)
        cls.command_alone = staticmethod(namespace["_events_cmd_alone"])

    def setUp(self):
        self.data_tmp = tempfile.TemporaryDirectory(prefix="quoted-data-test-")
        self.addCleanup(self.data_tmp.cleanup)
        self.data = Path(self.data_tmp.name)
        self.ctx = types.ModuleType("ctxfold_under_test")
        exec(compile(self.source, "<ctxfold-under-test>", "exec"), self.ctx.__dict__)
        self.ctx.MIRROR = str(self.data / "mirror")
        self.ctx.STATE = str(self.data / "state")
        self.ctx.ARCH = str(self.data / "archive")
        Path(self.ctx.ARCH).mkdir()
        (Path(self.ctx.ARCH) / ".on").touch()

    def run_events(self, mirror, state, events):
        Path(self.ctx.MIRROR).write_text(mirror)
        Path(self.ctx.STATE).write_text(state)
        output = io.StringIO()
        code = 0
        with patch.object(sys, "stdin", io.StringIO(events)), contextlib.redirect_stdout(output):
            try:
                self.ctx.events({"GET", "QUERY"})
            except SystemExit as exc:
                code = exc.code
        return code, output.getvalue()

    @staticmethod
    def turn(number, body, role="tool", prefix=""):
        return f"[[CTX_TURN {number} role={role}]]\n{prefix}ITEM {number}/4 (UPDATE)\n{body}\n"

    def assert_unchanged(self, mirror, state):
        self.assertEqual(Path(self.ctx.MIRROR).read_text(), mirror)
        self.assertEqual(Path(self.ctx.STATE).read_text(), state)
        self.assertEqual(sorted(p.name for p in Path(self.ctx.ARCH).iterdir()), [".on"])

    def test_valid_ordered_events_apply_and_archive(self):
        first, second = "abcd12 was set to 10.", "abcd12 went up by 5."
        code, output = self.run_events(
            self.turn(1, first) + self.turn(2, second), "abcd12 0\n",
            f'abcd12 | set | 10 | "{first}"\nabcd12 | add | 5 | "{second}"\n',
        )
        self.assertEqual(code, 0, output)
        self.assertEqual(Path(self.ctx.STATE).read_text(), "abcd12 15\n")
        self.assertEqual(Path(self.ctx.MIRROR).read_text(), "")
        self.assertEqual((Path(self.ctx.ARCH) / "item-001.txt").read_text(), first + "\n")
        self.assertEqual((Path(self.ctx.ARCH) / "item-002.txt").read_text(), second + "\n")

    def test_fabricated_merged_item_is_rejected_without_losing_evidence(self):
        sentence = "abcd12 was set to 999."
        mirror = self.turn(1, sentence, role="assistant", prefix="My reconstructed notes:\n")
        state = "abcd12 10\n"
        code, output = self.run_events(mirror, state, f'abcd12 | set | 999 | "{sentence}"\n')
        self.assertEqual(code, 2, output)
        self.assertIn("REFUSED (unverified item)", output)
        self.assert_unchanged(mirror, state)

    def test_merged_earlier_item_blocks_a_later_normal_item(self):
        first, second = "abcd12 was set to 10.", "abcd12 went up by 5."
        mirror = self.turn(1, first, role="user", prefix="Compacted notes:\n") + self.turn(2, second)
        state = "abcd12 0\n"
        code, output = self.run_events(mirror, state, f'abcd12 | add | 5 | "{second}"\n')
        self.assertEqual(code, 2, output)
        self.assertIn("REFUSED (unverified item)", output)
        self.assert_unchanged(mirror, state)

    def test_prefixed_tool_item_is_also_unverified(self):
        sentence = "abcd12 was set to 10."
        mirror = self.turn(1, sentence, prefix="An edited tool turn:\n")
        state = "abcd12 0\n"
        code, output = self.run_events(mirror, state, f'abcd12 | set | 10 | "{sentence}"\n')
        self.assertEqual(code, 2, output)
        self.assert_unchanged(mirror, state)

    def test_already_archived_copy_does_not_block_new_delivery(self):
        first, second = "abcd12 was set to 10.", "abcd12 went up by 5."
        archived = Path(self.ctx.ARCH) / "item-001.txt"
        archived.write_text(first + "\n")
        old_note = self.turn(1, first, role="user", prefix="Old notes:\n")
        code, output = self.run_events(old_note + self.turn(2, second), "abcd12 10\n",
                                       f'abcd12 | add | 5 | "{second}"\n')
        self.assertEqual(code, 0, output)
        self.assertEqual(Path(self.ctx.STATE).read_text(), "abcd12 15\n")
        self.assertEqual(Path(self.ctx.MIRROR).read_text(), old_note)
        self.assertEqual(archived.read_text(), first + "\n")

    def test_bad_quote_refuses_whole_list(self):
        mirror = self.turn(1, "abcd12 was set to 10. efgh34 was set to 20.")
        state = ""
        code, output = self.run_events(mirror, state,
            'abcd12 | reopen | 10 | "abcd12 was set to 10."\n'
            'efgh34 | reopen | 20 | "efgh34 was set to 999."\n')
        self.assertEqual(code, 2, output)
        self.assertIn("REFUSED (bad quote)", output)
        self.assert_unchanged(mirror, state)

    def test_unquoted_heredoc_with_command_substitution_is_rejected(self):
        self.assertFalse(self.command_alone("ctxfold --events <<EOF\n$(printf altered)\nnone\nEOF"))

    def test_quoted_heredoc_keeps_shell_substitution_literal(self):
        marker = self.data / "unexpected-write"
        body = f"$(printf altered > {marker})"
        for delimiter in ("'EOF'", '"EOF"'):
            with self.subTest(delimiter=delimiter):
                command = f"ctxfold --events <<{delimiter}\n{body}\nEOF"
                self.assertTrue(self.command_alone(command))
                result = subprocess.run(["bash", "-c", "ctxfold() { cat; }\n" + command],
                                        capture_output=True, text=True, check=True)
                self.assertEqual(result.stdout, body + "\n")
                self.assertFalse(marker.exists())

    def test_commands_after_heredoc_are_rejected(self):
        self.assertFalse(self.command_alone("ctxfold --events <<'EOF'\nnone\nEOF\nprintf altered"))
        self.assertFalse(self.command_alone("ctxfold --events <<'EOF'\nnone\nEOF\nprintf altered\nEOF"))


if __name__ == "__main__":
    unittest.main()
