import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/qwen38-27b-b70/scripts/run-20260827-qwen38-q4km-q4mtp-tp1-screen-attempt.sh"
PREREG = ROOT / "experiments/qwen38-27b-b70/data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-screen-r1-prereg.json"


class ContractTest(unittest.TestCase):
    def test_tp1_default_is_preserved(self) -> None:
        text = RUNNER.read_text()
        self.assertIn("tp_size=${TP_SIZE:-1}", text)
        self.assertIn("prereg=${PREREG:-", text)
        self.assertIn("batch_size=${BATCH_SIZE:-2048}", text)
        self.assertIn("ubatch_size=${UBATCH_SIZE:-512}", text)

    def test_tp2_has_two_locks_and_equal_target_split(self) -> None:
        text = RUNNER.read_text()
        for marker in (
            "exec 10>/tmp/b70-gpu1.lock",
            "ONEAPI_DEVICE_SELECTOR=level_zero:1,0",
            "--device SYCL0,SYCL1 --split-mode tensor --tensor-split 1,1",
            "--device-draft SYCL0",
            'LD_LIBRARY_PATH="${build_dir}/bin',
        ):
            self.assertIn(marker, text)

    def test_prereg_is_fail_closed_and_nonpromotional(self) -> None:
        payload = json.loads(PREREG.read_text())
        self.assertEqual(payload["contract"]["mtp_depths"], [0, 2])
        self.assertEqual(payload["pass_gate"]["complete_candidate_arrays_equal_oracle"], "12/12")
        self.assertTrue(payload["interpretation"]["failure_stops_campaign"])
        self.assertFalse(payload["interpretation"]["promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
