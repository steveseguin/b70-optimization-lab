import hashlib
import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "bench-openai-concurrency-oracle.py"
SPEC = importlib.util.spec_from_file_location("bench_openai_concurrency_oracle", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(prompt_id: str, prompt: str) -> dict[str, str]:
    return {
        "prompt_id": prompt_id,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }


class SelectPinnedOracleRowsTests(unittest.TestCase):
    def test_accepts_exact_prefix_from_larger_frozen_oracle(self) -> None:
        prompts = [{"id": "a", "prompt": "alpha"}, {"id": "b", "prompt": "beta"}]
        frozen = [row("a", "alpha"), row("b", "beta"), row("c", "gamma")]
        self.assertEqual(
            [item["prompt_id"] for item in MODULE.select_pinned_oracle_rows(frozen, prompts)],
            ["a", "b"],
        )

    def test_rejects_changed_prompt(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact expanded suite"):
            MODULE.select_pinned_oracle_rows(
                [row("a", "different")], [{"id": "a", "prompt": "alpha"}]
            )

    def test_rejects_missing_prompt(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact expanded suite"):
            MODULE.select_pinned_oracle_rows([], [{"id": "a", "prompt": "alpha"}])

    def test_rejects_duplicate_prompt_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate prompt_id"):
            MODULE.select_pinned_oracle_rows(
                [row("a", "alpha"), row("a", "alpha")],
                [{"id": "a", "prompt": "alpha"}],
            )


if __name__ == "__main__":
    unittest.main()
