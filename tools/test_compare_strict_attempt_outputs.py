import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare-strict-attempt-outputs.py"


class StrictAttemptComparisonTest(unittest.TestCase):
    def write_attempt(self, root: Path, attempt: str, token_ids: list[int]) -> None:
        root.mkdir()
        (root / "campaign-identity.json").write_text(
            json.dumps({"profile": "test", "attempt": attempt, "suite_sha256": "a" * 64})
        )
        (root / "performance.json").write_text(
            json.dumps(
                {
                    "rows": [{"prompt_id": "one", "token_ids": token_ids}],
                    "summary": {
                        "class_balanced_tok_s_1_100_intervals_after_ttft": {"median": 1.0}
                    },
                    "realistic_final_gate": {"passed": True},
                    "fresh_response_validity": {
                        "valid": True,
                        "cached_tokens_all_zero": True,
                    },
                }
            )
        )
        (root / "canaries.json").write_text(json.dumps({"pass_all": True}))

    def test_exact_and_divergent_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            left = tmp_path / "left"
            exact = tmp_path / "exact"
            different = tmp_path / "different"
            self.write_attempt(left, "a", [1, 2, 3])
            self.write_attempt(exact, "b", [1, 2, 3])
            self.write_attempt(different, "c", [1, 9, 3])

            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(left), str(exact)],
                check=True,
                capture_output=True,
                text=True,
            )
            value = json.loads(result.stdout)
            self.assertTrue(value["qualification"]["strict_pair_qualified"])

            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(left), str(different)],
                check=True,
                capture_output=True,
                text=True,
            )
            value = json.loads(result.stdout)
            self.assertFalse(value["qualification"]["strict_pair_qualified"])
            self.assertEqual(
                value["comparison"]["divergent_prompts"][0][
                    "first_divergence_token_zero_based"
                ],
                1,
            )

    def test_output_is_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            left = tmp_path / "left"
            right = tmp_path / "right"
            output = tmp_path / "result.json"
            self.write_attempt(left, "a", [1])
            self.write_attempt(right, "b", [1])
            output.write_text("preserve")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(left), str(right), "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
