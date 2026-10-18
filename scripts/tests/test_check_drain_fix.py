"""CPU-only fixture checks; never import a packet or touch coordination state."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "check_drain_fix.py"
SPEC = importlib.util.spec_from_file_location("check_drain_fix", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)
FIXTURES = Path(__file__).parent / "fixtures/drain_fix"


class DrainFixTests(unittest.TestCase):
    def test_fixture_classification(self):
        for name, expected in [("fixed", "FIXED"), ("equivalent", "FIXED"),
                               ("unfixed", "UNFIXED"), ("mixed", "UNFIXED"),
                               ("false_clamp", "UNFIXED")]:
            with self.subTest(name=name):
                row = guard.inspect_source((FIXTURES / f"{name}.py").read_text())
                self.assertEqual(row["status"], expected)

    def test_quoted_examples_are_not_sleep_calls(self):
        self.assertIsNone(guard.inspect_source((FIXTURES / "quoted.py").read_text()))

    def test_malformed_or_missing_cooldown_fails_closed(self):
        for source in ("def broken(", "", "sleep(.25)"):
            with self.subTest(source=source):
                self.assertEqual(guard.inspect_source(source, drain_gate=True)["status"], "UNFIXED")

    def test_multiple_sleeps_record_lines(self):
        row = guard.inspect_source((FIXTURES / "mixed.py").read_text())
        self.assertEqual(row["sleeps"], [{"line": 2, "status": "FIXED"},
                                         {"line": 3, "status": "UNFIXED"}])

    def test_other_clock_and_multiline(self):
        row = guard.inspect_source("time.sleep(min(.25, until -\n time.monotonic()))")
        self.assertEqual(row["status"], "UNFIXED")

    def test_shadowed_clamp_cannot_pass(self):
        for source in ("max = min\nsleep(max(0, until - now()))",
                       "def f(max):\n sleep(max(0, until - now()))"):
            with self.subTest(source=source):
                self.assertEqual(guard.inspect_source(source)["status"], "UNFIXED")

    def test_parenthesized_clock_in_alternate_file(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "conditions.py").write_text("sleep(min(.25, until - (now())))")
            report = guard.scan(Path(folder))
            self.assertEqual(report["counts"], {"FIXED": 0, "UNFIXED": 1})

    def test_nested_other_names_ignored_files_and_read_only_scan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "nested/.hidden").mkdir(parents=True)
            (root / ".ignore").write_text("nested/\n")
            shutil.copyfile(FIXTURES / "fixed.py", root / "drain_gate.py")
            shutil.copyfile(FIXTURES / "unfixed.py", root / "nested/.hidden/conditions.py")
            shutil.copyfile(FIXTURES / "equivalent.py", root / "runner")
            shutil.copyfile(FIXTURES / "quoted.py", root / "test_example.py")
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            report = guard.scan(root)
            self.assertEqual(report["counts"], {"FIXED": 2, "UNFIXED": 1})
            self.assertFalse(report["passed"])
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            self.assertTrue(all(len(row["sha256"]) == 64 for row in report["files"]))

    def test_cli_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for fixture, expected in [("fixed", 0), ("unfixed", 1)]:
                shutil.copyfile(FIXTURES / f"{fixture}.py", root / "drain_gate.py")
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), folder, "--json"],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(json.loads(result.stdout)["passed"], expected == 0)
            (root / "drain_gate.py").unlink()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(guard.main([folder]), 2)
                self.assertEqual(guard.main([str(root / "missing")]), 2)

    def test_all_uses_stage2(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copyfile(FIXTURES / "fixed.py", Path(folder) / "drain_gate.py")
            with mock.patch.object(guard, "STAGE2", Path(folder)), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(guard.main(["--all", "--json"]), 0)
            self.assertEqual(json.loads(out.getvalue())["counts"], {"FIXED": 1, "UNFIXED": 0})

    def test_scan_failure_cannot_pass(self):
        with mock.patch.object(guard, "rg_paths", side_effect=OSError("unreadable tree")):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(guard.main([str(FIXTURES)]), 2)


if __name__ == "__main__":
    unittest.main()
