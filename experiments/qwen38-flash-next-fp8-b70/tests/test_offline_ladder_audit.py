import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "audit", Path(__file__).resolve().parents[1] / "tools/audit-depth-ladder-offline.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run, self.sup, self.ref = [Path(self.tmp.name) / n for n in ("run", "sup", "ref")]
        for p in (self.run, self.sup, self.ref):
            p.mkdir()
        self.rows = {"2k": [{"row": i, "status": "passed", "output_token_ids_sha256": "a" * 64} for i in (1, 2)]}
        for p in (self.run, self.ref):
            (p / "depth-ladder.json").write_text(json.dumps(self.rows))
        for i in (1, 2):
            (self.run / f"exact-depth-2k-r{i}.rc").write_text("0\n")

    def audit(self):
        return module.audit(self.run, self.sup, self.ref, ["2k"], 2)

    def test_passing_rows_do_not_hide_failed_teardown(self):
        (self.sup / "final.rc").write_text("143\n")
        (self.sup / "xpu-discovery.err").write_text("bypassed: cached receipt from attempt 146")
        out = self.audit()
        self.assertTrue(out["row_summary_comparison_passed"])
        self.assertTrue(out["cached_gpu_receipts_detected"])
        self.assertEqual(out["teardown_status"], "nonzero_exit")
        self.assertEqual(out["device_health"], "unverified")

    def test_missing_exit_receipt_fails(self):
        (self.run / "exact-depth-2k-r2.rc").unlink()
        self.assertFalse(self.audit()["row_summary_comparison_passed"])

    def test_mismatched_output_fails(self):
        self.rows["2k"][1]["output_token_ids_sha256"] = "b" * 64
        (self.run / "depth-ladder.json").write_text(json.dumps(self.rows))
        self.assertFalse(self.audit()["row_summary_comparison_passed"])

    def test_truncated_summary_fails(self):
        (self.run / "depth-ladder.json").write_text("{")
        self.assertFalse(self.audit()["row_summary_comparison_passed"])

    def test_zero_exit_cannot_certify_health(self):
        (self.sup / "final.rc").write_text("0\n")
        self.assertEqual(self.audit()["teardown_status"], "unverified")


if __name__ == "__main__":
    unittest.main()
