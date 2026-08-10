#!/usr/bin/env python3
"""Adversarial offline tests for the canonical-Q8 c2 crossover study."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


SCRIPT = Path(__file__).with_name("canonical-q8-c2-crossover-study.py")
RUNNER = Path(__file__).with_name("run-canonical-q8-c2-crossover-four-gpu-wave.sh")
FROZEN_RUNNER_SHA256 = (
    "22863f08d545b675a18aa90ebf0097ffdbfcf792247c997aa25e521803cf176a"
)


def load_study() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "canonical_q8_c2_crossover_study", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load crossover study")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUDY = load_study()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flat_marker() -> str:
    return (
        f"{STUDY.MARKER} first-hit: layout=flat "
        "path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
        "src0=blk.0.attn_qkv.weight src0_ne=[5120,10240,1,1] "
        "src1_ne=[5120,2,1,1] dst_ne=[10240,2,1,1]"
    )


def recurrent_marker() -> str:
    return (
        f"{STUDY.MARKER} first-hit: layout=recurrent "
        "path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
        "src0=blk.0.ssm_out.weight src0_ne=[6144,5120,1,1] "
        "src1_ne=[6144,1,2,1] dst_ne=[5120,1,2,1]"
    )


def process_line(pid: str = "123") -> str:
    return f"{STUDY.PROCESS_BINDING} pid={pid}"


def canonical_argv(port: int = 19720) -> list[str]:
    gpu = port - 19720
    return [
        "/mnt/fast-ai/runtime/llama.cpp-15586e2d-q8-c2-canonical-109eee6f-hybrid/llama-server",
        "-m",
        "/proc/self/fd/18",
        "--alias",
        "qwen36-27b-q8_0-target-only",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-dev",
        f"SYCL{gpu}",
        "-ngl",
        "99",
        "-c",
        "65536",
        "-np",
        "2",
        "-b",
        "1024",
        "-ub",
        "128",
        "-t",
        "8",
        "--threads-http",
        "6",
        "--poll",
        "50",
        "-lv",
        "4",
        "-ctk",
        "f16",
        "-ctv",
        "f16",
        "-fa",
        "on",
        "--spec-type",
        "none",
        "--reasoning",
        "off",
        "--ctx-checkpoints",
        "0",
        "--cache-ram",
        "0",
        "--no-cache-idle-slots",
        "--no-context-shift",
        "--slots",
        "--metrics",
        "--jinja",
        "--no-kv-unified",
        "--cont-batching",
    ]


def lane_outcomes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for plan in STUDY.PLAN:
        rows.append(
            {
                "plan": dict(plan),
                "full_exact": plan["selector"] == 1,
                "landmark_reproduced": plan["selector"] == 0,
                "quality_regression": False,
            }
        )
    return rows


class PlanTests(unittest.TestCase):
    def test_plan_is_balanced_same_card_crossover(self) -> None:
        self.assertEqual(len(STUDY.PLAN), 8)
        for gpu in range(4):
            rows = [row for row in STUDY.PLAN if row["gpu_index"] == gpu]
            self.assertEqual([row["wave"] for row in rows], [1, 2])
            self.assertEqual({row["selector"] for row in rows}, {0, 1})
            self.assertEqual(len({row["scenario"] for row in rows}), 1)
        for wave in (1, 2):
            rows = [row for row in STUDY.PLAN if row["wave"] == wave]
            self.assertEqual(sum(row["selector"] for row in rows), 2)

    def test_print_plan_is_read_only_and_exact(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT), "print-plan", "--port-base", "19720"],
            check=True,
            text=True,
            capture_output=True,
        )
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 8)
        self.assertIn("wave=1\tgpu=0\tscenario=forward\tselector=0", lines[0])
        self.assertIn("wave=2\tgpu=3\tscenario=reverse\tselector=0", lines[-1])
        self.assertTrue(all("forced_tokens=512" in line for line in lines))
        self.assertTrue(all("server_sleep=disabled" in line for line in lines))

    def test_sleep_option_absence_rejects_split_and_equals_forms(self) -> None:
        self.assertTrue(
            STUDY.argv_option_absent(
                ["llama-server", "-c", "65536"], "--sleep-idle-seconds"
            )
        )
        self.assertFalse(
            STUDY.argv_option_absent(
                ["llama-server", "--sleep-idle-seconds", "60"], "--sleep-idle-seconds"
            )
        )
        self.assertFalse(
            STUDY.argv_option_absent(
                ["llama-server", "--sleep-idle-seconds=60"], "--sleep-idle-seconds"
            )
        )


class OccupancyTests(unittest.TestCase):
    def valid(self) -> tuple[dict[str, float], dict[str, float]]:
        return (
            {
                "tokens_predicted_total": 0.0,
                "n_decode_total": 0.0,
                "n_busy_slots_per_decode": 0.0,
            },
            {
                "tokens_predicted_total": 1024.0,
                "n_decode_total": 520.0,
                "n_busy_slots_per_decode": 1.99,
            },
        )

    def test_valid_full512_m2_occupancy(self) -> None:
        before, after = self.valid()
        result = STUDY.classify_occupancy(before, after)
        self.assertTrue(result["passed"], result["fields"])

    def test_impossible_one_decode_counter_fails(self) -> None:
        before, after = self.valid()
        after["n_decode_total"] = 1.0
        result = STUDY.classify_occupancy(before, after)
        self.assertFalse(result["fields"]["decode_delta_full512_floor"])
        self.assertFalse(result["fields"]["ratio_proves_m2"])

    def test_fractional_and_nonmonotonic_counters_fail(self) -> None:
        before, after = self.valid()
        after["n_decode_total"] = 519.5
        self.assertFalse(
            STUDY.classify_occupancy(before, after)["fields"]["integral_counters_valid"]
        )
        before, after = self.valid()
        before["n_decode_total"] = 600.0
        self.assertFalse(
            STUDY.classify_occupancy(before, after)["fields"]["fresh_counters_zero"]
        )
        self.assertFalse(
            STUDY.classify_occupancy(before, after)["fields"]["counters_monotonic"]
        )

    def test_busy_and_ratio_upper_bounds_fail(self) -> None:
        before, after = self.valid()
        after["n_busy_slots_per_decode"] = 2.1
        self.assertFalse(
            STUDY.classify_occupancy(before, after)["fields"][
                "busy_metrics_bounded_zero_to_two"
            ]
        )
        before, after = self.valid()
        after["n_decode_total"] = 511.0
        self.assertFalse(
            STUDY.classify_occupancy(before, after)["fields"]["ratio_proves_m2"]
        )


class SynchronizationTests(unittest.TestCase):
    def valid_rows(self) -> list[dict[str, float]]:
        return [
            {
                "request_started_perf_s": 10.001,
                "t100_perf_s": 11.0,
                "t512_perf_s": 15.0,
            },
            {
                "request_started_perf_s": 10.010,
                "t100_perf_s": 11.1,
                "t512_perf_s": 15.2,
            },
        ]

    def test_valid_two_stream_overlap(self) -> None:
        result = STUDY.classify_synchronization(self.valid_rows(), 10.0)
        self.assertTrue(result["passed"], result["fields"])

    def test_wrong_stream_count_and_bad_skew_fail(self) -> None:
        rows = self.valid_rows()
        self.assertFalse(STUDY.classify_synchronization(rows[:1], 10.0)["passed"])
        rows[1]["request_started_perf_s"] = 10.030
        self.assertFalse(
            STUDY.classify_synchronization(rows, 10.0)["fields"][
                "request_skew_within_limit"
            ]
        )

    def test_nonoverlap_and_bad_time_order_fail(self) -> None:
        rows = self.valid_rows()
        rows[1]["t100_perf_s"] = 15.1
        self.assertFalse(
            STUDY.classify_synchronization(rows, 10.0)["fields"]["broad_decode_overlap"]
        )
        rows = self.valid_rows()
        rows[0]["t100_perf_s"] = 9.0
        self.assertFalse(
            STUDY.classify_synchronization(rows, 10.0)["fields"]["per_row_time_order"]
        )


class OracleTests(unittest.TestCase):
    def valid_oracle(self) -> dict[str, Any]:
        rows = []
        for slot_id, case_id in enumerate(STUDY.EXPECTED_CASES):
            tokens = [slot_id + 1] * STUDY.TOKEN_COUNT
            rows.append(
                {
                    "case_id": case_id,
                    "slot_id": slot_id,
                    "token_ids": tokens,
                    "token_count": STUDY.TOKEN_COUNT,
                    "token_ids_sha256": STUDY.token_sha256(tokens),
                    "calibrated_prompt_tokens": STUDY.EXPECTED_PROMPT_TOKENS[case_id],
                    "prompt_sha256": "1" * 64,
                    "rendered_prompt_sha256": "2" * 64,
                    "content_sha256": "3" * 64,
                    "passed": True,
                }
            )
        return {
            "run_identity": {
                "mode": "sequential-oracle",
                "suite_sha256": STUDY.SUITE_SHA256,
                "model_sha256": STUDY.MODEL_SHA256,
                "runtime_sha256": STUDY.RUNTIME_SHA256,
                "band": "short",
                "ctx_size_total": 65536,
                "ctx_size_per_slot": 32768,
                "parallel_slots": 2,
                "cache_type_k": "f16",
                "cache_type_v": "f16",
                "max_tokens": STUDY.TOKEN_COUNT,
                "ignore_eos": True,
                "seed": 1,
                "cache_prompt": False,
                "server_benchmark_identity": STUDY.SERVER_IDENTITY,
            },
            "intrinsic_gate": {"passed": True},
            "oracle_comparison": {"status": "BASELINE_CAPTURE_READY"},
            "rows": rows,
        }

    def test_case_slot_mapping_is_frozen(self) -> None:
        oracle = self.valid_oracle()
        fields, _ = STUDY.validate_oracle(oracle, STUDY.SUITE_SHA256, "a" * 64, 0)
        self.assertTrue(all(fields.values()), fields)
        oracle["rows"][0]["slot_id"] = 1
        oracle["rows"][1]["slot_id"] = 0
        fields, _ = STUDY.validate_oracle(oracle, STUDY.SUITE_SHA256, "a" * 64, 0)
        self.assertFalse(fields["oracle_case_slot_mapping_exact"])

    def test_oracle_seed_rejects_json_boolean_alias(self) -> None:
        oracle = self.valid_oracle()
        oracle["run_identity"]["seed"] = True
        fields, _ = STUDY.validate_oracle(
            oracle, STUDY.SUITE_SHA256, "a" * 64, 0
        )
        self.assertFalse(fields["payload_exact"])


class StoredCaptureRowTests(unittest.TestCase):
    def valid(self) -> tuple[dict[str, Any], dict[str, Any]]:
        case_id = STUDY.EXPECTED_CASES[0]
        rendered = "rendered prompt"
        rendered_sha = hashlib.sha256(rendered.encode()).hexdigest()
        oracle = {
            "rendered_prompt_sha256": rendered_sha,
            "calibrated_prompt_tokens": STUDY.EXPECTED_PROMPT_TOKENS[case_id],
        }
        offsets = [index / 100.0 for index in range(STUDY.TOKEN_COUNT)]
        row: dict[str, Any] = {
            "case_id": case_id,
            "slot_id": 0,
            "rendered_prompt_sha256": rendered_sha,
            "payload": {
                "prompt": rendered,
                "id_slot": 0,
                **STUDY.PAYLOAD_FIELDS,
            },
            "token_ids": [1] * STUDY.TOKEN_COUNT,
            "token_offsets_s": offsets,
            "content": "content",
            "request_started_perf_s": 10.0,
            "request_ended_perf_s": 20.0,
            "t100_perf_s": 10.0 + offsets[99],
            "t512_perf_s": 10.0 + offsets[511],
            "final": {
                "id_slot": 0,
                "stop_type": "limit",
                "truncated": False,
                "timings": {
                    "cache_n": 0,
                    "predicted_n": STUDY.TOKEN_COUNT,
                    "prompt_n": STUDY.EXPECTED_PROMPT_TOKENS[case_id],
                },
            },
        }
        recomputed = STUDY.recompute_stored_row_contract(row, oracle)
        row["evidence_fields"] = recomputed["evidence_fields"]
        row["payload_fields"] = recomputed["payload_fields"]
        row["evidence_valid"] = True
        return row, oracle

    def test_valid_stored_row_recomputes_every_boolean_map(self) -> None:
        row, oracle = self.valid()
        fields, _ = STUDY.validate_stored_row_contract(row, oracle)
        self.assertTrue(all(fields.values()), fields)

    def test_raw_final_payload_offset_and_time_mutations_fail(self) -> None:
        mutations = {
            "cache_n": lambda row: row["final"]["timings"].__setitem__("cache_n", 1),
            "predicted_n": lambda row: row["final"]["timings"].__setitem__(
                "predicted_n", 511
            ),
            "prompt_n": lambda row: row["final"]["timings"].__setitem__("prompt_n", 1),
            "final_slot": lambda row: row["final"].__setitem__("id_slot", 1),
            "stop_type": lambda row: row["final"].__setitem__("stop_type", "eos"),
            "truncated": lambda row: row["final"].__setitem__("truncated", True),
            "payload": lambda row: row["payload"].__setitem__("n_predict", 511),
            "offset_count": lambda row: row["token_offsets_s"].pop(),
            "offset_order": lambda row: row["token_offsets_s"].__setitem__(100, 0.0),
            "t100": lambda row: row.__setitem__("t100_perf_s", 999.0),
            "t512": lambda row: row.__setitem__("t512_perf_s", 999.0),
            "request_end": lambda row: row.__setitem__("request_ended_perf_s", 9.0),
            "request_end_before_t512": lambda row: row.__setitem__(
                "request_ended_perf_s", 12.0
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                row, oracle = self.valid()
                mutate(row)
                fields, _ = STUDY.validate_stored_row_contract(row, oracle)
                self.assertFalse(all(fields.values()), fields)

    def test_json_boolean_substitutions_fail_even_with_resigned_maps(self) -> None:
        mutations = {
            "row_slot_false": lambda row: row.__setitem__("slot_id", False),
            "final_slot_false": lambda row: row["final"].__setitem__(
                "id_slot", False
            ),
            "cache_false": lambda row: row["final"]["timings"].__setitem__(
                "cache_n", False
            ),
            "predicted_false": lambda row: row["final"]["timings"].__setitem__(
                "predicted_n", False
            ),
            "prompt_false": lambda row: row["final"]["timings"].__setitem__(
                "prompt_n", False
            ),
            "temperature_false": lambda row: row["payload"].__setitem__(
                "temperature", False
            ),
            "top_p_true": lambda row: row["payload"].__setitem__("top_p", True),
            "seed_true": lambda row: row["payload"].__setitem__("seed", True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                row, oracle = self.valid()
                mutate(row)
                recomputed = STUDY.recompute_stored_row_contract(row, oracle)
                row["evidence_fields"] = recomputed["evidence_fields"]
                row["payload_fields"] = recomputed["payload_fields"]
                row["evidence_valid"] = all(recomputed["evidence_fields"].values())
                fields, _ = STUDY.validate_stored_row_contract(row, oracle)
                self.assertFalse(all(fields.values()), fields)

    def test_slot_snapshot_rejects_boolean_integer_aliases(self) -> None:
        slots = [
            {
                "id": 0,
                "is_processing": False,
                "n_ctx": 32768,
                "n_prompt_tokens_cache": 0,
            },
            {
                "id": 1,
                "is_processing": False,
                "n_ctx": 32768,
                "n_prompt_tokens_cache": 0,
            },
        ]
        self.assertTrue(STUDY.validate_slots(slots, True)["passed"])
        for key, value in (
            ("id", False),
            ("n_ctx", True),
            ("n_prompt_tokens_cache", False),
        ):
            mutated = json.loads(json.dumps(slots))
            mutated[0][key] = value
            self.assertFalse(STUDY.validate_slots(mutated, True)["passed"])


class MarkerTests(unittest.TestCase):
    def parse(
        self,
        selector: int,
        pre_lines: list[str],
        post_lines: list[str],
        final_lines: list[str] | None = None,
    ) -> tuple[dict[str, bool], dict[str, Any]]:
        pre = ("\n".join(pre_lines) + "\n").encode()
        post = ("\n".join(post_lines) + "\n").encode()
        final = ("\n".join(final_lines or post_lines) + "\n").encode()
        return STUDY.parse_route_markers(
            final,
            pre,
            post,
            selector,
            "123",
            flat_marker(),
        )

    def test_on_exact_first_hit_contract(self) -> None:
        pre = [process_line(), flat_marker()]
        post = [*pre, recurrent_marker()]
        fields, observed = self.parse(1, pre, post)
        self.assertTrue(all(fields.values()), fields)
        self.assertEqual(observed["first_hit_layouts"], ["flat", "recurrent"])
        self.assertFalse(observed["summary_present"])

    def test_optional_consistent_summary_is_accepted_without_totals(self) -> None:
        pre = [process_line(), flat_marker()]
        post = [*pre, recurrent_marker()]
        summary = (
            f"{STUDY.MARKER} summary: flat_dispatches=10 recurrent_dispatches=20 "
            "flat_multicol_suppressed=10 recurrent_dmmv_suppressed=20 "
            "reorder_ready_dispatches=30 single_col_mmvq_calls=60 violations=0"
        )
        fields, observed = self.parse(1, pre, post, [*post, summary])
        self.assertTrue(all(fields.values()), fields)
        self.assertTrue(observed["summary_present"])
        self.assertNotIn("summary", observed)
        self.assertNotIn("flat_dispatches", json.dumps(observed))

    def test_bad_summary_fails(self) -> None:
        pre = [process_line(), flat_marker()]
        post = [*pre, recurrent_marker()]
        summary = (
            f"{STUDY.MARKER} summary: flat_dispatches=10 recurrent_dispatches=20 "
            "flat_multicol_suppressed=9 recurrent_dmmv_suppressed=20 "
            "reorder_ready_dispatches=30 single_col_mmvq_calls=60 violations=0"
        )
        fields, _ = self.parse(1, pre, post, [*post, summary])
        self.assertFalse(fields["on_summary_internal_if_present"])

    def test_recurrent_before_release_fails(self) -> None:
        pre = [process_line(), flat_marker(), recurrent_marker()]
        fields, _ = self.parse(1, pre, pre)
        self.assertFalse(fields["on_prerelease_exact_flat_only"])
        self.assertFalse(fields["on_recurrent_after_preclient_boundary"])

    def test_phase1_flat_marker_mismatch_fails(self) -> None:
        pre = [process_line(), flat_marker().replace("blk.0", "blk.1")]
        post = [*pre, recurrent_marker()]
        fields, _ = self.parse(1, pre, post)
        self.assertFalse(fields["on_prerelease_exact_flat_only"])

    def test_recurrent_geometry_mismatch_fails(self) -> None:
        bad = recurrent_marker().replace("src1_ne=[6144,1,2,1]", "src1_ne=[6144,2,1,1]")
        pre = [process_line(), flat_marker()]
        post = [*pre, bad]
        fields, _ = self.parse(1, pre, post)
        self.assertFalse(fields["on_first_hit_shapes_exact"])

    def test_violation_fails(self) -> None:
        pre = [process_line(), flat_marker()]
        post = [*pre, recurrent_marker()]
        fields, _ = self.parse(
            1,
            pre,
            post,
            [*post, f"{STUDY.MARKER} violation: synthetic"],
        )
        self.assertFalse(fields["no_violation"])

    def test_off_zero_marker_contract(self) -> None:
        fields, _ = self.parse(0, [process_line()], [process_line()])
        self.assertTrue(all(fields.values()), fields)

    def test_off_first_hit_fails(self) -> None:
        fields, _ = self.parse(
            0,
            [process_line()],
            [process_line(), flat_marker()],
        )
        self.assertFalse(fields["off_postcapture_zero_markers"])
        self.assertFalse(fields["off_full_log_zero_markers"])


class ScientificOutcomeTests(unittest.TestCase):
    def test_registered_landmarks_are_exact(self) -> None:
        forward_tokens = [1] * 512
        forward = {
            "case_id": STUDY.EXPECTED_CASES[1],
            "slot_id": 1,
            "token_ids": forward_tokens,
            "oracle_comparison": {
                "lcp_tokens": 70,
                "first_mismatch": {
                    "ordinal_one_based": 71,
                    "observed_token_id": 332,
                    "oracle_token_id": 71093,
                },
            },
        }
        reverse = {
            **forward,
            "case_id": STUDY.EXPECTED_CASES[0],
            "oracle_comparison": {
                "lcp_tokens": 95,
                "first_mismatch": {
                    "ordinal_one_based": 96,
                    "observed_token_id": 90,
                    "oracle_token_id": 71093,
                },
            },
        }
        self.assertTrue(STUDY.landmark(forward, "forward"))
        self.assertTrue(STUDY.landmark(reverse, "reverse"))
        other = {
            "case_id": STUDY.EXPECTED_CASES[0],
            "slot_id": 0,
            "exact_to_oracle": True,
        }
        self.assertTrue(STUDY.scenario_landmark_reproduced([other, forward], "forward"))
        other["exact_to_oracle"] = False
        self.assertFalse(
            STUDY.scenario_landmark_reproduced([other, forward], "forward")
        )
        forward["oracle_comparison"]["first_mismatch"]["observed_token_id"] = 90
        self.assertFalse(STUDY.landmark(forward, "forward"))

    def test_pass_causal_control(self) -> None:
        outcome = STUDY.classify_outcome(lane_outcomes(), True)
        self.assertEqual(outcome["classification"], "PASS_CAUSAL_CONTROL")

    def test_candidate_exact_causal_inconclusive(self) -> None:
        lanes = lane_outcomes()
        next(lane for lane in lanes if lane["plan"]["selector"] == 0)[
            "landmark_reproduced"
        ] = False
        outcome = STUDY.classify_outcome(lanes, True)
        self.assertEqual(
            outcome["classification"], "CANDIDATE_EXACT_CAUSAL_INCONCLUSIVE"
        )
        self.assertFalse(outcome["off_landmarks_all"])

    def test_no_effect_requires_all_on_landmarks(self) -> None:
        lanes = lane_outcomes()
        for lane in lanes:
            if lane["plan"]["selector"] == 1:
                lane["full_exact"] = False
                lane["landmark_reproduced"] = True
        outcome = STUDY.classify_outcome(lanes, True)
        self.assertEqual(outcome["classification"], "NO_EFFECT")
        next(lane for lane in lanes if lane["plan"]["selector"] == 1)[
            "landmark_reproduced"
        ] = False
        outcome = STUDY.classify_outcome(lanes, True)
        self.assertEqual(outcome["classification"], "CANDIDATE_INEXACT")

    def test_any_unregistered_on_divergence_is_candidate_inexact(self) -> None:
        lanes = lane_outcomes()
        target = next(lane for lane in lanes if lane["plan"]["selector"] == 1)
        target["full_exact"] = False
        target["landmark_reproduced"] = False
        outcome = STUDY.classify_outcome(lanes, True)
        self.assertEqual(outcome["classification"], "CANDIDATE_INEXACT")

    def test_invalid_evidence_dominates_scientific_result(self) -> None:
        outcome = STUDY.classify_outcome(lane_outcomes(), False)
        self.assertEqual(outcome["classification"], "INVALID_EVIDENCE")
        self.assertIsNone(outcome["on_exact_all"])

    def test_quality_regression_uses_natural_boundaries(self) -> None:
        row = {
            "case_id": STUDY.EXPECTED_CASES[1],
            "oracle_comparison": {"first_mismatch": {"ordinal_one_based": 70}},
        }
        self.assertTrue(STUDY.quality_regression([row]))
        row["oracle_comparison"]["first_mismatch"]["ordinal_one_based"] = 71
        self.assertFalse(STUDY.quality_regression([row]))


class Phase1HandoffTests(unittest.TestCase):
    def make_packet(self, root: Path) -> dict[str, Any]:
        oracle0 = root / "selector0-oracle.json"
        oracle1 = root / "selector1-oracle.json"
        write_json(oracle0, {"selector": 0})
        write_json(oracle1, {"selector": 1})
        lanes = []
        for gpu, selector in enumerate((0, 0, 1, 1)):
            run_dir = root / f"gpu{gpu}-selector{selector}"
            run_dir.mkdir()
            attestation_path = run_dir / "lane-attestation.json"
            marker_path = run_dir / "diagnostic-completion-status.json"
            write_json(
                attestation_path,
                {
                    "status": "PASS",
                    "passed": True,
                    "gpu_index": gpu,
                    "selector": selector,
                    "fields": {"all": True},
                    "identity_fields": {
                        "identity_sleep_idle_seconds_exactly_once": True
                    },
                    "live_server_fields": {"sleep_idle_argv_absent": True},
                },
            )
            write_json(
                marker_path,
                {
                    "status": "EVIDENCE_VALID",
                    "evidence_valid": True,
                    "performance_promotable": False,
                    "gpu_index": gpu,
                    "selector": selector,
                },
            )
            route = {
                "prerelease_canonical_marker_lines": [flat_marker()] if selector else []
            }
            lanes.append(
                {
                    "gpu_index": gpu,
                    "selector": selector,
                    "run_dir": str(run_dir),
                    "completion_marker_sha256": sha(marker_path),
                    "attestation_sha256": sha(attestation_path),
                    "route_observation": route,
                }
            )
        summary = {
            "status": "PASS",
            "passed": True,
            "phase": "four-gpu-sequential-c1-oracle-on-c2-topology",
            "evidence_class": "diagnostic-only",
            "performance_promotable": False,
            "model_sha256": STUDY.MODEL_SHA256,
            "runtime_sha256": STUDY.RUNTIME_SHA256,
            "suite_sha256": STUDY.SUITE_SHA256,
            "mapping": [
                {"gpu_index": 0, "selector": 0},
                {"gpu_index": 1, "selector": 0},
                {"gpu_index": 2, "selector": 1},
                {"gpu_index": 3, "selector": 1},
            ],
            "runtime_bundle": {
                "runtime_manifest_sha256": STUDY.MANIFEST_SHA256,
                "canonical_sycl_dso_sha256": STUDY.SYCL_DSO_SHA256,
            },
            "comparisons": {
                name: {"passed": True}
                for name in (
                    "off_cross_card",
                    "on_cross_card",
                    "off_on_cross_selector",
                    "all_lanes_old_baseline",
                )
            },
            "selector_oracles": {
                "0": {"path": str(oracle0), "sha256": sha(oracle0)},
                "1": {"path": str(oracle1), "sha256": sha(oracle1)},
            },
            "phase2_handoff_contract": {
                "server_benchmark_identity_exact_match_required": True,
                "sleep_idle_server_argument_forbidden": True,
                "selector_matched_oracle_required": True,
                "fresh_phase1_cohort_required": True,
            },
            "lanes": lanes,
        }
        summary_path = root / "phase-summary.json"
        write_json(summary_path, summary)
        manifest_path = root / "wave-artifacts.sha256"
        inventory = sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file() and path != manifest_path
            ),
            key=lambda path: str(path.relative_to(root)),
        )
        manifest_path.write_text(
            "".join(f"{sha(path)}  {path.relative_to(root)}\n" for path in inventory)
        )
        marker = {
            "phase": "four-gpu-sequential-c1-oracle-on-c2-topology",
            "status": "EVIDENCE_VALID",
            "evidence_valid": True,
            "evidence_class": "diagnostic-only",
            "performance_promotable": False,
            "summary_sha256": sha(summary_path),
            "artifact_manifest_sha256": sha(manifest_path),
        }
        marker_path = root / "wave-diagnostic-completion-status.json"
        write_json(marker_path, marker)
        return {
            "oracle0": oracle0,
            "oracle1": oracle1,
            "manifest": manifest_path,
            "summary": summary_path,
            "marker": marker_path,
        }

    def validate(self, root: Path, packet: dict[str, Any]) -> dict[str, bool]:
        fields, _, _ = STUDY.validate_phase1_packet(
            root,
            sha(packet["manifest"]),
            sha(packet["summary"]),
            sha(packet["marker"]),
            1,
            packet["oracle1"],
            sha(packet["oracle1"]),
        )
        return fields

    def test_valid_fresh_no_sleep_phase1_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = self.make_packet(root)
            fields = self.validate(root, packet)
            self.assertTrue(all(fields.values()), fields)

    def test_phase1_mapping_rejects_json_boolean_integer_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = self.make_packet(root)
            summary = json.loads(packet["summary"].read_text())
            summary["mapping"][0]["gpu_index"] = False
            write_json(packet["summary"], summary)
            fields = self.validate(root, packet)
            self.assertFalse(fields["mapping_exact"])

            summary = json.loads(packet["summary"].read_text())
            summary["lanes"][2]["selector"] = True
            lane_valid, _ = STUDY.validate_phase1_lanes(root, summary)
            self.assertFalse(lane_valid)

    def test_manifest_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = self.make_packet(root)
            packet["oracle1"].write_text("{}\n")
            fields = self.validate(root, packet)
            self.assertFalse(fields["manifest_valid"])

    def test_sleep_enabled_handoff_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet = self.make_packet(root)
            summary = json.loads(packet["summary"].read_text())
            summary["phase2_handoff_contract"][
                "sleep_idle_server_argument_forbidden"
            ] = False
            write_json(packet["summary"], summary)
            fields, _, _ = STUDY.validate_phase1_packet(
                root,
                sha(packet["manifest"]),
                sha(packet["summary"]),
                sha(packet["marker"]),
                1,
                packet["oracle1"],
                sha(packet["oracle1"]),
            )
            self.assertFalse(fields["manifest_valid"])
            self.assertFalse(fields["no_sleep_handoff_exact"])


class XpuEvidenceTests(unittest.TestCase):
    @staticmethod
    def sample(gpu: int, used: str) -> str:
        return (
            "+------------------------------+\n"
            f"| Device ID | {gpu} |\n"
            f"| GPU Memory Used (MiB) | {used} |\n"
            "+------------------------------+\n"
        )

    def make_packet(self, root: Path) -> None:
        rows = []
        for gpu in range(4):
            (root / f"xpu-smi-final-gpu{gpu}.txt").write_text(
                self.sample(gpu, str(40 + gpu))
            )
            rows.append(f"gpu={gpu}\tused_mib={40 + gpu}\n")
        (root / "xpu-final-used.tsv").write_text("".join(rows))

    def test_raw_xpu_tables_bind_exactly_to_tsv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_packet(root)
            passed, observed = STUDY.validate_xpu_evidence(root, True)
            self.assertTrue(passed, observed)
            (root / "xpu-final-used.tsv").write_text(
                "".join(f"gpu={gpu}\tused_mib=43\n" for gpu in range(4))
            )
            self.assertFalse(STUDY.validate_xpu_evidence(root, True)[0])

    def test_parser_rejects_wrong_duplicate_fractional_and_malformed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "stats.txt"
            for payload in (
                "arbitrary nonempty output\n",
                self.sample(1, "43.5"),
                self.sample(1, "43") + "| Device ID | 1 |\n",
                self.sample(1, "43") + "| GPU Memory Used (MiB) | 43 |\n",
            ):
                path.write_text(payload)
                self.assertIsNone(STUDY.parse_xpu_stats_file(path))
            path.write_text(self.sample(2, "43.0"))
            self.assertEqual(STUDY.parse_xpu_stats_file(path), (2, 43))

    def test_wrong_raw_card_ordinal_fails_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_packet(root)
            (root / "xpu-smi-final-gpu2.txt").write_text(self.sample(1, "42"))
            self.assertFalse(STUDY.validate_xpu_evidence(root, True)[0])


class LiveBindingTests(unittest.TestCase):
    def binding(self, port: int = 19720) -> dict[str, Any]:
        argv = canonical_argv(port)
        ticks = 1
        fields = {
            "executable_runtime_exact": True,
            "port_argument_exact": True,
            "ctx_argument_exact": True,
            "parallel_argument_exact": True,
            "ubatch_argument_exact": True,
            "listener_present": True,
            "listener_owned_by_pid": True,
        }
        return {
            "pid": 123,
            "process_start_ticks": ticks,
            "process_start_epoch_s": STUDY.process_start_epoch_s(ticks),
            "executable_path": argv[0],
            "executable_sha256": STUDY.RUNTIME_SHA256,
            "argv": argv,
            "argv_sha256": STUDY.sha256_bytes(
                b"\0".join(value.encode() for value in argv)
            ),
            "listener_inodes": ["10"],
            "owned_socket_inodes": ["10", "11"],
            "fields": fields,
            "passed": True,
            "captured_at_epoch_ns": time.time_ns(),
        }

    def test_exclusive_listener_and_canonical_argv_pass(self) -> None:
        fields, _ = STUDY.validate_retained_live_binding(self.binding(), 123, 19720)
        self.assertTrue(all(fields.values()), fields)

    def test_extra_unowned_listener_and_duplicate_conflicting_option_fail(self) -> None:
        binding = self.binding()
        binding["listener_inodes"] = ["10", "12"]
        fields, _ = STUDY.validate_retained_live_binding(binding, 123, 19720)
        self.assertFalse(fields["binding_fields_recomputed"])
        binding = self.binding()
        binding["argv"].extend(["--port", "19999"])
        binding["argv_sha256"] = STUDY.sha256_bytes(
            b"\0".join(value.encode() for value in binding["argv"])
        )
        fields, _ = STUDY.validate_retained_live_binding(binding, 123, 19720)
        self.assertFalse(fields["canonical_argv_exact"])
        self.assertFalse(fields["binding_fields_recomputed"])

    def test_inode_lists_must_be_sorted_unique_and_epoch_recomputed(self) -> None:
        binding = self.binding()
        binding["owned_socket_inodes"] = ["11", "10", "10"]
        fields, _ = STUDY.validate_retained_live_binding(binding, 123, 19720)
        self.assertFalse(fields["inode_lists_canonical"])
        binding = self.binding()
        binding["process_start_epoch_s"] += 1
        fields, _ = STUDY.validate_retained_live_binding(binding, 123, 19720)
        self.assertFalse(fields["start_epoch_recomputed_exact"])

    def test_continuity_binds_start_epoch_and_capture_order(self) -> None:
        before = self.binding()
        after = json.loads(json.dumps(before))
        after["captured_at_epoch_ns"] = before["captured_at_epoch_ns"] + 1
        self.assertTrue(STUDY.recompute_binding_continuity(before, after)["passed"])
        after["process_start_epoch_s"] += 1
        self.assertFalse(
            STUDY.recompute_binding_continuity(before, after)["continuity_fields"][
                "process_start_exact"
            ]
        )
        after = json.loads(json.dumps(before))
        after["captured_at_epoch_ns"] = before["captured_at_epoch_ns"] - 1
        self.assertFalse(
            STUDY.recompute_binding_continuity(before, after)["continuity_fields"][
                "before_passed"
            ]
        )

    def test_attestation_must_predate_before_binding_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "server-attestation.json"
            path.write_text("{}\n")
            binding = self.binding()
            modified = path.stat().st_mtime_ns / 1_000_000_000
            binding["captured_at_epoch_ns"] = path.stat().st_mtime_ns + 1_000_000
            process_epoch = binding["process_start_epoch_s"]
            retained = {
                "attestation_path": str(path.resolve()),
                "attestation_modified_epoch_s": modified,
                "process_start_epoch_s": process_epoch,
                "fields": {
                    "regular_file": True,
                    "live_binding_passed": True,
                    "attestation_created_after_process_start": True,
                    "attestation_not_future_dated": True,
                },
                "passed": True,
            }
            self.assertTrue(
                STUDY.validate_retained_attestation_binding(retained, path, binding)
            )
            binding["captured_at_epoch_ns"] = path.stat().st_mtime_ns - 1
            self.assertFalse(
                STUDY.validate_retained_attestation_binding(retained, path, binding)
            )

    def test_input_snapshots_are_nonempty_exact_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input"
            path.write_text("sealed\n")
            expected = {"input": path}
            snapshot = STUDY.snapshot_inputs(expected)
            self.assertTrue(STUDY.validate_snapshot_exact(snapshot, expected))
            self.assertFalse(STUDY.validate_snapshot_exact({}, expected))
            path.write_text("mutated\n")
            self.assertFalse(STUDY.validate_snapshot_exact(snapshot, expected))


class RawIdentityAndRuntimeTests(unittest.TestCase):
    PHASE1_LANE = Path(
        "/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/"
        "canonical-q8-c1-oracle-four-gpu-20260810T013725.235133447Z/"
        "gpu0-selector0"
    )
    MANIFEST = SCRIPT.parents[1] / "runtime-manifest-canonical-q8-c2.json"

    def test_full_server_identity_keys_are_unique_and_exact(self) -> None:
        expected = {**STUDY.SERVER_IDENTITY, "gpu_index": "0"}
        header = "".join(f"{key}={value}\n" for key, value in expected.items())
        fields = STUDY.exact_header_fields(
            (header + "--- server ---\n").encode(), expected
        )
        self.assertTrue(all(fields.values()), fields)
        duplicate = "model_alias=contradictory\n" + header + "--- server ---\n"
        fields = STUDY.exact_header_fields(duplicate.encode(), expected)
        self.assertFalse(fields["identity_model_alias_exactly_once"])

    @unittest.skipUnless(PHASE1_LANE.is_dir(), "fresh sealed Phase-1 packet unavailable")
    def test_raw_server_attestation_is_rebuilt_and_disagreement_fails(self) -> None:
        self.assertTrue(
            STUDY.recompute_server_attestation(
                self.PHASE1_LANE / "server-attestation.json",
                self.PHASE1_LANE / "server.stdout.log",
                self.PHASE1_LANE / "server.identity.log",
            )[0]
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (
                "server-attestation.json",
                "server.stdout.log",
                "server.identity.log",
            ):
                shutil.copy2(self.PHASE1_LANE / name, root / name)
            with (root / "server.stdout.log").open("a") as stream:
                stream.write("llama_context: n_ctx = 1\n")
            exact, _ = STUDY.recompute_server_attestation(
                root / "server-attestation.json",
                root / "server.stdout.log",
                root / "server.identity.log",
            )
            self.assertFalse(exact)

    @unittest.skipUnless(PHASE1_LANE.is_dir(), "fresh sealed Phase-1 packet unavailable")
    def test_runtime_reports_are_recomputed_from_raw_inventories(self) -> None:
        fields, _ = STUDY.validate_runtime(
            self.MANIFEST,
            self.PHASE1_LANE / "runtime-reference.json",
            self.PHASE1_LANE / "runtime-final.json",
            STUDY.MANIFEST_SHA256,
        )
        self.assertTrue(all(fields.values()), fields)

    @unittest.skipUnless(PHASE1_LANE.is_dir(), "fresh sealed Phase-1 packet unavailable")
    def test_identically_mutated_runtime_reports_cannot_self_attest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for stem in ("runtime-reference", "runtime-final"):
                for suffix in (".json", ".ldd.txt", ".resolved.sha256"):
                    shutil.copy2(self.PHASE1_LANE / f"{stem}{suffix}", root / f"{stem}{suffix}")
                report_path = root / f"{stem}.json"
                report = json.loads(report_path.read_text())
                report["dependencies"][0]["sha256"] = "0" * 64
                write_json(report_path, report)
            fields, observed = STUDY.validate_runtime(
                self.MANIFEST,
                root / "runtime-reference.json",
                root / "runtime-final.json",
                STUDY.MANIFEST_SHA256,
            )
            self.assertTrue(fields["signature_exact"])
            self.assertFalse(fields["reference_report_recomputed"])
            self.assertFalse(fields["final_report_recomputed"])
            self.assertFalse(
                observed["reference_raw_fields"]["dependencies_current_exact"]
            )


class PhysicalContinuityAndPassiveTests(unittest.TestCase):
    def discovery(self) -> dict[str, Any]:
        return {
            "device_list": [
                {
                    "device_id": gpu,
                    "device_function_type": "physical",
                    "device_name": "Intel(R) Arc(TM) Pro B70",
                    "uuid": f"uuid-{gpu}",
                    "pci_bdf_address": f"0000:{gpu:02x}:00.0",
                }
                for gpu in range(4)
            ]
        }

    def make_launch_wave(
        self, root: Path, wave: int, parent_pid: int = 900, parent_ticks: int = 700
    ) -> list[dict[str, Any]]:
        rows = []
        lines = []
        for plan in (row for row in STUDY.PLAN if row["wave"] == wave):
            gpu = plan["gpu_index"]
            pid = 1000 + wave * 10 + gpu
            ticks = 2000 + wave * 10 + gpu
            row = {
                **plan,
                "port": 19720 + gpu,
                "pid": pid,
                "parent_pid": parent_pid,
                "parent_start_ticks": parent_ticks,
                "start_ticks": ticks,
                "pgid": pid,
                "sid": pid,
            }
            rows.append(row)
            lines.append(
                f"wave={wave}\tgpu={gpu}\tscenario={plan['scenario']}\tselector={plan['selector']}"
                f"\tport={row['port']}\tpid={pid}\tparent_pid={parent_pid}"
                f"\tparent_start_ticks={parent_ticks}\tstart_ticks={ticks}\tpgid={pid}\tsid={pid}\n"
            )
            write_json(
                root / f"gpu{gpu}-session-gate.json",
                {
                    "passed": True,
                    "pid": pid,
                    "parent_pid": parent_pid,
                    "parent_start_ticks": str(parent_ticks),
                    "start_ticks": str(ticks),
                    "pgid": pid,
                    "sid": pid,
                },
            )
            lane = root / f"gpu{gpu}-{plan['scenario']}-selector{plan['selector']}"
            lane.mkdir()
            write_json(lane / "lane-attestation.json", {**plan, "port": 19720 + gpu})
            write_json(lane / "diagnostic-completion-status.json", dict(plan))
        (root / "wave-launches.tsv").write_text("".join(lines))
        return rows

    def test_discovery_rejects_symlink_and_boolean_ordinal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "discovery.json"
            write_json(path, self.discovery())
            fields, devices = STUDY.validate_device_discovery(path)
            self.assertTrue(all(fields.values()), fields)
            self.assertEqual(len(devices), 4)
            link = root / "discovery-link.json"
            link.symlink_to(path)
            self.assertFalse(
                STUDY.validate_device_discovery(link)[0]["regular_nonsymlink_file"]
            )
            value = self.discovery()
            value["device_list"][0]["device_id"] = False
            write_json(path, value)
            self.assertFalse(
                all(STUDY.validate_device_discovery(path)[0].values())
            )

    def test_observed_launch_maps_and_outer_child_identities_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_root = Path(temporary)
            wave1 = run_root / "wave1"
            wave2 = run_root / "wave2"
            wave1.mkdir()
            wave2.mkdir()
            rows1 = self.make_launch_wave(wave1, 1)
            rows2 = self.make_launch_wave(wave2, 2)
            fields1, observed1 = STUDY.validate_wave_launch_map(wave1, 1)
            fields2, observed2 = STUDY.validate_wave_launch_map(wave2, 2)
            self.assertTrue(all(fields1.values()), fields1)
            self.assertTrue(all(fields2.values()), fields2)
            identity = run_root / "outer-runner-identity.env"
            identity.write_text("pid=900\nstart_ticks=700\n")
            continuity, _ = STUDY.validate_outer_runner_continuity(
                identity, observed1 + observed2
            )
            self.assertTrue(all(continuity.values()), continuity)
            wrong_parent = [dict(row) for row in rows1 + rows2]
            wrong_parent[-1]["parent_start_ticks"] = 701
            self.assertFalse(
                STUDY.validate_outer_runner_continuity(identity, wrong_parent)[0][
                    "single_outer_identity_across_waves"
                ]
            )
            reused_child = [dict(row) for row in rows1 + rows2]
            reused_child[-1]["pid"] = reused_child[0]["pid"]
            reused_child[-1]["start_ticks"] = reused_child[0]["start_ticks"]
            self.assertFalse(
                STUDY.validate_outer_runner_continuity(identity, reused_child)[0][
                    "eight_distinct_child_identities"
                ]
            )

    def test_raw_passive_scans_reject_device_lost_and_xe_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "lane.log").write_text("ordinary shutdown\n")
            (root / "preprobe-kernel-journal.txt").write_text("ordinary kernel line\n")
            (root / "preprobe-log-error-scan.txt").write_text("")
            (root / "preprobe-device-error-scan.txt").write_text("")
            fields = STUDY.validate_passive_raw_evidence(root, "preprobe")
            self.assertTrue(all(fields.values()), fields)
            (root / "lane.log").write_text("ZE_RESULT_ERROR_DEVICE_LOST\n")
            self.assertFalse(
                STUDY.validate_passive_raw_evidence(root, "preprobe")[
                    "raw_logs_no_frozen_error_match"
                ]
            )
            (root / "lane.log").write_text("ordinary shutdown\n")
            (root / "preprobe-kernel-journal.txt").write_text("xe reset detected\n")
            self.assertFalse(
                STUDY.validate_passive_raw_evidence(root, "preprobe")[
                    "raw_journal_no_frozen_device_match"
                ]
            )

    def test_success_state_rejects_contradictory_failure_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "wave-state.env").write_text("state=RELEASE\n")
            write_json(
                root / "release.json",
                {
                    "released": True,
                    "phase": "canonical-q8-c2-crossover",
                    "wave": 1,
                    "released_utc": "2026-08-10T00:00:00Z",
                },
            )
            (root / "wave-status.txt").write_text("PRE_SEAL_EVIDENCE_VALID\n")
            fields = STUDY.validate_wave_success_state(root, 1)
            self.assertTrue(all(fields.values()), fields)
            for name in ("abort", "postrelease-failure.env", "child-survivor.env"):
                with self.subTest(name=name):
                    artifact = root / name
                    artifact.write_text("contradiction\n")
                    self.assertFalse(
                        STUDY.validate_wave_success_state(root, 1)[
                            "failure_state_artifacts_absent"
                        ]
                    )
                    artifact.unlink()
            lane = root / "lane"
            lane.mkdir()
            (lane / "run-status.txt").write_text("PRE_SEAL_EVIDENCE_VALID\n")
            self.assertTrue(all(STUDY.validate_lane_success_state(lane).values()))
            (lane / "server-identity-unbound.env").write_text("signals_sent=0\n")
            self.assertFalse(
                STUDY.validate_lane_success_state(lane)["failure_artifacts_absent"]
            )


class RunnerStaticTests(unittest.TestCase):
    @staticmethod
    def shell_function(name: str, following_name: str) -> str:
        text = RUNNER.read_text()
        start = text.index(f"{name}() {{\n")
        end = text.index(f"\n{following_name}() {{", start)
        return text[start:end]

    @staticmethod
    def run_bash(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", script], text=True, capture_output=True, check=False
        )

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_runner_is_activated_and_maps_both_waves(self) -> None:
        text = RUNNER.read_text()
        self.assertIn('PHASE2_LIVE_GATE="REVIEWED_AND_FROZEN"', text)
        self.assertNotIn('PHASE2_LIVE_GATE="${', text)
        self.assertIn('[[ "$PHASE2_LIVE_GATE" == "REVIEWED_AND_FROZEN" ]]', text)
        self.assertIn("WAVE1_SELECTORS=(0 1 0 1)", text)
        self.assertIn("WAVE2_SELECTORS=(1 0 1 0)", text)
        self.assertIn("SCENARIOS=(forward forward reverse reverse)", text)

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_runner_freezes_exact_analyzer_bytes(self) -> None:
        expected = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
        self.assertIn(f'EXPECTED_ANALYZER_SHA256="{expected}"', RUNNER.read_text())

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_review_checkpoint_pins_exact_runner_bytes(self) -> None:
        self.assertEqual(
            hashlib.sha256(RUNNER.read_bytes()).hexdigest(), FROZEN_RUNNER_SHA256
        )

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_runner_forbids_sleep_and_old_compact_client(self) -> None:
        text = RUNNER.read_text()
        self.assertIn("SLEEP_IDLE_SECONDS=-1", text)
        self.assertNotIn("--sleep-idle-seconds 60", text)
        self.assertNotIn('python3 "$MATRIX_CLIENT" --scenario', text)
        self.assertIn('python3 "$ANALYZER" capture', text)
        self.assertIn("forced-512", text)

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_live_gate_precedes_mutating_or_active_operations(self) -> None:
        text = RUNNER.read_text()
        gate = text.index('[[ "$PHASE2_LIVE_GATE" == "REVIEWED_AND_FROZEN" ]]')
        self.assertLess(gate, text.index('mkdir "$RUN_ROOT"'))
        self.assertLess(gate, text.index("xpu-smi discovery"))
        self.assertLess(gate, text.index('"$LAUNCHER"'))

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_synthetic_pending_gate_fails_before_creating_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            run_root = temporary_root / "must-not-exist"
            activated = 'PHASE2_LIVE_GATE="REVIEWED_AND_FROZEN"'
            pending = 'PHASE2_LIVE_GATE="PENDING_INDEPENDENT_REVIEW"'
            runner_text = RUNNER.read_text()
            self.assertEqual(runner_text.count(activated), 1)
            self.assertNotIn(pending, runner_text)
            pending_runner = temporary_root / RUNNER.name
            pending_runner.write_text(runner_text.replace(activated, pending, 1))
            pending_runner.chmod(0o755)
            result = subprocess.run(
                [str(pending_runner), "--run-phase2"],
                text=True,
                capture_output=True,
                env={
                    "PATH": "/usr/bin:/bin",
                    "RUN_ROOT": str(run_root),
                    "PHASE2_LIVE_GATE": "REVIEWED_AND_FROZEN",
                },
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("live gate is pending", result.stderr)
            self.assertFalse(run_root.exists())
            direct = subprocess.run(
                [str(pending_runner), "--child"],
                text=True,
                capture_output=True,
                env={
                    "PATH": "/usr/bin:/bin",
                    "RUN_DIR": str(run_root),
                    "PHASE2_LIVE_GATE": "REVIEWED_AND_FROZEN",
                },
            )
            self.assertEqual(direct.returncode, 2)
            self.assertIn("live gate is pending", direct.stderr)
            self.assertFalse(run_root.exists())

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_direct_executable_plan_and_noarg_contract(self) -> None:
        self.assertTrue(RUNNER.stat().st_mode & 0o111)
        plan = subprocess.run(
            [str(RUNNER), "--print-wave-plan"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(len(plan.stdout.splitlines()), 8)
        noarg = subprocess.run(
            [str(RUNNER)], text=True, capture_output=True, check=False
        )
        self.assertEqual(noarg.returncode, 2)
        self.assertIn("--print-wave-plan", noarg.stderr)

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_lifecycle_helpers_use_argument_index_not_caller_gpu(self) -> None:
        recorded = self.shell_function(
            "recorded_session_alive", "session_members_present"
        )
        session = self.shell_function(
            "session_members_present", "capture_recorded_members"
        )
        signal = self.shell_function(
            "signal_session", "capture_transition_lane_processes"
        )
        common = """
