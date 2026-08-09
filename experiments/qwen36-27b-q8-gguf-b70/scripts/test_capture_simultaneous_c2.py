#!/usr/bin/env python3
"""Offline unit tests for simultaneous-c2 timing and fail-closed gates."""

from __future__ import annotations

import copy
import importlib.util
import json
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


MODULE = load_script("capture-simultaneous-c2.py", "capture_simultaneous_c2")
COMMON = load_script("capture-exact-tokens.py", "capture_exact_tokens_for_c2_tests")


class AnalyzeRowGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokens = list(range(10_000, 10_512))
        self.offsets = [0.1 + index * 0.01 for index in range(512)]
        self.item = {
            "case": {
                "id": "middle-a",
                "calibrated_prompt_tokens": 4_096,
            },
            "slot_id": 0,
            "prompt": "plain prompt",
            "rendered": "rendered prompt",
        }
        timings = {
            "cache_n": 0,
            "predicted_n": 512,
            "prompt_n": 4_096,
        }
        self.stream = {
            "token_ids": list(self.tokens),
            "token_offsets_s": list(self.offsets),
            "content": "complete response",
            "final": {
                "id_slot": 0,
                "stop_type": "limit",
                "truncated": False,
                "timings": dict(timings),
            },
            "request_started_perf_s": 100.0,
            "request_ended_perf_s": 106.0,
        }
        self.replay = {
            "tokens": list(self.tokens),
            "content": "complete response",
            "id_slot": 0,
            "stop_type": "limit",
            "truncated": False,
            "timings": dict(timings),
        }

    def analyze(self, stream=None, replay=None):
        return MODULE.analyze_row(
            self.item,
            self.stream if stream is None else stream,
            self.replay if replay is None else replay,
            COMMON,
        )

    def test_complete_uncached_slot_pinned_row_passes(self) -> None:
        row = self.analyze()
        self.assertTrue(row["passed"])
        self.assertEqual(row["sustained_metric"]["interval_count"], 511)
        self.assertAlmostEqual(row["t512_perf_s"], 105.21)

    def test_wrong_slot_is_rejected_from_stream_or_replay(self) -> None:
        for source in ("stream", "replay"):
            with self.subTest(source=source):
                stream = copy.deepcopy(self.stream)
                replay = copy.deepcopy(self.replay)
                if source == "stream":
                    stream["final"]["id_slot"] = 1
                else:
                    replay["id_slot"] = 1
                self.assertFalse(self.analyze(stream, replay)["passed"])

    def test_nonzero_cache_is_rejected_from_stream_or_replay(self) -> None:
        for source in ("stream", "replay"):
            with self.subTest(source=source):
                stream = copy.deepcopy(self.stream)
                replay = copy.deepcopy(self.replay)
                if source == "stream":
                    stream["final"]["timings"]["cache_n"] = 1
                else:
                    replay["timings"]["cache_n"] = 1
                self.assertFalse(self.analyze(stream, replay)["passed"])

    def test_early_stop_is_rejected_even_if_t512_was_observed(self) -> None:
        stream = copy.deepcopy(self.stream)
        replay = copy.deepcopy(self.replay)
        stream["final"]["stop_type"] = "eos"
        replay["stop_type"] = "eos"
        row = self.analyze(stream, replay)
        self.assertIsNotNone(row["t512_perf_s"])
        self.assertFalse(row["passed"])

    def test_missing_t512_is_rejected(self) -> None:
        stream = copy.deepcopy(self.stream)
        stream["token_ids"] = stream["token_ids"][:-1]
        stream["token_offsets_s"] = stream["token_offsets_s"][:-1]
        row = self.analyze(stream, self.replay)
        self.assertIsNone(row["t512_perf_s"])
        self.assertEqual(row["sustained_metric"]["interval_count"], 0)
        self.assertFalse(row["passed"])

    def test_boolean_token_ids_are_rejected(self) -> None:
        for source in ("stream", "replay"):
            with self.subTest(source=source):
                stream = copy.deepcopy(self.stream)
                replay = copy.deepcopy(self.replay)
                if source == "stream":
                    stream["token_ids"][0] = True
                else:
                    replay["tokens"][0] = True
                with self.assertRaises(RuntimeError):
                    self.analyze(stream, replay)


