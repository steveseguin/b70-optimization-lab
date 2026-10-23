"""CPU-only tests of the compiled planner; never start a native model owner.

Build the separate synthetic HOST_ONLY probe first. P202_HOST_PROBE may select
that executable explicitly. A missing probe fails rather than skipping gates.
The numeric operator proof belongs to the author's single differential run;
these tests invoke only the bounded --plan branch.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest


PACKET = Path(__file__).resolve().parents[1]
ROOT = PACKET.parents[3]
PROBE = Path(os.environ.get("P202_HOST_PROBE", str(PACKET / "build/layer0-host-probe")))
DIFFERENTIAL = Path(os.environ.get(
    "P202_DIFFERENTIAL_RECEIPT", str(PACKET / "evidence/host-differential.json")
))


class ChunkPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PROBE.is_file() or not os.access(PROBE, os.X_OK):
            raise AssertionError("Build the synthetic p202 HOST_ONLY probe before these gates")

    def invoke(self, start, count, context=4096, width=2):
        return subprocess.run(
            [str(PROBE), "--plan", str(start), str(count), str(context), str(width)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5,
            env={"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"},
            check=False,
        )

    def plan(self, start, count, context=4096, width=2):
        result = self.invoke(start, count, context, width)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["final_position"], count - 1)
        visited = []
        for span in value["spans"]:
            self.assertIs(span["final"], False)
            self.assertIn(span["count"], range(1, width + 1))
            first, last = span["start"], span["start"] + span["count"] - 1
            self.assertEqual(first // 32, last // 32, "chunk crosses an extent boundary")
            self.assertLess(last, count - 1, "final argmax-producing prompt token was chunked")
            visited.extend(range(first, last + 1))
        self.assertEqual(visited, list(range(start, count - 1)), "missing, repeated or reordered prompt token")
        return value

    def refuse(self, *args):
        result = self.invoke(*args)
        self.assertNotEqual(result.returncode, 0, "invalid plan unexpectedly admitted")
        self.assertNotIn('"passed":true', result.stdout.replace(" ", ""))

    def test_single_prompt_has_only_unchanged_final_step(self):
        self.assertEqual(self.plan(0, 1)["spans"], [])

    def test_two_prompt_tokens_leave_one_nonfinal_row(self):
        self.assertEqual(self.plan(0, 2)["spans"], [{"start": 0, "count": 1, "final": False}])

    def test_pair_and_odd_tail_never_consume_final_prompt(self):
        for count in (3, 4, 5, 6, 87):
            with self.subTest(count=count):
                self.plan(0, count)

    def test_split_at_extent_boundary(self):
        self.assertEqual(self.plan(31, 35)["spans"], [
            {"start": 31, "count": 1, "final": False},
            {"start": 32, "count": 2, "final": False},
        ])

    def test_boundary_neighborhoods_have_exact_coverage(self):
        for start, count in ((2, 5), (3, 6), (30, 34), (30, 35), (31, 33), (32, 35), (63, 67)):
            with self.subTest(start=start, count=count):
                self.plan(start, count)

    def test_append_starts_with_saved_pending_token(self):
        value = self.plan(342, 370)
        self.assertEqual(value["spans"][0]["start"], 342)
        self.assertEqual(sum(s["count"] for s in value["spans"]), 27)
        self.assertEqual(value["final_position"], 369)

    def test_append_only_pending_uses_final_step(self):
        self.assertEqual(self.plan(342, 343)["spans"], [])

    def test_width_one_is_a_serial_control(self):
        value = self.plan(29, 37, width=1)
        self.assertTrue(all(s["count"] == 1 for s in value["spans"]))

    def test_last_context_positions_are_bounded(self):
        self.plan(4092, 4096)
        self.assertEqual(self.plan(4095, 4096)["spans"], [])

    def test_empty_and_exhausted_ranges_refuse(self):
        for start, count in ((0, 0), (1, 1), (5, 4), (4096, 4096)):
            with self.subTest(start=start, count=count):
                self.refuse(start, count)

    def test_context_overflow_refuses(self):
        self.refuse(0, 4097, 4096)
        self.refuse(0, 1, 0)
        self.refuse(31, 34, 33)
        self.refuse(0, 87, 4097)

    def test_unadmitted_chunk_width_refuses(self):
        for width in (0, 3, 4, 1024):
            with self.subTest(width=width):
                self.refuse(0, 87, 4096, width)

    def test_invalid_numeric_cli_refuses(self):
        for value in ("-1", "1junk", "184467440737095516160", "nan"):
            with self.subTest(value=value):
                self.refuse(value, 87)

    def test_binding_ranges_and_extents(self):
        result = subprocess.run(
            [str(PROBE), "--binding-check"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=5,
            env={"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "2"}, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertIs(value["passed"], True)
        for name in (
            "partial_write_alias_refused", "read_write_alias_refused",
            "readonly_alias_allowed", "adjacent_allowed", "short_extent_refused",
            "null_refused", "zero_required_refused", "overflow_refused",
            "inactive_unchanged", "sticky_error_unchanged", "invalid_position_unchanged",
        ):
            with self.subTest(name=name):
                self.assertIs(value["checks"][name], True)


class RecordedAuthorityTests(unittest.TestCase):
    def test_production_binding_is_the_recorded_q6_tuple(self):
        binding = json.loads((PACKET / "production-binding.json").read_text())
        for key, expected in {
            "K": 2560, "qkv_rows": 10240, "z_rows": 6144, "type": "Q6_K",
            "grid": 14, "variant": 6, "split": 1, "subgroup": 32,
            "expanded_row_bytes": 3380, "raw_row_bytes": 2100,
        }.items():
            with self.subTest(key=key):
                self.assertEqual(binding["dense"][key], expected)
        self.assertEqual(
            hashlib.sha256((PACKET / "production_reference.hpp").read_bytes()).hexdigest(),
            binding["production_reference_sha256"],
        )

    def test_bound_sources_and_recorded_inputs_are_unchanged(self):
        inventory = json.loads((PACKET / "authority-inputs.json").read_text())
        for relative, expected in {
            **inventory["source_aliases_sha256"], **inventory["artifacts_sha256"]
        }.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_cpu_oracle_prefixes_are_independent_recorded_authority(self):
        inventory = json.loads((PACKET / "authority-inputs.json").read_text())
        rows = {row["name"]: row for row in inventory["recorded_requests"]}
        for oracle in inventory["cpu_oracles"]:
            recorded = json.loads((ROOT / oracle["path"]).read_text())
            device = json.loads((ROOT / rows[oracle["p201_prefix_exact"]]["result"]).read_text())
            self.assertFalse(recorded["device_executed"])
            self.assertEqual(recorded["tokens"], device["tokens"][:128])
            self.assertEqual(len(recorded["steps"]), 128)
            self.assertTrue(all(len(step["logits_bf16_sha256"]) == 64 for step in recorded["steps"]))


class SyntheticDifferentialTests(unittest.TestCase):
    """Validate the author's retained five-case execution without rerunning it."""
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads(DIFFERENTIAL.read_text())
        cls.cases = {case["name"]: case for case in cls.receipt["cases"]}

    def test_result_is_bound_to_current_binary_build_and_complete_sources(self):
        receipt = self.receipt
        self.assertIs(receipt["passed"], True)
        self.assertIs(receipt["device_executed"], False)
        self.assertEqual(receipt["binary_sha256"], hashlib.sha256(PROBE.read_bytes()).hexdigest())
        build_path = PACKET / "evidence/build.json"
        self.assertEqual(receipt["build_receipt_sha256"], hashlib.sha256(build_path.read_bytes()).hexdigest())
        build = json.loads(build_path.read_text())
        self.assertIs(build["passed"], True)
        self.assertIs(build["synthetic_only"], True)
        self.assertEqual(receipt["source_sha256"], build["source_sha256"])
        self.assertEqual(receipt["binary_sha256"], build["binary_sha256"])
        self.assertTrue(receipt["source_sha256"])
        for relative, expected in receipt["source_sha256"].items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)

    def test_all_adversarial_cases_compare_every_intermediate_byte_extent(self):
        fixtures = json.loads((PACKET / "tests/differential-fixtures.json").read_text())
        self.assertEqual(set(self.cases), {case["name"] for case in fixtures["cases"]})
        self.assertEqual(len(self.receipt["cases"]), len(self.cases), "duplicate cases")
        expected_bytes = {
            "qkv": 40960, "z": 24576, "conv_output": 40960,
            "conv_history_after_row0": 61440, "conv_history_final": 61440,
            "gdn_output": 24576, "state_after_row0": 1572864, "state_final": 1572864,
            "round2_reference_output": 24576, "round2_reference_state": 1572864,
        }
        for name, case in self.cases.items():
            with self.subTest(case=name):
                self.assertIs(case["passed"], True)
                comparisons = {item["stage"]: item for item in case["comparisons"]}
                self.assertEqual(set(comparisons), set(expected_bytes))
                self.assertEqual(len(comparisons), len(case["comparisons"]))
                for stage, size in expected_bytes.items():
                    item = comparisons[stage]
                    self.assertIs(item["equal"], True, (name, stage))
                    self.assertIsNone(item["first_mismatch_element"], (name, stage))
                    self.assertEqual(item["bytes"], size, (name, stage))
                    self.assertRegex(item["serial_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(item["serial_sha256"], item["chunk_sha256"], (name, stage))

    def test_state_evolution_and_wrong_state_control_are_observable(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                stages = {item["stage"]: item for item in case["comparisons"]}
                final_state = stages["state_final"]["chunk_sha256"]
                self.assertIs(case["active_state_changed"], True)
                self.assertIs(case["row0_row1_outputs_differ"], True)
                self.assertNotEqual(final_state, case["inputs"]["initial_state_sha256"])
                self.assertNotEqual(final_state, stages["state_after_row0"]["chunk_sha256"])
                negative = case["negative_controls"]
                self.assertIs(negative["independent_state_differs"], True)
                self.assertNotEqual(final_state, negative["wrong_state_sha256"])
        self.assertNotEqual(
            self.cases["distinct_rows"]["inputs"]["activation_sha256"],
            self.cases["swapped_rows"]["inputs"]["activation_sha256"],
        )
        self.assertNotEqual(
            self.cases["distinct_rows"]["inputs"]["initial_state_sha256"],
            self.cases["nonzero_initial_state"]["inputs"]["initial_state_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