set -u
declare -a CHILD_PIDS=([0]=100 [1]=200)
declare -a CHILD_PPIDS=([0]=99 [1]=199)
declare -a CHILD_START_TICKS=([0]=10 [1]=20)
declare -a CHILD_PGIDS=([0]=100 [1]=200)
declare -a CHILD_SIDS=([0]=100 [1]=200)
gpu=1
bound_pid_running() { [[ "$1 $2 $3" == "100 99 10" ]]; }
"""
        recorded_script = (
            common
            + """
ps() {
  if [[ "$*" == *"pgid=,sid="* ]]; then printf '100 100\n'
  elif [[ "$*" == *"sid=,stat="* ]]; then printf '100 S\n'
  else return 2
  fi
}
"""
            + recorded
            + "\nrecorded_session_alive 0\n"
        )
        self.assertEqual(self.run_bash(recorded_script).returncode, 0)
        session_script = (
            common
            + """
ps() { printf '100 S\n'; }
"""
            + session
            + "\nsession_members_present 0\n"
        )
        self.assertEqual(self.run_bash(session_script).returncode, 0)
        signal_script = (
            common
            + """
ps() { printf '100 100\n'; }
kill() { printf '%s\n' "$*"; }
"""
            + signal
            + "\nsignal_session 0 TERM\n"
        )
        signaled = self.run_bash(signal_script)
        self.assertEqual(signaled.returncode, 0, signaled.stderr)
        self.assertEqual(signaled.stdout, "-TERM -- -100\n")
        membership_lost = self.run_bash(
            common
            + """