class CanaryGateTests(unittest.TestCase):
    def capture(self, response):
        prepared = [
            {
                "case": {"id": "canary"},
                "slot_id": 0,
                "rendered": "rendered",
                "payload": {},
            }
        ]
        common = SimpleNamespace(post_json=lambda *_args, **_kwargs: response)
        return MODULE.capture_canaries(
            "http://127.0.0.1:19460", prepared, common, 2
        )[0]

    def valid_response(self):
        return {
            "tokens": list(range(128)),
            "content": "canary output",
            "id_slot": 0,
            "stop_type": "limit",
            "truncated": False,
            "timings": {"cache_n": 0, "predicted_n": 128},
        }

    def test_valid_canary_retains_observed_identity(self) -> None:
        row = self.capture(self.valid_response())
        self.assertTrue(row["passed"])
        self.assertEqual(row["observed_slot_id"], 0)
        self.assertEqual(row["predicted_n"], 128)
        self.assertEqual(row["timings"]["cache_n"], 0)

    def test_noninteger_boolean_tokens_or_nonstring_content_fail(self) -> None:
        for field in ("tokens", "boolean-token", "content"):
            with self.subTest(field=field):
                response = self.valid_response()
                if field == "tokens":
                    response["tokens"][-1] = "127"
                elif field == "boolean-token":
                    response["tokens"][0] = True
                else:
                    response["content"] = {"not": "text"}
                self.assertFalse(self.capture(response)["passed"])


class SemanticRetrievalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tokens = list(range(95))
        self.content = '{"case_id":"q27-q8-lc-04k-middle"}'
        self.forced_tokens = [*self.tokens[:-1], 999, *range(1000, 1417)]
        self.prepared = [
            {
                "case": {
                    "id": "q27-q8-lc-04k-middle",
                    "calibrated_prompt_tokens": 4369,
                },
                "slot_id": 0,
                "prompt": "prompt",
                "rendered": "rendered",
                "payload": {},
            }
        ]

    def capture(
        self,
        response,
        validation_pass=True,
        forced_tokens=None,
        forced_content=None,
    ):
        common = SimpleNamespace(post_json=lambda *_args, **_kwargs: response)
        prompt_builder = SimpleNamespace(
            validate=lambda *_args: {"pass": validation_pass}
        )
        return MODULE.capture_semantic_retrieval(
            "http://127.0.0.1:19460",
            self.prepared,
            [
                {
                    "tokens": forced_tokens or self.forced_tokens,
                    "content": forced_content or f"{self.content} trailing",
                }
            ],
            prompt_builder,
            common,
            2,
        )[0]

    def valid_response(self):
        return {
            "tokens": list(self.tokens),
            "content": self.content,
            "id_slot": 0,
            "stop_type": "eos",
            "truncated": False,
            "timings": {
                "cache_n": 0,
                "predicted_n": len(self.tokens),
                "prompt_n": 4369,
            },
        }

    def test_natural_stop_semantic_row_is_linked_to_forced_512_prefix(self) -> None:
        row = self.capture(self.valid_response())
        self.assertTrue(row["passed"])
        self.assertTrue(row["forced_512_pre_eos_token_prefix_exact"])
        self.assertTrue(row["forced_512_content_prefix_exact"])
        self.assertNotEqual(
            row["natural_terminal_token_id"],
            row["forced_token_at_natural_stop_position"],
        )

    def test_semantic_or_prefix_or_strict_integer_drift_fails(self) -> None:
        for mutation in (
            "semantic",
            "prefix",
            "content-prefix",
            "slot-bool",
            "cache-bool",
            "predicted-bool",
            "prompt-bool",
        ):
            with self.subTest(mutation=mutation):
                response = self.valid_response()
                validation_pass = mutation != "semantic"
                forced_tokens = list(self.forced_tokens)
                forced_content = f"{self.content} trailing"
                if mutation == "prefix":
                    forced_tokens[0] += 1
                elif mutation == "content-prefix":
                    forced_content = "different content"
                elif mutation == "slot-bool":
                    response["id_slot"] = False
                elif mutation == "cache-bool":
                    response["timings"]["cache_n"] = False
                elif mutation == "predicted-bool":
                    response["timings"]["predicted_n"] = True
                elif mutation == "prompt-bool":
                    response["timings"]["prompt_n"] = True
                self.assertFalse(
                    self.capture(
                        response,
                        validation_pass,
                        forced_tokens,
                        forced_content,
                    )["passed"]
                )


