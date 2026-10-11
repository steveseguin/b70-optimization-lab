#!/usr/bin/env python3
"""CPU-only synthetic receipt tests; no runtime process or model access."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("summarise", HERE / "summarise.py")
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="iq3-summary-test-")
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)

    def row(self, repeat=1, prompt="test", decode=20.0, prefill=50.0, output=b"answer\n\n"):
        row = {"id": prompt, "repeat": repeat, "returncode": 0, "failed": False,
               "argv": ["llama-completion", "--device", "SYCL0", "--predict", "64"],
               "stdout_sha256": hashlib.sha256(output).hexdigest(),
               "timings": {"decode": {"count": 63, "count_unit": "runs", "milliseconds": 3150,
                                      "reported_tokens_per_second": decode},
                           "prefill": {"count": 80, "milliseconds": 1600,
                                       "reported_tokens_per_second": prefill}}}
        (self.directory / f"repeat{repeat}-{prompt}.stdout").write_bytes(output)
        return row

    def run_summary(self, rows, comparison=False):
        (self.directory / "runs.json").write_text(json.dumps(rows))
        if comparison:
            (self.directory / "comparison.json").write_text("{}")
        return summary.summarise(self.directory, ["test"])

    def test_complete_equal_repeats_and_medians(self):
        result = self.run_summary([self.row(), self.row(2, decode=30, prefill=60)], True)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["table"][0]["byte_equal"])
        self.assertEqual(result["medians"]["all observed"]["decode"], {"value": 25, "n": 2})
        self.assertEqual(result["medians"]["all observed"]["prefill"]["value"], 55)
        self.assertEqual(result["table"][0]["repeats"][0]["generated_tokens"], 64)

    def test_missing_repeat_is_unassessed_and_partial(self):
        result = self.run_summary([self.row()])
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["table"][0]["byte_equal"])
        self.assertEqual(result["medians"]["repeat2"]["decode"]["n"], 0)

    def test_immediate_eog_preserves_prefill_excludes_decode(self):
        row = self.row(output=b" [end of text]\n\n\n")
        row["timings"].update(decode=None, generated_tokens=0)
        result = self.run_summary([row])
        self.assertEqual(result["table"][0]["repeats"][0]["generated_tokens"], 0)
        self.assertEqual(result["medians"]["repeat1"]["decode"]["n"], 0)
        self.assertEqual(result["medians"]["repeat1"]["prefill"]["n"], 1)

    def test_early_eog_excludes_terminator(self):
        output = b"short answer [end of text]\n\n\n"
        row = self.row(output=output)
        row["timings"]["decode"]["count"] = 7
        self.assertEqual(summary.generated_tokens(row, output), 7)

    def test_short_unknown_end_does_not_invent_generated_count(self):
        row = self.row()
        row["timings"]["decode"]["count"] = 7
        self.assertIsNone(summary.generated_tokens(row, b"short"))

    def test_failed_row_excluded_from_rates_and_equality(self):
        bad = self.row(2, decode=900)
        bad["failed"] = True
        result = self.run_summary([self.row(), bad])
        self.assertEqual(result["medians"]["all observed"]["decode"]["value"], 20)
        self.assertIsNone(result["table"][0]["byte_equal"])

    def test_nonzero_returncode_is_failure(self):
        row = self.row()
        row["returncode"] = 1
        self.assertIsNone(summary.rate(row, "prefill"))

    def test_nonfinite_and_zero_rates_are_excluded(self):
        for value in (float("inf"), float("nan"), 0, -1, None):
            with self.subTest(value=value):
                self.assertIsNone(summary.rate(self.row(decode=value), "decode"))

    def test_missing_or_modified_stdout_never_equal(self):
        rows = [self.row(), self.row(2)]
        output = self.directory / "repeat2-test.stdout"
        output.unlink()
        self.assertIsNone(self.run_summary(rows)["table"][0]["byte_equal"])
        output.write_bytes(b"tampered")
        self.assertIsNone(self.run_summary(rows)["table"][0]["byte_equal"])

    def test_empty_stdout_is_not_a_pass(self):
        rows = [self.row(output=b""), self.row(2, output=b"")]
        self.assertIsNone(self.run_summary(rows)["table"][0]["byte_equal"])

    def test_repeat_mismatch_is_explicit(self):
        result = self.run_summary([self.row(), self.row(2, output=b"different")], True)
        self.assertFalse(result["table"][0]["byte_equal"])
        self.assertIn("repeat mismatch", result["status"])

    def test_fault_label_retains_only_observed_medians(self):
        (self.directory / "FAULT.json").write_text("{}")
        result = self.run_summary([self.row()])
        self.assertEqual(result["status"], "FAULT / partial")
        self.assertIn("pre-fault", summary.render([result]))

    def test_duplicate_and_unknown_rows_refused(self):
        for rows in ([self.row(), self.row()], [self.row(prompt="unknown")]):
            with self.assertRaisesRegex(ValueError, "duplicate or unregistered"):
                self.run_summary(rows)

    def test_missing_runs_and_comparison_not_fabricated_complete(self):
        self.assertEqual(summary.summarise(self.directory, ["test"])["rows"], 0)
        self.assertEqual(self.run_summary([self.row(), self.row(2)])["status"], "partial")

    def test_device_identity_and_no_pooling(self):
        (self.directory / "environment.json").write_text(json.dumps({"ONEAPI_DEVICE_SELECTOR": "level_zero:2"}))
        one = self.run_summary([self.row()])
        two = copy.deepcopy(one)
        two["directory"] = "other-card"
        text = summary.render([one, two])
        self.assertEqual(text.count("| Observed-row median |"), 2)
        self.assertIn("level_zero:2", text)
        self.assertIn("not certified", text)

    def test_cli_multiple_directories_out_and_stdout(self):
        (self.directory / "runs.json").write_text(json.dumps([self.row(prompt="code-review")]))
        command = [sys.executable, "-B", str(HERE / "summarise.py"), str(self.directory), str(self.directory)]
        output = self.directory / "summary.md"
        result = subprocess.run(command + ["--out", str(output)], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "")
        self.assertEqual(output.read_text().count("| Observed-row median |"), 2)
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, output.read_text())


if __name__ == "__main__":
    unittest.main()