calls=0
bound_pid_running() { calls=$((calls + 1)); (( calls == 1 )); }
ps() { printf '100 100\n'; }
kill() { printf 'UNSAFE %s\n' "$*"; }
"""
            + signal
            + "\nif signal_session 0 TERM; then exit 9; fi\n"
        )
        self.assertEqual(membership_lost.returncode, 0, membership_lost.stderr)
        self.assertEqual(membership_lost.stdout, "")

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_same_command_dependent_local_expansions_are_banned(self) -> None:
        for line in RUNNER.read_text().splitlines():
            if not line.lstrip().startswith("local "):
                continue
            assigned = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)=", line)
            for name in assigned:
                self.assertIsNone(
                    re.search(
                        rf"\$(?:\{{{re.escape(name)}(?:\W|$)|{re.escape(name)}\b)", line
                    ),
                    f"same-command dependent local expansion for {name}: {line}",
                )

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_failed_transition_waits_reaps_all_matching_children_and_never_signals(
        self,
    ) -> None:
        function = self.shell_function(
            "wait_failed_transition_quiet", "terminate_current_wave"
        )
        self.assertNotIn("kill", function)
        reaped = self.run_bash(
            """
set -u
UNBOUND_TRANSITION_WAIT_S=35
matching=1
waited=0
pid_running() { return 1; }
capture_transition_lane_processes() {
  : > "$2"
  (( matching == 0 )) || printf 'pid=124\tppid=123\n' > "$2"
}
sleep() { matching=0; SECONDS=$((SECONDS + 1)); }
wait() { waited=1; }
"""
            + function
            + "\nwait_failed_transition_quiet 123 /run/lane /tmp/transition-test-$$\nprintf 'waited=%s\\n' \"$waited\"\n"
        )
        self.assertEqual(reaped.returncode, 0, reaped.stderr)
        self.assertEqual(reaped.stdout, "waited=1\n")
        survivor = self.run_bash(
            """