class ConcurrentAggregateGateTests(unittest.TestCase):
    @staticmethod
    def passing_rows() -> list[dict]:
        return [
            {
                "passed": True,
                "request_started_perf_s": 100.010,
                "request_ended_perf_s": 106.0,
                "t1_perf_s": 101.0,
                "t100_perf_s": 102.0,
                "t512_perf_s": 105.0,
                "prompt_tokens": 1_000,
                "sustained_metric": {"tok_s": 20.0},
            },
            {
                "passed": True,
                "request_started_perf_s": 100.020,
                "request_ended_perf_s": 106.2,
                "t1_perf_s": 101.2,
                "t100_perf_s": 102.4,
                "t512_perf_s": 105.4,
                "prompt_tokens": 1_200,
                "sustained_metric": {"tok_s": 25.0},
            },
        ]

    def run_concurrent(
        self,
        rows: list[dict],
        release_perf_s: float = 100.0,
        metrics_after: dict | None = None,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite_path = root / "suite.json"
            oracle_path = root / "oracle.json"
            baseline_suite_path = root / "baseline-suite.json"
            baseline_oracle_path = root / "baseline-oracle.json"
            output_path = root / "result.json"
            suite_path.write_text(
                json.dumps(
                    {
                        "pairs": [
                            {
                                "band": "short",
                                "cases": [{"id": "short-a"}, {"id": "short-b"}],
                            }
                        ]
                    }
                )
            )
            (root / "prompt-builder.py").write_text("def make_prompt(case): return 'x'\n")
            (root / "common.py").write_text("# mocked by the test\n")
            (root / "attestation.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "identity_fields": {"identity": True},
                        "argv_fields": {"argv": True},
                        "runtime_fields": {"runtime": True},
                        "expected_identity": {"ctx_size": "65536"},
                    }
                )
            )
            oracle_path.write_text("{}\n")
            baseline_suite_path.write_text("{}\n")
            baseline_oracle_path.write_text("{}\n")
            baseline_oracle_sha256 = MODULE.hashlib.sha256(
                baseline_oracle_path.read_bytes()
            ).hexdigest()
            prepared = [{"payload": {}}, {"payload": {}}]
            common = SimpleNamespace(
                post_json=lambda *_args, **_kwargs: {},
                prepare_post_512_canary=lambda *_args, **_kwargs: {
                    "suite_sha256": "c" * 64
                },
                capture_post_512_canary=lambda *_args, **_kwargs: {
                    "passed": True,
                    "slot_id_requested": _args[-1],
                },
            )
            prompt_builder = SimpleNamespace(
                make_prompt=lambda _case: "unused",
                validate=lambda _case, _content: {"pass": True},
            )
            argv = [
                str(SCRIPT_DIR / "capture-simultaneous-c2.py"),
                "--mode",
                "concurrent",
                "--base-url",
                "http://127.0.0.1:19460",
                "--suite",
                str(suite_path),
                "--band",
                "short",
                "--prompt-builder",
                str(root / "prompt-builder.py"),
                "--common-script",
                str(root / "common.py"),
                "--server-attestation",
                str(root / "attestation.json"),
                "--baseline-canary-suite",
                str(baseline_suite_path),
                "--baseline-canary-oracle",
                str(baseline_oracle_path),
                "--baseline-canary-oracle-sha256",
                baseline_oracle_sha256,
                "--baseline-canary-prompt-id",
                "incident-retrospective",
                "--oracle-json",
                str(oracle_path),
                "--out",
                str(output_path),
                "--model-sha256",
                "a" * 64,
                "--runtime-sha256",
                "b" * 64,
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    MODULE, "load_module", side_effect=[common, prompt_builder]
                ),
                mock.patch.object(MODULE, "prepare_cases", return_value=prepared),
                mock.patch.object(
                    MODULE,
                    "capture_idle_slots",
                    return_value=[
                        {"id": 0, "n_ctx": 32768, "is_processing": False},
                        {"id": 1, "n_ctx": 32768, "is_processing": False},
                    ],
                ),
                mock.patch.object(
                    MODULE,
                    "capture_metrics",
                    side_effect=[
                        {
                            "tokens_predicted_total": 0.0,
                            "n_decode_total": 0.0,
                            "n_busy_slots_per_decode": 0.0,
                        },
                        metrics_after
                        or {
                            "tokens_predicted_total": 1024.0,
                            "n_decode_total": 600.0,
                            "n_busy_slots_per_decode": 1.9,
                        },
                    ],
                ),
                mock.patch.object(
                    MODULE,
                    "capture_streams",
                    return_value=([{}, {}], release_perf_s),
                ),
                mock.patch.object(
                    MODULE,
                    "capture_canaries",
                    return_value=[{"passed": True}, {"passed": True}],
                ),
                mock.patch.object(
                    MODULE,
                    "capture_semantic_retrieval",
                    return_value=[{"passed": True}, {"passed": True}],
                ),
                mock.patch.object(
                    MODULE, "analyze_row", side_effect=copy.deepcopy(rows)
                ),
                mock.patch.object(
                    MODULE,
                    "compare_oracle",
                    return_value={"passed": True, "status": "PASS_ORACLE_EXACT"},
                ),
            ):
                return_code = MODULE.main()
            return return_code, json.loads(output_path.read_text())

    def test_aggregate_uses_joint_c2_timing_windows(self) -> None:
        return_code, result = self.run_concurrent(self.passing_rows())
        aggregate = result["aggregate"]
        self.assertEqual(return_code, 0)
        self.assertTrue(result["intrinsic_gate"]["overlap_passed"])
        self.assertTrue(result["intrinsic_gate"]["external_baseline_canary_passed"])
        self.assertEqual(
            [
                row["slot_id_requested"]
                for row in result["external_baseline_canaries"]
            ],
            [0, 1],
        )
        self.assertTrue(result["decode_occupancy"]["passed"])
        self.assertEqual(result["decode_occupancy"]["tokens_predicted_delta"], 1024)
        self.assertAlmostEqual(
            result["decode_occupancy"]["predicted_tokens_per_llama_decode"],
            1024 / 600,
        )
        self.assertAlmostEqual(aggregate["send_skew_s"], 0.010)
        self.assertTrue(aggregate["broad_decode_overlap"])
        self.assertAlmostEqual(aggregate["conventional_decode_window_s"], 4.4)
        self.assertAlmostEqual(
            aggregate["aggregate_tok_s_1_512_intervals"], 1022 / 4.4
        )
        self.assertAlmostEqual(aggregate["request_wall_s"], 6.2)
        self.assertAlmostEqual(aggregate["aggregate_full_512_wall_tok_s"], 1024 / 6.2)
        self.assertAlmostEqual(aggregate["aggregate_pp_wall_s"], 1.2)
        self.assertAlmostEqual(aggregate["aggregate_prompt_tok_s_wall"], 2200 / 1.2)
        self.assertAlmostEqual(aggregate["fairness_min_over_max"], 0.8)

    def test_excessive_send_skew_fails_intrinsic_gate(self) -> None:
        rows = self.passing_rows()
        rows[1]["request_started_perf_s"] = 100.036
        return_code, result = self.run_concurrent(rows)
        self.assertGreater(result["aggregate"]["send_skew_s"], 0.025)
        self.assertTrue(result["aggregate"]["broad_decode_overlap"])
        self.assertFalse(result["intrinsic_gate"]["overlap_passed"])
        self.assertFalse(result["intrinsic_gate"]["passed"])
        self.assertEqual(return_code, 1)

    def test_serial_decode_windows_fail_overlap_gate(self) -> None:
        rows = self.passing_rows()
        rows[0].update(
            {
                "request_ended_perf_s": 104.2,
                "t1_perf_s": 101.0,
                "t100_perf_s": 102.0,
                "t512_perf_s": 104.0,
            }
        )
        rows[1].update(
            {
                "request_ended_perf_s": 107.2,
                "t1_perf_s": 104.1,
                "t100_perf_s": 105.0,
                "t512_perf_s": 107.0,
            }
        )
        return_code, result = self.run_concurrent(rows)
        self.assertLessEqual(
            min(row["t512_perf_s"] for row in rows),
            max(row["t100_perf_s"] for row in rows),
        )
        self.assertFalse(result["aggregate"]["broad_decode_overlap"])
        self.assertFalse(result["intrinsic_gate"]["overlap_passed"])
        self.assertFalse(result["intrinsic_gate"]["passed"])
        self.assertEqual(return_code, 1)

    def test_unbatched_decode_counter_fails_occupancy_gate(self) -> None:
        return_code, result = self.run_concurrent(
            self.passing_rows(),
            metrics_after={
                "tokens_predicted_total": 1024.0,
                "n_decode_total": 1088.0,
                "n_busy_slots_per_decode": 1.1,
            },
        )
        self.assertFalse(result["decode_occupancy"]["passed"])
        self.assertFalse(result["intrinsic_gate"]["overlap_passed"])
        self.assertFalse(result["intrinsic_gate"]["passed"])
        self.assertEqual(return_code, 1)


