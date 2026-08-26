import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("qualify-openai-concurrency-attempt.py")
SPEC = importlib.util.spec_from_file_location("qualifier", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def response(prompt_id: str, *, raw: bool) -> dict:
    row = {
        "prompt_id": prompt_id,
        "prompt_sha256": "a" * 64,
        "completion_tokens": 128,
        "ttft_s": 0.1,
        "elapsed_s": 1.0,
    }
    if raw:
        row["token_ids"] = list(range(128))
    else:
        row["token_ids_sha256"] = "b" * 64
    return row


def result(*, raw_oracle: bool) -> dict:
    oracle = [response(f"task-c{i:03d}", raw=raw_oracle) for i in range(64)]
    batch_row = response("task-c000", raw=True)
    return {
        "oracle": {"cached_tokens_all_zero": True, "rows": oracle},
        "batches": [{
            "concurrency": 1,
            "aggregate_tok_s_wall": 128.0,
            "cached_tokens_all_zero": True,
            "complete_token_id_identity_all": True,
            "cross_base_oracle_collision_count": 0,
            "rows": [batch_row],
        }],
    }


class QualificationTests(unittest.TestCase):
    def test_raw_pilot_oracle_passes_and_compacts(self) -> None:
        data = result(raw_oracle=True)
        qualified = MODULE.qualify(data, pilot=True, active_slots=4)
        self.assertEqual(qualified["classification"], "qualified-oracle-pilot")
        self.assertTrue(qualified["oracle_raw_token_ids_complete"])
        compact = MODULE.compact_oracle(data)
        self.assertEqual(len(compact["rows"]), 64)
        self.assertRegex(compact["rows"][0]["token_ids_sha256"], r"^[0-9a-f]{64}$")

    def test_compact_frozen_oracle_passes_publication_attempt(self) -> None:
        qualified = MODULE.qualify(
            result(raw_oracle=False), pilot=False, active_slots=4
        )
        self.assertEqual(
            qualified["classification"],
            "output-isolation-qualified-shape-variant",
        )
        self.assertTrue(qualified["oracle_compact_digests_complete"])
        self.assertTrue(qualified["complete_token_id_identity_all"])

    def test_raw_oracle_cannot_substitute_for_frozen_compact_oracle(self) -> None:
        qualified = MODULE.qualify(
            result(raw_oracle=True), pilot=False, active_slots=4
        )
        self.assertEqual(qualified["classification"], "failed-closed")


if __name__ == "__main__":
    unittest.main()
