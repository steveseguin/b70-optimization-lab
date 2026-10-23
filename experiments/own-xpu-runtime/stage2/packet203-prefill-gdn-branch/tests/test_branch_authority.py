"""Synthetic CPU tail/control gates; retained numeric run is never repeated."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[3]
PARENT = P.parent / "packet202-prefill-chunk-prep"
BINARY = P / "build/branch-host-probe"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


class AuthorityTests(unittest.TestCase):
    def test_recorded_authority_bytes(self):
        for path, expected in read(P / "authority-inputs.json")["artifacts_sha256"].items():
            with self.subTest(path=path):
                self.assertEqual(sha(ROOT / path), expected)

    def test_selected_norm_and_projection_identity(self):
        binding = read(P / "production-binding.json")
        self.assertEqual(binding["gated_norm"]["flags"], 8)
        self.assertEqual(binding["gated_norm"]["gain_dtype"], "F32")
        self.assertEqual(binding["gated_norm"]["heads"], 48)
        self.assertEqual(binding["gated_norm"]["width"], 128)
        for key, value in {
            "K": 6144, "rows": 2560, "type": "Q6_K", "variant": 7, "split": 4,
            "expanded_row_bytes": 8112, "raw_row_bytes": 5040,
            "stored_bytes": 20766720, "partial_stride_floats": 8, "live_partial_floats": 4,
        }.items():
            with self.subTest(key=key):
                self.assertEqual(binding["output_projection"][key], value)
        self.assertEqual(binding["production_reference_sha256"], sha(P / "selected_reference.hpp"))
        for path, expected in binding["source_sha256"].items():
            with self.subTest(path=path):
                self.assertEqual(sha(ROOT / path), expected)


class EntryControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BINARY.is_file():
            raise AssertionError("Build the p203 synthetic CPU probe before these tests")
        result = subprocess.run(
            [str(BINARY), "--binding-check"], capture_output=True, text=True,
            env={"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"},
            timeout=10, check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.result = json.loads(result.stdout)
        if cls.result["passed"] is not True:
            raise AssertionError("binding gate did not pass")

    def check_modes(self, name):
        for implementation in ("pair", "serial"):
            with self.subTest(implementation=implementation):
                self.assertIs(self.result["checks"][name + "_" + implementation], True)

    def test_inactive_entry_preserves_all_outputs_and_controls(self):
        self.check_modes("inactive_unchanged")

    def test_sticky_error_entry_preserves_all_outputs_and_controls(self):
        self.check_modes("sticky_error_unchanged")

    def test_invalid_position_sets_error_before_any_tail_write(self):
        self.check_modes("invalid_position_unchanged")

    def test_short_extent_and_real_pointer_alias_refuse(self):
        self.assertIs(self.result["checks"]["short_extent_refused"], True)
        self.assertIs(self.result["checks"]["actual_output_input_alias_refused"], True)

    def test_unknown_cli_refuses_without_numerical_case(self):
        for argv in (("--case", "not-a-case"), ("--binding-check", "extra"), ("--device",)):
            with self.subTest(argv=argv):
                result = subprocess.run(
                    [str(BINARY), *argv], capture_output=True, text=True,
                    env={"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "2"}, timeout=5,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('"passed":true', result.stdout.replace(" ", ""))


class RetainedDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = read(P / "evidence/host-differential.json")
        cls.cases = {case["name"]: case for case in cls.receipt["cases"]}

    def test_build_binary_and_full_dependency_closure(self):
        receipt = self.receipt
        build = read(P / "evidence/build.json")
        self.assertIs(receipt["passed"], True)
        self.assertIs(receipt["device_executed"], False)
        self.assertIs(build["passed"], True)
        self.assertIs(build["synthetic_only"], True)
        self.assertEqual(receipt["binary_sha256"], sha(BINARY))
        self.assertEqual(receipt["binary_sha256"], build["binary_sha256"])
        self.assertEqual(receipt["build_receipt_sha256"], sha(P / "evidence/build.json"))
        self.assertEqual(receipt["source_sha256"], build["source_sha256"])
        self.assertTrue(receipt["source_sha256"])
        for path, expected in receipt["source_sha256"].items():
            with self.subTest(path=path):
                self.assertEqual(sha(ROOT / path), expected)

    def test_every_case_and_intermediate_has_exact_bytes(self):
        expected = {
            "upstream_qkv": 40960, "upstream_z": 24576, "upstream_conv": 40960,
            "upstream_gdn": 24576, "upstream_state": 1572864,
            "gated_norm": 24576, "split_partials": 163840,
            "output_projection": 10240, "stream_injection": 40960,
        }
        self.assertEqual(set(self.cases), {
            "distinct_rows", "identical_rows", "swapped_rows", "bf16_rounding", "nonzero_initial_state",
        })
        self.assertEqual(len(self.receipt["cases"]), 5)
        for name, case in self.cases.items():
            with self.subTest(case=name):
                self.assertIs(case["passed"], True)
                stages = {stage["stage"]: stage for stage in case["comparisons"]}
                self.assertEqual(set(stages), set(expected))
                self.assertEqual(len(stages), len(case["comparisons"]))
                for stage, count in expected.items():
                    result = stages[stage]
                    self.assertEqual(result["bytes"], count, (name, stage))
                    self.assertIs(result["equal"], True, (name, stage))
                    self.assertRegex(result["serial_sha256"], r"^[0-9a-f]{64}$")
                    self.assertEqual(result["serial_sha256"], result["chunk_sha256"], (name, stage))
                    if stage != "split_partials":
                        self.assertIsNone(result["first_mismatch_element"])

    def test_upstream_results_match_frozen_parent_cases(self):
        parent = {case["name"]: case for case in read(PARENT / "evidence/host-differential.json")["cases"]}
        mapping = {"upstream_qkv": "qkv", "upstream_z": "z", "upstream_conv": "conv_output",
                   "upstream_gdn": "gdn_output", "upstream_state": "state_final"}
        for name, case in self.cases.items():
            old = {stage["stage"]: stage for stage in parent[name]["comparisons"]}
            new = {stage["stage"]: stage for stage in case["comparisons"]}
            for current, previous in mapping.items():
                with self.subTest(case=name, stage=current):
                    self.assertEqual(new[current]["serial_sha256"], old[previous]["serial_sha256"])
                    self.assertEqual(new[current]["chunk_sha256"], old[previous]["chunk_sha256"])

    def test_unused_partial_slots_preserve_sentinels(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                self.assertIs(case["partial_sentinel_slots_unchanged"], True)

    def test_z_injection_and_bf16_boundary_negative_controls_discriminate(self):
        for name, case in self.cases.items():
            with self.subTest(case=name):
                final = next(stage["chunk_sha256"] for stage in case["comparisons"]
                             if stage["stage"] == "stream_injection")
                controls = case["negative_controls"]
                for key in ("z_ignored_differs", "stream_injection_ignored_differs",
                            "pre_bf16_injection_differs", "injection_values_changed_differs",
                            "all_eight_injection_streams_changed"):
                    self.assertIs(controls[key], True, (name, key))
                for key in ("wrong_z_streams_sha256", "pre_round_streams_sha256",
                            "wrong_injection_streams_sha256"):
                    self.assertRegex(controls[key], r"^[0-9a-f]{64}$")
                    self.assertNotEqual(controls[key], final, (name, key))


if __name__ == "__main__":
    unittest.main()
