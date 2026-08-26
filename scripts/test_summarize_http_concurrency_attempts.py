import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("summarize-http-concurrency-attempts.py")
SPEC = importlib.util.spec_from_file_location("summary", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class SummaryTests(unittest.TestCase):
    def make_attempt(self, root: Path, values: list[float]) -> Path:
        root.mkdir()
        result = {
            "config": {"oracle_digests_sha256": "abc"},
            "batches": [
                {
                    "concurrency": c,
                    "aggregate_tok_s_wall": value,
                    "oracle_exact_count": c,
                    "oracle_exact_total": c,
                }
                for c, value in zip((1, 2), values)
            ],
        }
        qualification = {
            "classification": "output-isolation-qualified-shape-variant",
            "completion_tokens_128_all": True,
            "cached_tokens_all_zero": True,
            "complete_token_id_identity_all": True,
            "cross_base_oracle_collision_count": 0,
            "latency": [
                {
                    "concurrent_users": c,
                    "queued_profile": c > 1,
                    "ttft_ms_p50": 10.0 * c,
                    "ttft_ms_p95": 12.0 * c,
                    "end_to_end_ms_p50": 100.0 * c,
                    "end_to_end_ms_p95": 120.0 * c,
                }
                for c in (1, 2)
            ],
        }
        (root / "result.json").write_text(json.dumps(result))
        (root / "qualification.json").write_text(json.dumps(qualification))
        return root

    def test_median_and_stability(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = self.make_attempt(root / "a", [10.0, 20.0])
            b = self.make_attempt(root / "b", [10.2, 19.8])
            out = root / "out.json"
            argv = ["summary", "--attempt", str(a), "--attempt", str(b),
                    "--out", str(out), "--label", "test"]
            with mock.patch("sys.argv", argv):
                self.assertEqual(MODULE.main(), 0)
            data = json.loads(out.read_text())
            self.assertEqual(data["classification"], "qualified-output-audited-http-concurrency")
            self.assertAlmostEqual(data["points"][0]["median_aggregate_tok_s"], 10.1)
            self.assertTrue(all(point["stability_passed"] for point in data["points"]))
            self.assertFalse(data["points"][0]["queued_profile"])
            self.assertTrue(data["points"][1]["queued_profile"])
            self.assertEqual(data["points"][1]["latency_ms"]["ttft_ms_p95"]["median"], 24.0)
            self.assertTrue(data["points"][1]["latency_ms"]["ttft_ms_p95"]["stability_passed"])

    def test_failed_stability_returns_three_and_labels_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = self.make_attempt(root / "a", [10.0, 20.0])
            b = self.make_attempt(root / "b", [15.0, 19.8])
            out = root / "out.json"
            argv = ["summary", "--attempt", str(a), "--attempt", str(b),
                    "--out", str(out), "--label", "test"]
            with mock.patch("sys.argv", argv):
                self.assertEqual(MODULE.main(), 3)
            data = json.loads(out.read_text())
            self.assertEqual(data["classification"], "failed-stability-gate")
            self.assertFalse(data["points"][0]["stability_passed"])

    def test_rejects_incomplete_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = self.make_attempt(root / "a", [10.0, 20.0])
            b = self.make_attempt(root / "b", [10.2, 19.8])
            qualification = json.loads((b / "qualification.json").read_text())
            qualification["completion_tokens_128_all"] = False
            (b / "qualification.json").write_text(json.dumps(qualification))
            argv = ["summary", "--attempt", str(a), "--attempt", str(b),
                    "--out", str(root / "out.json"), "--label", "test"]
            with mock.patch("sys.argv", argv):
                with self.assertRaises(SystemExit):
                    MODULE.main()


if __name__ == "__main__":
    unittest.main()
