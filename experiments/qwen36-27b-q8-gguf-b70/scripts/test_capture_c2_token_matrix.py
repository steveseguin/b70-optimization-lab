#!/usr/bin/env python3
"""Offline tests for the diagnostic-only compact c2 token matrix."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent


def load_script(filename: str, module_name: str):
    path = SCRIPT_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_script("capture-c2-token-matrix.py", "capture_c2_token_matrix")
WAVE_WRAPPER = SCRIPT_DIR / "run-c2-token-matrix-four-gpu-wave.sh"


def prepared(case_id: str, slot_id: int, prompt_n: int = 4_000) -> dict:
    return {
        "case": {"id": case_id, "calibrated_prompt_tokens": prompt_n},
        "slot_id": slot_id,
        "prompt": f"plain-{case_id}",
        "rendered": f"rendered-{case_id}",
        "payload": {
            "prompt": f"rendered-{case_id}",
            "n_predict": 128,
            "temperature": 0,
            "top_p": 1,
            "seed": 1,
            "cache_prompt": False,
            "return_tokens": True,
            "ignore_eos": True,
            "id_slot": slot_id,
        },
    }


def stream(item: dict, tokens: list[int] | None = None) -> dict:
    token_ids = list(range(10_000, 10_128)) if tokens is None else list(tokens)
    slot_id = item["slot_id"]
    return {
        "token_ids": token_ids,
        "token_offsets_s": [0.1 + index * 0.01 for index in range(len(token_ids))],
        "content": "full streamed content",
        "final": {
            "id_slot": slot_id,
            "stop_type": "limit",
            "truncated": False,
            "timings": {
                "cache_n": 0,
                "predicted_n": 128,
                "prompt_n": item["case"]["calibrated_prompt_tokens"],
            },
        },
        "connected_perf_s": 99.0 + slot_id * 0.001,
        "request_started_perf_s": 100.001 + slot_id * 0.001,
        "request_ended_perf_s": 102.0 + slot_id * 0.001,
        "elapsed_s": 1.999,
    }


def slots_after() -> list[dict]:
    return [
        {
            "id": slot_id,
            "is_processing": False,
            "n_ctx": 32768,
            "n_prompt_tokens_cache": 0,
            "params": {
                "backend_sampling": False,
                "temperature": 0.0,
                "top_p": 1.0,
                "seed": 1,
                "ignore_eos": True,
                "stream": True,
                "n_predict": 128,
            },
        }
        for slot_id in (0, 1)
    ]


def metrics_pair() -> tuple[dict, dict]:
    return (
        {
            "tokens_predicted_total": 0.0,
            "n_decode_total": 0.0,
            "n_busy_slots_per_decode": 0.0,
        },
        {
            "tokens_predicted_total": 256.0,
            "n_decode_total": 140.0,
            "n_busy_slots_per_decode": 1.9,
        },
    )


class StrictScalarTests(unittest.TestCase):
    def test_boolean_token_id_is_not_an_integer(self) -> None:
        self.assertFalse(MODULE.is_json_integer(True))
        self.assertFalse(MODULE.is_token_id_list([1, False, 3], 3))

    def test_boolean_stream_counters_are_rejected(self) -> None:
        item = prepared("case-a", 0)
        for counter, value in (
            ("cache_n", False),
            ("predicted_n", True),
            ("prompt_n", True),
        ):
            with self.subTest(counter=counter):
                candidate = stream(item)
                candidate["final"]["timings"][counter] = value
                fields = MODULE.validate_stream(item, candidate)
                self.assertFalse(fields[
                    {
                        "cache_n": "cache_zero",
                        "predicted_n": "predicted_128",
                        "prompt_n": "prompt_count_exact",
                    }[counter]
                ])

    def test_boolean_metric_counter_is_rejected(self) -> None:
        before, after = metrics_pair()
        for snapshot_name, key in (
            ("before", "tokens_predicted_total"),
            ("after", "n_decode_total"),
            ("after", "n_busy_slots_per_decode"),
        ):
            with self.subTest(snapshot=snapshot_name, key=key):
                candidate_before = copy.deepcopy(before)
                candidate_after = copy.deepcopy(after)
                target = candidate_before if snapshot_name == "before" else candidate_after
                target[key] = True
                result = MODULE.classify_occupancy(candidate_before, candidate_after)
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["numeric_snapshots_valid"])


class PrefixClassificationTests(unittest.TestCase):
    def test_exact_prefix_reports_128_token_lcp(self) -> None:
        tokens = list(range(128))
        result = MODULE.compare_prefix(tokens, list(tokens))
        self.assertTrue(result["comparable"])
        self.assertTrue(result["exact_to_c1"])
        self.assertEqual(result["lcp_tokens"], 128)
        self.assertIsNone(result["first_mismatch"])

    def test_mismatch_is_validly_located(self) -> None:
        expected = list(range(128))
        observed = list(expected)
        observed[37] = 99_999
        result = MODULE.compare_prefix(observed, expected)
        self.assertFalse(result["exact_to_c1"])
        self.assertEqual(result["lcp_tokens"], 37)
        self.assertEqual(
            result["first_mismatch"],
            {
                "index": 37,
                "observed_token_id": 99_999,
                "expected_token_id": 37,
            },
        )


class OccupancyTests(unittest.TestCase):
    def test_two_stream_counters_prove_m2(self) -> None:
        before, after = metrics_pair()
        result = MODULE.classify_occupancy(before, after)
        self.assertTrue(result["passed"])
        self.assertEqual(result["tokens_predicted_delta"], 256)
        self.assertAlmostEqual(result["predicted_tokens_per_llama_decode"], 256 / 140)

    def test_wrong_predicted_count_or_unbatched_ratio_fails(self) -> None:
        before, after = metrics_pair()
        wrong_count = copy.deepcopy(after)
        wrong_count["tokens_predicted_total"] = 355.0
        self.assertFalse(MODULE.classify_occupancy(before, wrong_count)["passed"])
        unbatched = copy.deepcopy(after)
        unbatched["n_decode_total"] = 260.0
        self.assertFalse(MODULE.classify_occupancy(before, unbatched)["passed"])

    def test_fractional_or_impossible_counter_proof_fails(self) -> None:
        before, after = metrics_pair()
        for mutation in ("fractional-total", "ratio-over-two", "busy-over-two"):
            with self.subTest(mutation=mutation):
                candidate_before = copy.deepcopy(before)
                candidate_after = copy.deepcopy(after)
                if mutation == "fractional-total":
                    candidate_before["n_decode_total"] = 0.5
                elif mutation == "ratio-over-two":
                    candidate_after["n_decode_total"] = 1.0
                else:
                    candidate_after["n_busy_slots_per_decode"] = 100.0
                self.assertFalse(
                    MODULE.classify_occupancy(
                        candidate_before, candidate_after
                    )["passed"]
                )

    def test_nonzero_lifetime_baseline_rejects_nonfresh_server(self) -> None:
        before, after = metrics_pair()
        for key, value in (
            ("tokens_predicted_total", 1.0),
            ("n_decode_total", 1.0),
            ("n_busy_slots_per_decode", 1.0),
        ):
            with self.subTest(key=key):
                candidate_before = copy.deepcopy(before)
                candidate_after = copy.deepcopy(after)
                candidate_before[key] = value
                if key == "tokens_predicted_total":
                    candidate_after[key] += value
                elif key == "n_decode_total":
                    candidate_after[key] += value
                result = MODULE.classify_occupancy(
                    candidate_before, candidate_after
                )
                self.assertFalse(result["passed"])
                self.assertFalse(result["fields"]["fresh_server_counters_zero"])


class ScenarioClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.a = prepared("case-a", 1)
        self.b = prepared("case-b", 0)
        self.a_tokens = list(range(20_000, 20_128))
        self.b_tokens = list(range(10_000, 10_128))
        self.oracle = {
            "case-a": {"token_ids": [*self.a_tokens, *range(30_000, 30_384)]},
            "case-b": {"token_ids": [*self.b_tokens, *range(40_000, 40_384)]},
        }
        self.before, self.after = metrics_pair()

    def classify(self, scenario: str, items: list[dict], streams: list[dict]):
        return MODULE.classify_scenario(
            scenario,
            items,
            streams,
            self.oracle,
            self.before,
            self.after,
            100.0,
            [
                {"id": 0, "n_ctx": 32768, "is_processing": False},
                {"id": 1, "n_ctx": 32768, "is_processing": False},
            ],
            slots_after(),
        )

    def test_swap_exact_is_valid_exact_evidence(self) -> None:
        rows = [stream(self.b, self.b_tokens), stream(self.a, self.a_tokens)]
        result = self.classify("swap", [self.b, self.a], rows)
        self.assertTrue(result["evidence_valid"])
        self.assertTrue(result["exact_to_c1"])
        self.assertEqual(result["classification"], "VALID_EXACT_TO_C1")
        self.assertAlmostEqual(result["synchronization"]["request_skew_s"], 0.001)

    def test_forward_exact_is_valid_exact_evidence(self) -> None:
        left = prepared("case-a", 0)
        right = prepared("case-b", 1)
        rows = [stream(left, self.a_tokens), stream(right, self.b_tokens)]
        result = self.classify("forward", [left, right], rows)
        self.assertTrue(result["evidence_valid"])
        self.assertTrue(result["exact_to_c1"])
        self.assertFalse(result["duplicate_equality"]["applicable"])

    def test_token_mismatch_does_not_invalidate_diagnostic_evidence(self) -> None:
        mismatched = list(self.a_tokens)
        mismatched[23] += 1
        rows = [stream(self.b, self.b_tokens), stream(self.a, mismatched)]
        result = self.classify("swap", [self.b, self.a], rows)
        self.assertTrue(result["evidence_valid"])
        self.assertFalse(result["exact_to_c1"])
        self.assertEqual(result["classification"], "VALID_DIVERGENCE_FROM_C1")
        self.assertEqual(
            result["rows"][1]["oracle_prefix_comparison"]["first_mismatch"]["index"],
            23,
        )

    def test_duplicate_b_reports_cross_slot_equality(self) -> None:
        left = prepared("case-b", 0)
        right = prepared("case-b", 1)
        rows = [stream(left, self.b_tokens), stream(right, self.b_tokens)]
        result = self.classify("duplicate-b", [left, right], rows)
        self.assertTrue(result["evidence_valid"])
        self.assertTrue(result["duplicate_equality"]["passed"])
        self.assertTrue(result["exact_to_c1"])

        divergent = list(self.b_tokens)
        divergent[-1] += 1
        rows[1] = stream(right, divergent)
        result = self.classify("duplicate-b", [left, right], rows)
        self.assertTrue(result["evidence_valid"])
        self.assertFalse(result["duplicate_equality"]["passed"])
        self.assertFalse(result["exact_to_c1"])

    def test_duplicate_a_reports_cross_slot_equality(self) -> None:
        left = prepared("case-a", 0)
        right = prepared("case-a", 1)
        rows = [stream(left, self.a_tokens), stream(right, self.a_tokens)]
        result = self.classify("duplicate-a", [left, right], rows)
        self.assertTrue(result["evidence_valid"])
        self.assertTrue(result["duplicate_equality"]["passed"])
        self.assertTrue(result["exact_to_c1"])

    def test_all_scenario_assignments_are_exact(self) -> None:
        cases = [prepared("case-a", 0), prepared("case-b", 1)]
        expected = {
            "swap": ["case-b", "case-a"],
            "duplicate-b": ["case-b", "case-b"],
            "forward": ["case-a", "case-b"],
            "duplicate-a": ["case-a", "case-a"],
        }
        self.assertEqual(set(MODULE.SCENARIO_CASE_INDEXES), set(expected))
        for scenario, case_ids in expected.items():
            with self.subTest(scenario=scenario):
                assigned = [
                    MODULE.assign_slot(cases[index], slot)
                    for slot, index in enumerate(
                        MODULE.SCENARIO_CASE_INDEXES[scenario]
                    )
                ]
                self.assertEqual(
                    [item["case"]["id"] for item in assigned], case_ids
                )
                self.assertEqual([item["slot_id"] for item in assigned], [0, 1])

    def test_missing_tokens_wrong_slot_cache_or_predicted_count_invalidates_evidence(self) -> None:
        for mutation in ("missing", "slot", "cache", "predicted"):
            with self.subTest(mutation=mutation):
                candidate = stream(self.a, self.a_tokens)
                if mutation == "missing":
                    candidate["token_ids"].pop()
                    candidate["token_offsets_s"].pop()
                elif mutation == "slot":
                    candidate["final"]["id_slot"] = 0
                elif mutation == "cache":
                    candidate["final"]["timings"]["cache_n"] = 1
                else:
                    candidate["final"]["timings"]["predicted_n"] = 127
                result = self.classify(
                    "swap",
                    [self.b, self.a],
                    [stream(self.b, self.b_tokens), candidate],
                )
                self.assertFalse(result["evidence_valid"])
                self.assertEqual(result["classification"], "INVALID_EVIDENCE")

    def test_backend_sampling_payload_override_is_rejected(self) -> None:
        item = prepared("case-a", 0)
        self.assertTrue(all(MODULE.validate_payload(item).values()))
        item["payload"]["backend_sampling"] = True
        fields = MODULE.validate_payload(item)
        self.assertFalse(fields["backend_sampling_unchanged"])

    def test_wrong_prompt_or_extra_sampling_field_is_rejected(self) -> None:
        for mutation in ("wrong-prompt", "extra-sampling"):
            with self.subTest(mutation=mutation):
                item = prepared("case-a", 0)
                if mutation == "wrong-prompt":
                    item["payload"]["prompt"] = "same-length-wrong-rendered-value"
                else:
                    item["payload"]["repeat_penalty"] = 2.0
                self.assertFalse(all(MODULE.validate_payload(item).values()))

    def test_duplicate_or_reordered_base_prepared_cases_are_rejected(self) -> None:
        cases = [
            {"id": "case-a", "calibrated_prompt_tokens": 4_000},
            {"id": "case-b", "calibrated_prompt_tokens": 4_100},
        ]
        valid = [prepared("case-a", 0, 4_000), prepared("case-b", 1, 4_100)]
        self.assertTrue(MODULE.validate_base_prepared(valid, cases)["passed"])
        for candidate in (
            [copy.deepcopy(valid[1]), copy.deepcopy(valid[1])],
            list(reversed(copy.deepcopy(valid))),
            [copy.deepcopy(valid[0])],
        ):
            self.assertFalse(MODULE.validate_base_prepared(candidate, cases)["passed"])

    def test_integral_payload_fields_reject_float_or_boolean_aliases(self) -> None:
        for key, value in (("n_predict", 128.0), ("seed", 1.0), ("seed", True)):
            with self.subTest(key=key, value=value):
                item = prepared("case-a", 0)
                item["payload"][key] = value
                self.assertFalse(MODULE.validate_payload(item)["formal_fields_exact"])


class WaveModePlanTests(unittest.TestCase):
    def run_plan(self, mode: str | None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        if mode is None:
            environment.pop("WAVE_MODE", None)
        else:
            environment["WAVE_MODE"] = mode
        return subprocess.run(
            ["bash", str(WAVE_WRAPPER), "--print-wave-plan"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_default_mode_preserves_duplicate_b_swap_plan(self) -> None:
        result = self.run_plan(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "wave_mode=duplicate-b-swap",
                "gpu=0\tscenario=duplicate-b",
                "gpu=1\tscenario=swap",
                "gpu=2\tscenario=duplicate-b",
                "gpu=3\tscenario=swap",
            ],
        )

    def test_alternate_mode_locks_duplicate_a_forward_plan(self) -> None:
        result = self.run_plan("duplicate-a-forward")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "wave_mode=duplicate-a-forward",
                "gpu=0\tscenario=duplicate-a",
                "gpu=1\tscenario=forward",
                "gpu=2\tscenario=duplicate-a",
                "gpu=3\tscenario=forward",
            ],
        )

    def test_unknown_mode_fails_before_wave_work(self) -> None:
        result = self.run_plan("unknown")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("WAVE_MODE must be", result.stderr)

    def test_child_rejects_scenario_outside_locked_mode_before_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run_dir = base / "must-not-exist"
            environment = os.environ.copy()
            environment.update(
                {
                    "WAVE_MODE": "duplicate-a-forward",
                    "GPU_INDEX": "0",
                    "PORT": "19520",
                    "SCENARIO": "forward",
                    "RUN_DIR": str(run_dir),
                    "MODEL_FD": "99",
                    "QWEN36_GPU_LEASE_FD": "98",
                    "QWEN36_PORT_LEASE_FD": "97",
                    "WAVE_RELEASE_FILE": str(base / "release.json"),
                    "WAVE_ABORT_FILE": str(base / "abort"),
                    "ORACLE_SNAPSHOT": str(base / "oracle.json"),
                    "RUNTIME_REFERENCE_REPORT": str(base / "runtime.json"),
                    "MODEL_STAT_BASELINE": str(base / "model-stat.json"),
                }
            )
            result = subprocess.run(
                ["bash", str(WAVE_WRAPPER), "--child"],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("does not match locked wave mode", result.stderr)
            self.assertFalse(run_dir.exists())


class OracleAndInputIntegrityTests(unittest.TestCase):
    def oracle(self) -> tuple[dict, list[dict]]:
        cases = [
            {"id": "case-a", "calibrated_prompt_tokens": 4_000},
            {"id": "case-b", "calibrated_prompt_tokens": 4_100},
        ]
        rows = []
        for slot_id, case in enumerate(cases):
            token_ids = list(range(slot_id * 1_000, slot_id * 1_000 + 512))
            rows.append(
                {
                    "case_id": case["id"],
                    "slot_id": slot_id,
                    "passed": True,
                    "token_ids": token_ids,
                    "token_count": 512,
                    "token_ids_sha256": MODULE.sha256_bytes(
                        json.dumps(token_ids, separators=(",", ":")).encode()
                    ),
                    "prompt_sha256": "a" * 64,
                    "rendered_prompt_sha256": "b" * 64,
                    "content_sha256": "c" * 64,
                }
            )
        oracle = {
            "run_identity": {
                "mode": "sequential-oracle",
                "suite_sha256": "d" * 64,
                "band": "short",
                "model_sha256": "e" * 64,
                "runtime_sha256": "f" * 64,
                "cache_type_k": "f16",
                "cache_type_v": "f16",
                "ctx_size_total": 65536,
                "ctx_size_per_slot": 32768,
                "parallel_slots": 2,
                "max_tokens": 512,
                "ignore_eos": True,
                "seed": 1,
                "cache_prompt": False,
            },
            "intrinsic_gate": {"passed": True},
            "oracle_comparison": {"status": "BASELINE_CAPTURE_READY"},
            "slot_topology": {"passed": True},
            "rows": rows,
        }
        return oracle, cases

    def test_valid_oracle_and_boolean_token_rejection(self) -> None:
        oracle, cases = self.oracle()
        fields, _ = MODULE.validate_oracle(
            oracle, "d" * 64, cases, "e" * 64, "f" * 64
        )
        self.assertTrue(all(fields.values()))
        oracle["rows"][0]["token_ids"][0] = False
        fields, _ = MODULE.validate_oracle(
            oracle, "d" * 64, cases, "e" * 64, "f" * 64
        )
        self.assertFalse(fields["row_structure"])

    def test_input_digest_drift_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            path.write_text("before\n")
            before = MODULE.snapshot_inputs({"input": path})
            after_unchanged = MODULE.snapshot_inputs({"input": path})
            self.assertTrue(
                MODULE.compare_input_snapshots(before, after_unchanged)["passed"]
            )
            path.write_text("after\n")
            after_changed = MODULE.snapshot_inputs({"input": path})
            result = MODULE.compare_input_snapshots(before, after_changed)
            self.assertFalse(result["passed"])
            self.assertFalse(result["labels_exact"]["input"])

    def test_one_key_attestation_maps_are_rejected(self) -> None:
        runtime_sha = "f" * 64
        identity = {
            "llama_server_sha256": runtime_sha,
            "cache_type_k": "f16",
            "cache_type_v": "f16",
            "ctx_size": "65536",
            "ctx_size_per_slot": "32768",
            "parallel_slots": "2",
            "cont_batching": "1",
            "kv_unified": "0",
            "speculation": "none",
            "vision_projector": "none",
        }
        attestation = {
            "passed": True,
            "identity_fields": {"one": True},
            "argv_fields": {"one": True},
            "runtime_fields": {"one": True},
            "observed": {"fit_free_mib": 1814, "minimum_fit_free_mib": 1024},
            "expected_identity": identity,
        }
        fields = MODULE.attest_server(
            attestation, {"server_benchmark_identity": identity}, runtime_sha
        )
        self.assertFalse(all(fields.values()))
        self.assertFalse(fields["identity_fields_complete"])
        self.assertFalse(fields["argv_fields_complete"])
        self.assertFalse(fields["runtime_fields_complete"])

    def test_live_process_continuity_rejects_pid_reuse(self) -> None:
        before = {
            "pid": 1234,
            "process_start_ticks": 100,
            "executable_sha256": "a" * 64,
            "argv_sha256": "b" * 64,
            "passed": True,
        }
        after = copy.deepcopy(before)
        self.assertTrue(MODULE.compare_live_server_bindings(before, after)["passed"])
        after["process_start_ticks"] += 1
        self.assertFalse(MODULE.compare_live_server_bindings(before, after)["passed"])


class MainExitPolicyTests(unittest.TestCase):
    def test_valid_token_divergence_writes_complete_packet_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite_path = root / "suite.json"
            builder_path = root / "builder.py"
            common_path = root / "common.py"
            capture_path = root / "capture.py"
            attestation_path = root / "attestation.json"
            oracle_path = root / "oracle.json"
            output_path = root / "result.json"
            cases = [
                {"id": "case-a", "calibrated_prompt_tokens": 4_000},
                {"id": "case-b", "calibrated_prompt_tokens": 4_100},
            ]
            suite_path.write_text(
                json.dumps({"pairs": [{"band": "short", "cases": cases}]}) + "\n"
            )
            for path in (builder_path, common_path, capture_path):
                path.write_text("# mocked offline fixture\n")
            suite_sha = MODULE.sha256_bytes(suite_path.read_bytes())
            model_sha = "a" * 64
            runtime_sha = "b" * 64
            server_identity = {
                "llama_server_sha256": runtime_sha,
                "cache_type_k": "f16",
                "cache_type_v": "f16",
                "ctx_size": "65536",
                "ctx_size_per_slot": "32768",
                "parallel_slots": "2",
                "cont_batching": "1",
                "kv_unified": "0",
                "speculation": "none",
                "vision_projector": "none",
            }
            base_prepared = [prepared("case-a", 0, 4_000), prepared("case-b", 1, 4_100)]
            a_tokens = list(range(20_000, 20_128))
            b_tokens = list(range(10_000, 10_128))
            oracle_rows = []
            for slot_id, item, prefix in (
                (0, base_prepared[0], a_tokens),
                (1, base_prepared[1], b_tokens),
            ):
                token_ids = [*prefix, *range(50_000 + slot_id * 384, 50_384 + slot_id * 384)]
                oracle_rows.append(
                    {
                        "case_id": item["case"]["id"],
                        "slot_id": slot_id,
                        "passed": True,
                        "token_count": 512,
                        "token_ids": token_ids,
                        "token_ids_sha256": MODULE.sha256_bytes(
                            json.dumps(token_ids, separators=(",", ":")).encode()
                        ),
                        "prompt_sha256": MODULE.sha256_text(item["prompt"]),
                        "rendered_prompt_sha256": MODULE.sha256_text(item["rendered"]),
                        "content_sha256": "c" * 64,
                    }
                )
            oracle = {
                "run_identity": {
                    "mode": "sequential-oracle",
                    "suite_sha256": suite_sha,
                    "band": "short",
                    "model_sha256": model_sha,
                    "runtime_sha256": runtime_sha,
                    "cache_type_k": "f16",
                    "cache_type_v": "f16",
                    "ctx_size_total": 65536,
                    "ctx_size_per_slot": 32768,
                    "parallel_slots": 2,
                    "max_tokens": 512,
                    "ignore_eos": True,
                    "seed": 1,
                    "cache_prompt": False,
                    "server_benchmark_identity": server_identity,
                },
                "intrinsic_gate": {"passed": True},
                "oracle_comparison": {"status": "BASELINE_CAPTURE_READY"},
                "slot_topology": {"passed": True},
                "rows": oracle_rows,
            }
            oracle_path.write_text(json.dumps(oracle) + "\n")
            attestation = {
                "passed": True,
                "identity_fields": {
                    key: True for key in MODULE.REQUIRED_ATTESTATION_IDENTITY_FIELDS
                },
                "argv_fields": {
                    key: True for key in MODULE.REQUIRED_ATTESTATION_ARGV_FIELDS
                },
                "runtime_fields": {
                    key: True for key in MODULE.REQUIRED_ATTESTATION_RUNTIME_FIELDS
                },
                "observed": {
                    "fit_free_mib": 1814,
                    "minimum_fit_free_mib": 1024,
                    "kv_config": [],
                    "offload_pairs": [],
                    "recurrent_config": [],
                    "slot_config": [],
                },
                "expected_identity": server_identity,
            }
            attestation_path.write_text(json.dumps(attestation) + "\n")

            before_1, after_1 = metrics_pair()
            capture = SimpleNamespace(
                prepare_cases=lambda *_args, **_kwargs: copy.deepcopy(base_prepared),
                capture_idle_slots=lambda *_args, **_kwargs: slots_after(),
                capture_metrics=mock.Mock(side_effect=[before_1, after_1]),
            )

            def capture_streams(_mode, _url, items, _common, _timeout):
                outputs = []
                for item in items:
                    tokens = a_tokens if item["case"]["id"] == "case-a" else b_tokens
                    tokens = list(tokens)
                    if item["case"]["id"] == "case-a" and item["slot_id"] == 1:
                        tokens[11] += 1
                    outputs.append(stream(item, tokens))
                return outputs, 100.0

            capture.capture_streams = capture_streams
            argv = [
                str(SCRIPT_DIR / "capture-c2-token-matrix.py"),
                "--scenario",
                "swap",
                "--base-url",
                "http://127.0.0.1:19460",
                "--suite",
                str(suite_path),
                "--prompt-builder",
                str(builder_path),
                "--common-script",
                str(common_path),
                "--capture-script",
                str(capture_path),
                "--server-attestation",
                str(attestation_path),
                "--server-attestation-sha256",
                MODULE.sha256_bytes(attestation_path.read_bytes()),
                "--oracle-json",
                str(oracle_path),
                "--oracle-sha256",
                MODULE.sha256_bytes(oracle_path.read_bytes()),
                "--model-sha256",
                model_sha,
                "--runtime-sha256",
                runtime_sha,
                "--server-pid",
                "1234",
                "--out",
                str(output_path),
            ]
            process_binding = {
                "pid": 1234,
                "process_start_ticks": 999,
                "process_start_epoch_s": 0.0,
                "executable_sha256": runtime_sha,
                "argv_sha256": "d" * 64,
                "passed": True,
            }
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    MODULE,
                    "load_module",
                    side_effect=[
                        SimpleNamespace(),
                        SimpleNamespace(make_prompt=lambda _case: "unused"),
                        capture,
                    ],
                ),
                mock.patch.object(
                    MODULE,
                    "capture_live_server_binding",
                    side_effect=[process_binding, copy.deepcopy(process_binding)],
                ),
            ):
                return_code = MODULE.main()
            result = json.loads(output_path.read_text())
            self.assertEqual(return_code, 0)
            self.assertTrue(result["evidence_valid"])
            self.assertFalse(result["exact_to_c1"])
            self.assertEqual(result["classification"], "VALID_DIVERGENCE_FROM_C1")
            self.assertEqual(result["scenario"]["rows"][1]["content"], "full streamed content")
            self.assertIn("timings", result["scenario"]["rows"][1]["final"])


if __name__ == "__main__":
    unittest.main()