set -u
UNBOUND_TRANSITION_WAIT_S=2
waited=0
pid_running() { return 1; }
capture_transition_lane_processes() { printf 'pid=124\n' > "$2"; }
sleep() { SECONDS=$((SECONDS + 1)); }
wait() { waited=1; }
"""
            + function
            + "\nif wait_failed_transition_quiet 123 /run/lane /tmp/transition-test-$$; then exit 9; fi\nprintf 'waited=%s\\n' \"$waited\"\n"
        )
        self.assertEqual(survivor.returncode, 0, survivor.stderr)
        self.assertEqual(survivor.stdout, "waited=0\n")

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_failed_transition_survivor_withholds_detached_seal(self) -> None:
        text = RUNNER.read_text()
        self.assertIn("UNBOUND_TRANSITION_WAIT_S=35", text)
        self.assertIn("waited_through_gate_timeout=1", text)
        self.assertIn("transition_signals_sent=0", text)
        self.assertIn("run-root-detached-seal-withheld.env", text)
        self.assertIn(
            "if (( OUTER_SURVIVOR == 0 && post_query == 0 && post_quiet == 0 ))",
            text,
        )
        self.assertIn('FAILED_TRANSITION_PID="$launch_pid"', text)
        self.assertIn(
            "failure-postcleanup-unbound-transition-child.txt",
            text.replace("${prefix}", "failure-postcleanup"),
        )

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_atomic_abort_release_and_last_moment_child_gate(self) -> None:
        claim = self.shell_function("claim_wave_state", "wave_failure_present")
        failure = self.shell_function("wave_failure_present", "publish_wave_abort")
        abort = self.shell_function("publish_wave_abort", "publish_wave_release")
        release = self.shell_function("publish_wave_release", "stable_log_size")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = (
                "set -u\n"
                f'CURRENT_WAVE_STATE="{root / "state"}"\n'
                f'CURRENT_WAVE_ABORT="{root / "abort"}"\n'
                f'CURRENT_WAVE_FAILURE="{root / "failure"}"\n'
                f'CURRENT_WAVE_RELEASE="{root / "release"}"\n'
                + claim
                + "\n"
                + failure
                + "\n"
                + abort
                + "\n"
                + release
                + "\npublish_wave_abort 1 0\n"
                + "if publish_wave_release 1; then exit 9; fi\n"
                + "grep -qx state=ABORT \"$CURRENT_WAVE_STATE\"\n"
                + "[[ ! -e \"$CURRENT_WAVE_RELEASE\" ]]\n"
            )
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = (
                "set -u\n"
                f'CURRENT_WAVE_STATE="{root / "state"}"\n'
                f'CURRENT_WAVE_ABORT="{root / "abort"}"\n'
                f'CURRENT_WAVE_FAILURE="{root / "failure"}"\n'
                f'CURRENT_WAVE_RELEASE="{root / "release"}"\n'
                + claim
                + "\n"
                + failure
                + "\n"
                + abort
                + "\n"
                + release
                + "\npublish_wave_release 1\n"
                + "publish_wave_abort 1 0\n"
                + "grep -qx state=RELEASE \"$CURRENT_WAVE_STATE\"\n"
                + "[[ -s \"$CURRENT_WAVE_RELEASE\" && -s \"$CURRENT_WAVE_FAILURE\" ]]\n"
                + "wave_failure_present\n"
            )
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 0, result.stderr)
        child = RUNNER.read_text().split("child_main() {", 1)[1].split(
            'if [[ "$ACTION" == "--child" ]]', 1
        )[0]
        capture = child.index(
            'timeout --signal=TERM --kill-after=30 "$REQUEST_TIMEOUT_S"'
        )
        final_abort_check = child.rfind(
            'wave_failure_present && die "wave aborted at capture boundary"',
            0,
            capture,
        )
        self.assertGreater(
            final_abort_check, child.rfind("release state mismatch", 0, capture)
        )

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_child_survivor_and_outer_identity_are_propagated_and_bound(self) -> None:
        text = RUNNER.read_text()
        for required in (
            "CURRENT_WAVE_CHILD_SURVIVOR",
            "publish_child_survivor",
            "child_survivor_reported",
            "OUTER_START_TICKS",
            "parent_start_ticks",
            "outer-runner-identity.env",
            "outer runner identity lost between waves",
            "outer runner identity lost at final seal boundary",
        ):
            self.assertIn(required, text)
        self.assertIn("if (( CHILD_CLEANUP_SURVIVOR == 1 ))", text)
        self.assertIn("postcleanup_query_failed=%s", text)

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_failure_path_retains_passive_device_and_quiet_state(self) -> None:
        text = RUNNER.read_text()
        failure_scan = self.shell_function("failure_passive_scan", "outer_failure")
        outer_start = text.index("outer_failure() {\n")
        outer_end = text.index("\n}\ntrap outer_failure", outer_start) + 2
        outer_failure = text[outer_start:outer_end]
        self.assertNotIn("Aborted", failure_scan)
        self.assertNotIn("out of memory", failure_scan)
        for required in (
            "failure-predrain",
            "failure-postcleanup",
            "device_fault_detected",
            "query_failed",
            "quiet_state_failed",
            "active_xpu_probe_performed=0",
        ):
            self.assertIn(required, text)
        self.assertIn("failure_passive", outer_failure)
        self.assertIn("active_xpu_probe_after_failure:false", outer_failure)
        self.assertIn("[r]un-canonical-q8-c2-crossover-four-gpu-wave.sh", failure_scan)
        self.assertIn("'$1 != outer'", failure_scan)

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_phase1_packet_identity_is_literal_and_not_env_overridable(self) -> None:
        text = RUNNER.read_text()
        literals = {
            "PHASE1_DIR": "/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/canonical-q8-c1-oracle-four-gpu-20260810T013725.235133447Z",
            "EXPECTED_PHASE1_MANIFEST_SHA256": "2871f4947a06a99f28ea813dbb1b092f638336ef46be6631d79f7528fe98259c",
            "EXPECTED_PHASE1_SUMMARY_SHA256": "5550e5a60f577d6642d750b1f7035759a286ffcb383e35497e0c546f2d46741b",
            "EXPECTED_PHASE1_MARKER_SHA256": "5335f67a5b5a177ae6bada2cabb45f6c1fc45cc62f285072e2ceefa572d6ce01",
            "EXPECTED_SELECTOR0_ORACLE_SHA256": "62a3e2991f697db2e420a49ddb048539cf94f1fd436f93b3f48b08eb8b38d573",
            "EXPECTED_SELECTOR1_ORACLE_SHA256": "bb179eac0ffa11bffc2d56f77b309ccdf62fcbce193f56a1cb9efbc944e6a2d4",
        }
        for name, value in literals.items():
            self.assertIn(f'{name}="{value}"', text)
            self.assertNotIn(f'{name}="${{', text)

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_dependency_hashes_close_manifest_window_and_direct_child_bypass(
        self,
    ) -> None:
        text = RUNNER.read_text()
        manifest_start = text.index('SCRIPT_SHA256="$(file_sha256 "$SCRIPT")"')
        manifest_end = text.index('sha256sum -c "$WAVE_INPUT_MANIFEST"', manifest_start)
        manifest_window = text[manifest_start:manifest_end]
        self.assertIn(
            "assert_outer_fixed_dependencies", text[:manifest_start].splitlines()[-1]
        )
        self.assertIn("assert_outer_fixed_dependencies", manifest_window)
        child_start = text.index("child_main() {\n")
        child_end = text.index('\nif [[ "$ACTION" == "--child" ]]', child_start)
        child = text[child_start:child_end]
        core = child.index("assert_core_dependency_hashes")
        phase1 = child.index("assert_phase1_packet_hashes")
        self.assertLess(core, child.index('mkdir "$RUN_DIR"'))
        self.assertLess(phase1, child.index('mkdir "$RUN_DIR"'))
        self.assertLess(core, child.index("sample_gpu"))
        self.assertGreaterEqual(child.count("assert_core_dependency_hashes"), 3)
        self.assertGreaterEqual(child.count("assert_phase1_packet_hashes"), 3)
        before_sample = child.rfind("assert_core_dependency_hashes", 0, child.index("sample_gpu"))
        before_launch = child.rfind("assert_core_dependency_hashes", 0, child.index('"$LAUNCHER"'))
        self.assertGreater(before_sample, child.index('mkdir "$RUN_DIR"'))
        self.assertGreater(before_launch, child.index("sample_gpu"))

    @unittest.skipUnless(RUNNER.exists(), "runner is added after analyzer checkpoint")
    def test_expected_hash_check_rejects_freshly_rebaselined_mutation(self) -> None:
        file_sha = self.shell_function("file_sha256", "assert_sha")
        assert_sha = self.shell_function("assert_sha", "assert_core_dependency_hashes")
        with tempfile.TemporaryDirectory() as temporary:
            dependency = Path(temporary) / "dependency"
            dependency.write_text("reviewed\n")
            expected = hashlib.sha256(dependency.read_bytes()).hexdigest()
            dependency.write_text("mutated-and-new-manifest-baseline\n")
            script = (
                "die() { exit 2; }\n"
                + file_sha
                + "\n"
                + assert_sha
                + f'\nassert_sha "{dependency}" "{expected}"\n'
            )
            result = self.run_bash(script)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