class BarrierProtocolTests(unittest.TestCase):
    def test_release_timestamp_is_set_when_all_clients_are_ready(self) -> None:
        before_wait: list[float] = []
        after_wait: list[float] = []

        def fake_stream(
            _base_url,
            payload,
            _timeout,
            barrier,
            _connections,
            _connections_lock,
        ):
            before_wait.append(MODULE.time.perf_counter())
            barrier.wait(timeout=2)
            after_wait.append(MODULE.time.perf_counter())
            return {"worker": payload["worker"]}

        prepared = [
            {"payload": {"worker": 0}},
            {"payload": {"worker": 1}},
        ]
        with mock.patch.object(MODULE, "stream_preconnected", side_effect=fake_stream):
            rows, release = MODULE.capture_streams(
                "concurrent", "http://127.0.0.1:19460", prepared, COMMON, 2
            )
        self.assertEqual(rows, [{"worker": 0}, {"worker": 1}])
        self.assertIsInstance(release, float)
        self.assertLessEqual(max(before_wait), release)
        self.assertLessEqual(release, min(after_wait))


class OracleValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = {
            "suite_sha256": "s",
            "band": "short",
            "model_sha256": "m",
            "runtime_sha256": "candidate-runtime",
            "ctx_size_total": 65536,
            "ctx_size_per_slot": 32768,
            "parallel_slots": 2,
            "cache_type_k": "f16",
            "cache_type_v": "f16",
            "max_tokens": 512,
            "ignore_eos": True,
            "seed": 1,
            "server_benchmark_identity": {"ctx_size": "65536"},
        }
        self.rows = [
            {
                "case_id": f"case-{slot}",
                "slot_id": slot,
                "prompt_sha256": f"p{slot}",
                "rendered_prompt_sha256": f"r{slot}",
                "token_ids": [slot, 10],
                "content_sha256": f"c{slot}",
                "passed": True,
            }
            for slot in (0, 1)
        ]
        self.canaries = [
            {
                "case_id": f"canary-{slot}",
                "slot_id": slot,
                "observed_slot_id": slot,
                "cache_n": 0,
                "predicted_n": 128,
                "rendered_prompt_sha256": f"cr{slot}",
                "token_ids": [slot, *range(1, 128)],
                "content_sha256": f"cc{slot}",
                "passed": True,
            }
            for slot in (0, 1)
        ]
        self.semantic = [
            {
                "case_id": f"case-{slot}",
                "slot_id": slot,
                "prompt_sha256": f"p{slot}",
                "rendered_prompt_sha256": f"r{slot}",
                "token_ids": [slot, 30, 999],
                "content": f"semantic-{slot}",
                "forced_512_pre_eos_token_prefix_exact": True,
                "forced_512_content_prefix_exact": True,
                "validation": {"pass": True},
                "passed": True,
            }
            for slot in (0, 1)
        ]
        self.oracle = {
            "run_identity": {
                **self.identity,
                "mode": "sequential-oracle",
                "runtime_sha256": "control-runtime",
            },
            "intrinsic_gate": {"passed": True},
            "oracle_comparison": {"status": "BASELINE_CAPTURE_READY"},
            "rows": copy.deepcopy(self.rows),
            "canaries": copy.deepcopy(self.canaries),
            "semantic_retrieval": copy.deepcopy(self.semantic),
        }

    def compare(self, oracle=None):
        return MODULE.compare_oracle(
            self.identity,
            self.rows,
            self.canaries,
            self.semantic,
            self.oracle if oracle is None else oracle,
        )

    def test_valid_sequential_oracle_allows_runtime_change(self) -> None:
        result = self.compare()
        self.assertTrue(result["passed"])
        self.assertTrue(result["oracle_valid_sequential_baseline"])
        self.assertFalse(result["runtime_sha256_same"])

    def test_reverse_case_to_slot_assignment_remains_exact(self) -> None:
        reversed_rows = copy.deepcopy(list(reversed(self.rows)))
        reversed_canaries = copy.deepcopy(list(reversed(self.canaries)))
        for slot_id, row in enumerate(reversed_rows):
            row["slot_id"] = slot_id
        for slot_id, row in enumerate(reversed_canaries):
            row["slot_id"] = slot_id
            row["observed_slot_id"] = slot_id
        result = MODULE.compare_oracle(
            self.identity,
            reversed_rows,
            reversed_canaries,
            list(reversed(copy.deepcopy(self.semantic))),
            self.oracle,
        )
        self.assertTrue(result["passed"])
        self.assertTrue(
            all(not row["oracle_slot_id_same"] for row in result["rows"])
        )

    def test_failed_or_concurrent_oracle_is_rejected(self) -> None:
        for mutation in ("failed", "concurrent"):
            with self.subTest(mutation=mutation):
                oracle = copy.deepcopy(self.oracle)
                if mutation == "failed":
                    oracle["intrinsic_gate"]["passed"] = False
                else:
                    oracle["run_identity"]["mode"] = "concurrent"
                self.assertFalse(self.compare(oracle)["passed"])

    def test_duplicate_or_extra_oracle_rows_are_rejected(self) -> None:
        for mutation in ("duplicate", "extra"):
            with self.subTest(mutation=mutation):
                oracle = copy.deepcopy(self.oracle)
                oracle["rows"].append(copy.deepcopy(oracle["rows"][0]))
                if mutation == "extra":
                    oracle["rows"][-1]["case_id"] = "extra-case"
                self.assertFalse(self.compare(oracle)["passed"])

    def test_boolean_token_ids_are_rejected_in_oracle_or_candidate(self) -> None:
        for source in ("oracle-row", "oracle-canary", "candidate-row", "candidate-canary"):
            with self.subTest(source=source):
                oracle = copy.deepcopy(self.oracle)
                rows = copy.deepcopy(self.rows)
                canaries = copy.deepcopy(self.canaries)
                if source == "oracle-row":
                    oracle["rows"][0]["token_ids"][0] = True
                elif source == "oracle-canary":
                    oracle["canaries"][0]["token_ids"][0] = True
                elif source == "candidate-row":
                    rows[0]["token_ids"][0] = True
                else:
                    canaries[0]["token_ids"][0] = True
                self.assertFalse(
                    MODULE.compare_oracle(
                        self.identity, rows, canaries, self.semantic, oracle
                    )["passed"]
                )

    def test_boolean_slot_or_counter_fields_are_rejected(self) -> None:
        for source in (
            "oracle-row-slot",
            "oracle-canary-slot",
            "candidate-row-slot",
            "candidate-canary-slot",
            "candidate-canary-observed-slot",
            "candidate-canary-cache",
            "candidate-canary-predicted",
        ):
            with self.subTest(source=source):
                oracle = copy.deepcopy(self.oracle)
                rows = copy.deepcopy(self.rows)
                canaries = copy.deepcopy(self.canaries)
                if source == "oracle-row-slot":
                    oracle["rows"][0]["slot_id"] = False
                elif source == "oracle-canary-slot":
                    oracle["canaries"][0]["slot_id"] = False
                elif source == "candidate-row-slot":
                    rows[0]["slot_id"] = False
                elif source == "candidate-canary-slot":
                    canaries[0]["slot_id"] = False
                elif source == "candidate-canary-observed-slot":
                    canaries[0]["observed_slot_id"] = False
                elif source == "candidate-canary-cache":
                    canaries[0]["cache_n"] = False
                else:
                    canaries[0]["predicted_n"] = True
                self.assertFalse(
                    MODULE.compare_oracle(
                        self.identity, rows, canaries, self.semantic, oracle
                    )["passed"]
                )

    def test_cross_phase_semantic_drift_is_rejected(self) -> None:
        for field, value in (
            ("token_ids", [0, 31, 999]),
            ("content", "semantic drift"),
            ("prompt_sha256", "prompt drift"),
        ):
            with self.subTest(field=field):
                semantic = copy.deepcopy(self.semantic)
                semantic[0][field] = value
                self.assertFalse(
                    MODULE.compare_oracle(
                        self.identity,
                        self.rows,
                        self.canaries,
                        semantic,
                        self.oracle,
                    )["passed"]
                )

    def test_duplicate_or_missing_semantic_case_is_rejected(self) -> None:
        for mutation in ("duplicate", "missing"):
            with self.subTest(mutation=mutation):
                semantic = copy.deepcopy(self.semantic)
                if mutation == "duplicate":
                    semantic[1]["case_id"] = semantic[0]["case_id"]
                else:
                    semantic.pop()
                self.assertFalse(
                    MODULE.compare_oracle(
                        self.identity,
                        self.rows,
                        self.canaries,
                        semantic,
                        self.oracle,
                    )["passed"]
                )


