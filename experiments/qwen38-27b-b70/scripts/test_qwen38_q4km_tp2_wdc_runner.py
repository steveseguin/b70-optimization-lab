import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/qwen38-27b-b70/scripts/run-20260830-qwen38-q4km-tp2-wdc-http-quality-arm-r1.sh"


class Qwen38Q4kmRunnerTests(unittest.TestCase):
    def test_pilot_generates_its_own_shape_oracle(self) -> None:
        source = RUNNER.read_text()
        self.assertIn(
            'if [[ "${baseline_mode}" == 0 && "${pilot_mode}" == 0 ]]; then',
            source,
        )
        self.assertIn(
            "--pilot-from-batch --oracle-out",
            source,
        )


if __name__ == "__main__":
    unittest.main()