class CliSafetyTests(unittest.TestCase):
    def test_output_must_not_overwrite_oracle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("suite.json", "builder.py", "common.py", "oracle.json"):
                (root / name).write_text("{}\n")
            argv = [
                str(SCRIPT_DIR / "capture-simultaneous-c2.py"),
                "--mode",
                "concurrent",
                "--base-url",
                "http://127.0.0.1:19460",
                "--suite",
                str(root / "suite.json"),
                "--band",
                "short",
                "--prompt-builder",
                str(root / "builder.py"),
                "--common-script",
                str(root / "common.py"),
                "--server-attestation",
                str(root / "oracle.json"),
                "--baseline-canary-suite",
                str(root / "suite.json"),
                "--baseline-canary-oracle",
                str(root / "oracle.json"),
                "--baseline-canary-oracle-sha256",
                MODULE.hashlib.sha256((root / "oracle.json").read_bytes()).hexdigest(),
                "--baseline-canary-prompt-id",
                "incident-retrospective",
                "--oracle-json",
                str(root / "oracle.json"),
                "--out",
                str(root / "oracle.json"),
                "--model-sha256",
                "a" * 64,
                "--runtime-sha256",
                "b" * 64,
            ]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit):
                    MODULE.main()

if __name__ == "__main__":
    unittest.main()
