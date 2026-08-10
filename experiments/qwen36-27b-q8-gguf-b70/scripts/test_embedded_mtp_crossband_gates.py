#!/usr/bin/env python3
"""Offline tests for the embedded-MTP cross-band gates."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
LANE = SCRIPT_DIR.parent
ROOT = LANE.parent.parent
GATE_PATH = SCRIPT_DIR / "embedded_mtp_crossband_gates.py"
SUITE = LANE / "c2-long-context-suite-v1.json"
PROMPT_BUILDER = ROOT / "scripts" / "bench-openai-long-context-suite.py"


def load_gate_module() -> Any:
    spec = importlib.util.spec_from_file_location("embedded_mtp_crossband_gates", GATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load cross-band gate module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATES = load_gate_module()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_server_argv(
    mode: str, band: str, gpu: int, wave: int, ubatch: int, port: int
) -> list[str]:
    alias = f"qwen36-27b-mtp-crossband-w{wave}-g{gpu}-{band}-{mode}"
    spec_args = ["--spec-type", "none"]
    if mode == "mtp3":
        spec_args = [
            "--spec-type",
            "draft-mtp",
            "--spec-draft-n-max",
            "3",
            "--spec-draft-n-min",
            "0",
            "--spec-draft-p-split",
            "0.10",
            "--spec-draft-p-min",
            "0.00",
            "--spec-draft-backend-sampling",
            "--spec-draft-device",
            "SYCL0",
            "--spec-draft-ngl",
            "all",
            "--spec-draft-type-k",
            "f16",
            "--spec-draft-type-v",
            "f16",
        ]
    return [
        GATES.RUNTIME_PATH,
        "-m",
        "/proc/self/fd/10",
        "--alias",
        alias,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-dev",
        "SYCL0",
        "-ngl",
        "all",
        "-c",
        "32768",
        "-np",
        "1",
        "-b",
        "1024",
        "-ub",
        str(ubatch),
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
        "-fit",
        "on",
        "-fitt",
        "1024",
        *spec_args,
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


def server_log(mode: str, ubatch: int) -> str:
    lines = [
        "I qwen35.block_count u32 = 65",
        "I n_layer = 64",
        "I n_layer_all = 65",
        "I qwen35.nextn_predict_layers u32 = 1",
        "I common_params_fit_impl: will leave 3000 >= 1024 MiB of free device memory, no changes needed",
        "I offloaded 66/66 layers to GPU",
        "I n_ctx = 32768",
        "I initializing, n_slots = 1, n_ctx_slot = 32768, kv_unified = 'false'",
        "I n_batch = 1024",
        f"I n_ubatch = {ubatch}",
        "I SYCL0 KV buffer size = 2048.00 MiB",
    ]
    if mode == "control":
        lines.append("I no implementations specified for speculative decoding")
    else:
        lines.extend(
            [
                "I creating MTP draft context against the target model '/proc/self/fd/10'",
                "I n_batch = 1024",
                f"I n_ubatch = {ubatch}",
                "I SYCL0 KV buffer size = 128.00 MiB",
            ]
        )
    return "\n".join(lines) + "\n"


class ServerGateTests(unittest.TestCase):
    def test_exact_middle_control_and_near32k_mtp_identities_pass(self) -> None:
        cases = (
            ("control", "middle", 0, 1, 128, 20120),
            ("mtp3", "near32k", 3, 1, 1024, 20123),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (mode, band, gpu, wave, ubatch, port) in enumerate(cases):
                identity = root / f"identity-{index}.json"
                log = root / f"server-{index}.log"
                output = root / f"gate-{index}.json"
                alias = f"qwen36-27b-mtp-crossband-w{wave}-g{gpu}-{band}-{mode}"
                write_json(
                    identity,
                    {
                        "mode": mode,
                        "band": band,
                        "gpu_index": gpu,
                        "wave": wave,
                        "batch_size": 1024,
                        "ubatch_size": ubatch,
                        "port": port,
                        "alias": alias,
                        "model_load_path": "/proc/self/fd/10",
                        "model_sha256": GATES.MODEL_SHA256,
                        "runtime_sha256": GATES.RUNTIME_SHA256,
                        "runtime_path": GATES.RUNTIME_PATH,
                        "argv": expected_server_argv(mode, band, gpu, wave, ubatch, port),
                    },
                )
                log.write_text(server_log(mode, ubatch), encoding="utf-8")
                result = GATES.gate_server(
                    argparse.Namespace(
                        mode=mode,
                        band=band,
                        ubatch_size=ubatch,
                        gpu_index=gpu,
                        wave=wave,
                        log=log,
                        identity=identity,
                        output=output,
                    )
                )
                self.assertEqual(result, 0)
                self.assertTrue(json.loads(output.read_text())["passed"])

    def test_middle_rejects_ubatch_1024_before_artifact_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "middle requires ubatch 128"):
                GATES.gate_server(
                    argparse.Namespace(
                        mode="control",
                        band="middle",
                        ubatch_size=1024,
                        gpu_index=0,
                        wave=1,
                        log=Path(temporary) / "missing.log",
                        identity=Path(temporary) / "missing.json",
                        output=Path(temporary) / "output.json",
                    )
                )


def metric_text(prompt_tokens: int, predicted_tokens: int) -> str:
    return "\n".join(
        (
            f"llamacpp:prompt_tokens_total {prompt_tokens}",
            f"llamacpp:tokens_predicted_total {predicted_tokens}",
            "llamacpp:requests_processing 0",
            "llamacpp:requests_deferred 0",
        )
    ) + "\n"


class ArmGateTests(unittest.TestCase):
    def test_fresh_baseline_arm_and_counter_join_pass(self) -> None:
        by_band, make_prompt = GATES.load_suite(SUITE, PROMPT_BUILDER)
        cases = by_band["middle"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for mode in ("control", "mtp3"):
                rows = []
                for case in cases:
                    prompt_n = int(case["calibrated_prompt_tokens"])
                    offsets = [1.0 + index / 20.0 for index in range(512)]
                    request_started = 100.0 + len(rows) * 30.0
                    request_ended = request_started + 26.0
                    timing: dict[str, Any] = {
                        "predicted_n": 512,
                        "predicted_ms": 25600.0,
                        "predicted_per_second": 20.0,
                        "prompt_n": prompt_n,
                        "prompt_ms": prompt_n * 10.0,
                        "prompt_per_second": 100.0,
                        "cache_n": 0,
                    }
                    if mode == "mtp3":
                        timing.update({"draft_n": 100, "draft_n_accepted": 60})
                    expected = GATES.expected_json(case)
                    content = json.dumps(expected, sort_keys=True)
                    rows.append(
                        {
                            "prompt_id": case["id"],
                            "prompt_sha256": GATES.sha256_text(make_prompt(case)),
                            "calibrated_prompt_tokens": prompt_n,
                            "rendered_prompt_sha256": "a" * 64,
                            "token_count": 512,
                            "token_ids": list(range(512)),
                            "content": content,
                            "content_sha256": GATES.sha256_text(content),
                            "stream_content_matches_replay": True,
                            "stream_alignment_unique": True,
                            "stream_final_predicted_n": 512,
                            "final_predicted_n": 512,
                            "stop_type_matches_replay": True,
                            "stop_type": "limit",
                            "stream_stop_type": "limit",
                            "id_slot_matches_request": True,
                            "stream_timings": timing,
                            "timings": dict(timing),
                            "ttft_s": offsets[0],
                            "request_started_perf_s": request_started,
                            "request_ended_perf_s": request_ended,
                            "request_elapsed_s": request_ended - request_started,
                            "token_event_offsets_s": offsets,
                            "primary_metric": {
                                "interval_count": 99,
                                "event_count": 100,
                                "numerator": 99,
                                "start_event_index": 0,
                                "end_event_index": 99,
                                "duration_s": 99 / 20,
                                "tok_s": 20.0,
                            },
                            "full_512_metric": {
                                "interval_count": 511,
                                "event_count": 512,
                                "numerator": 511,
                                "start_event_index": 0,
                                "end_event_index": 511,
                                "duration_s": 511 / 20,
                                "tok_s": 20.0,
                            },
                        }
                    )
                capture = root / f"{mode}-capture.json"
                write_json(
                    capture,
                    {
                        "run_identity": {
                            "suite_sha256": GATES.SUITE_SHA256,
                            "prompt_builder_sha256": GATES.PROMPT_BUILDER_SHA256,
                            "band": "middle",
                            "prompt_ids": [case["id"] for case in cases],
                            "model_sha256": GATES.MODEL_SHA256,
                            "runtime_sha256": GATES.RUNTIME_SHA256,
                            "ctx_size": 32768,
                            "cache_type_k": "f16",
                            "cache_type_v": "f16",
                            "sycl_dnn_enabled": 0,
                            "sycl_opt_enabled": 1,
                            "max_tokens": 512,
                            "ignore_eos": True,
                            "require_exact_token_count": True,
                            "require_full_512_metric": True,
                            "require_post_512_canary": False,
                            "post_512_canary_suite_path": None,
                            "post_512_canary_suite_sha256": None,
                            "post_512_canary_oracle_path": None,
                            "post_512_canary_oracle_sha256": None,
                            "post_512_canary_prompt_id": None,
                            "post_512_canary_slot_id": None,
                            "slot_id": 0,
                            "seed": 1,
                            "temperature": 0,
                            "top_p": 1,
                            "cache_prompt": False,
                            "return_tokens": True,
                            "stream": True,
                            "exact_token_replay": True,
                            "replay_order": "all_streaming_rows_then_all_non_streaming_replays",
                            "api": "llama.cpp /apply-template, streaming timing, deterministic non-streaming token replay",
                            "suite_path": str(SUITE),
                            "prompt_builder_path": str(PROMPT_BUILDER),
                            "base_url": "http://127.0.0.1:20120",
                        },
                        "intrinsic_gate": {"passed": True},
                        "oracle_comparison": {
                            "status": "BASELINE_CAPTURE_READY",
                            "passed": None,
                            "oracle_json": None,
                        },
                        "prefix_oracle_comparison": None,
                        "rows": rows,
                    },
                )
                server_gate = {
                    "passed": True,
                    "mode": mode,
                    "band": "middle",
                    "gpu_index": 0,
                    "wave": 1,
                    "port": 20120,
                    "ubatch_size": 128,
                    "identity_sha256": "b" * 64,
                }
                server_pre = root / f"{mode}-server-pre.json"
                server_post = root / f"{mode}-server-post.json"
                write_json(server_pre, server_gate)
                write_json(server_post, server_gate)
                before = root / f"{mode}-before.prom"
                after = root / f"{mode}-after.prom"
                before.write_text(metric_text(0, 0), encoding="utf-8")
                after.write_text(
                    metric_text(2 * sum(int(case["calibrated_prompt_tokens"]) for case in cases), 2048),
                    encoding="utf-8",
                )
                counters = {"accepted_tokens": 0, "draft_tokens": 0, "drafts": 0}
                if mode == "mtp3":
                    counters = {"accepted_tokens": 240, "draft_tokens": 400, "drafts": 160}
                metrics_gate = root / f"{mode}-metrics-gate.json"
                write_json(metrics_gate, {"passed": True, "mode": mode, "counters": counters})
                output = root / f"{mode}-arm-gate.json"
                gate_args = argparse.Namespace(
                    mode=mode,
                    band="middle",
                    ubatch_size=128,
                    gpu_index=0,
                    wave=1,
                    capture=capture,
                    suite=SUITE,
                    prompt_builder=PROMPT_BUILDER,
                    server_gate=server_pre,
                    server_post_gate=server_post,
                    metrics_before=before,
                    metrics_after=after,
                    metrics_gate=metrics_gate,
                    output=output,
                )
                result = GATES.gate_arm(gate_args)
                self.assertEqual(result, 0, json.loads(output.read_text()))
                if mode == "control":
                    invalid_capture = json.loads(capture.read_text())
                    invalid_capture["rows"][0]["request_ended_perf_s"] = invalid_capture[
                        "rows"
                    ][0]["request_started_perf_s"]
                    write_json(capture, invalid_capture)
                    invalid_output = root / "control-invalid-interval-arm-gate.json"
                    invalid_args = argparse.Namespace(
                        **(vars(gate_args) | {"output": invalid_output})
                    )
                    self.assertEqual(GATES.gate_arm(invalid_args), 1)
                    invalid_gate = json.loads(invalid_output.read_text())
                    self.assertFalse(
                        invalid_gate["rows"][0]["checks"][
                            "finite_ordered_request_interval"
                        ]
                    )


def build_crossover(root: Path, candidate_multiplier: float) -> None:
    suite = json.loads(SUITE.read_text())
    ids = {
        pair["band"]: [case["id"] for case in pair["cases"]]
        for pair in suite["pairs"]
        if pair["band"] in {"middle", "near32k"}
    }
    write_json(
        root / "run-identity.json",
        {
            "date_utc": "20260810T010203.123456789Z",
            "evidence_class": "parallel-functional-screen",
            "performance_promotable": False,
            "localmaxxing_submission_ready": False,
            "model_load_path": "/proc/self/fd/10",
            "model_size": 29047084160,
            "model_sha256": GATES.MODEL_SHA256,
            "model_repository": GATES.MODEL_REPOSITORY,
            "model_revision": GATES.MODEL_REVISION,
            "runtime_path": GATES.RUNTIME_PATH,
            "runtime_sha256": GATES.RUNTIME_SHA256,
            "runtime_manifest_sha256": GATES.RUNTIME_MANIFEST_SHA256,
            "runtime_commit": GATES.RUNTIME_COMMIT,
            "suite_sha256": GATES.SUITE_SHA256,
            "prompt_builder_sha256": GATES.PROMPT_BUILDER_SHA256,
            "port_base": 20120,
            "ctx_size": 32768,
            "batch_size": 1024,
            "max_tokens": 512,
            "ignore_eos": True,
            "cache_type_k": "f16",
            "cache_type_v": "f16",
            "sycl_dnn_enabled": 0,
            "sycl_opt_enabled": 1,
            "assignments": GATES.EXPECTED_ASSIGNMENT_OBJECTS,
        },
    )
    for (wave, gpu), (band, mode) in GATES.EXPECTED_ASSIGNMENTS.items():
        directory = GATES.arm_dir(root, wave, gpu, band, mode)
        directory.mkdir(parents=True)
        speed = 20.0 * (candidate_multiplier if mode == "mtp3" else 1.0)
        prompt_rate = 300.0 if band == "near32k" else 200.0
        ttft = 100.0 if band == "near32k" else 30.0
        per_prompt = {
            prompt_id: {
                "d99_interval_tok_s": speed,
                "d511_interval_tok_s": speed,
                "native_stream_tok_s": speed,
                "native_replay_tok_s": speed,
                "prompt_tok_s": prompt_rate,
                "ttft_s": ttft,
            }
            for prompt_id in ids[band]
        }
        counters = {"draft_tokens": 0, "accepted_tokens": 0, "drafts": 0}
        if mode == "mtp3":
            counters = {"draft_tokens": 400, "accepted_tokens": 240, "drafts": 160}
        capture = {
            "rows": [
                {
                    "prompt_id": prompt_id,
                    "rendered_prompt_sha256": hashlib.sha256(prompt_id.encode()).hexdigest(),
                    "token_ids": [gpu + 1] * 512,
                    "content": f"same-card-gpu-{gpu}-{prompt_id}",
                    "content_sha256": hashlib.sha256(
                        f"same-card-gpu-{gpu}-{prompt_id}".encode()
                    ).hexdigest(),
                    "request_started_perf_s": 1000.0
                    + wave * 100.0
                    + prompt_index * 20.0
                    + gpu * 0.01,
                    "request_ended_perf_s": 1010.0
                    + wave * 100.0
                    + prompt_index * 20.0
                    + gpu * 0.01,
                }
                for prompt_index, prompt_id in enumerate(ids[band])
            ]
        }
        capture_path = directory / "exact-tokens.json"
        write_json(capture_path, capture)
        arm_gate = {
            "passed": True,
            "band": band,
            "mode": mode,
            "gpu_index": gpu,
            "wave": wave,
            "port": 20120 + gpu,
            "capture_sha256": sha256(capture_path),
            "per_prompt": per_prompt,
            "summary": {"prometheus": {"counters": counters}},
        }
        gate_path = directory / "arm-gate.json"
        write_json(gate_path, arm_gate)
        (directory / "cleanup-status.env").write_text(
            "forced_kill=0\ncleanup_survivor=0\nport_closed=1\nvram_returned=1\n",
            encoding="utf-8",
        )
        manifest_lines = []
        for name in ("arm-gate.json", "cleanup-status.env", "exact-tokens.json"):
            manifest_lines.append(f"{sha256(directory / name)}  ./{name}")
        manifest = directory / "artifacts.sha256"
        manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        write_json(
            directory / "completion-status.json",
            {
                "status": "PASS",
                "evidence_valid": True,
                "performance_promotable": False,
                "arm_gate_sha256": sha256(gate_path),
                "artifacts_manifest_sha256": sha256(manifest),
            },
        )


def refresh_fixture_arm_integrity(directory: Path) -> None:
    capture_path = directory / "exact-tokens.json"
    gate_path = directory / "arm-gate.json"
    gate = json.loads(gate_path.read_text())
    gate["capture_sha256"] = sha256(capture_path)
    write_json(gate_path, gate)
    manifest_lines = []
    for name in ("arm-gate.json", "cleanup-status.env", "exact-tokens.json"):
        manifest_lines.append(f"{sha256(directory / name)}  ./{name}")
    manifest = directory / "artifacts.sha256"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    marker = json.loads((directory / "completion-status.json").read_text())
    marker["arm_gate_sha256"] = sha256(gate_path)
    marker["artifacts_manifest_sha256"] = sha256(manifest)
    write_json(directory / "completion-status.json", marker)


class CrossoverTests(unittest.TestCase):
    def test_retention_win_and_valid_negative_are_both_valid_evidence(self) -> None:
        for multiplier, classification, performance in (
            (1.10, "PASS_CROSSBAND_MTP_RETENTION_WIN", True),
            (1.02, "VALID_CROSSBAND_NO_MTP_WIN", False),
        ):
            with self.subTest(multiplier=multiplier), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                build_crossover(root, multiplier)
                output = root / "comparison.json"
                result = GATES.compare_crossover(
                    argparse.Namespace(
                        root=root,
                        suite=SUITE,
                        prompt_builder=PROMPT_BUILDER,
                        output=output,
                    )
                )
                value = json.loads(output.read_text())
                self.assertEqual(result, 0)
                self.assertEqual(value["classification"], classification)
                self.assertTrue(value["evidence_passed"])
                self.assertIs(value["performance_passed"], performance)
                self.assertFalse(value["performance_promotable"])
                self.assertFalse(value["localmaxxing_submission_ready"])
                self.assertTrue(
                    all(
                        wave["passed"]
                        for wave in value["wave_first_scored_intersections"]
                    )
                )

    def test_disjoint_first_scored_interval_invalidates_otherwise_valid_wave(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_crossover(root, 1.10)
            directory = GATES.arm_dir(root, 1, 3, "near32k", "mtp3")
            capture_path = directory / "exact-tokens.json"
            capture = json.loads(capture_path.read_text())
            capture["rows"][0]["request_started_perf_s"] = 1120.0
            capture["rows"][0]["request_ended_perf_s"] = 1130.0
            write_json(capture_path, capture)
            refresh_fixture_arm_integrity(directory)
            output = root / "comparison.json"
            result = GATES.compare_crossover(
                argparse.Namespace(
                    root=root,
                    suite=SUITE,
                    prompt_builder=PROMPT_BUILDER,
                    output=output,
                )
            )
            comparison = json.loads(output.read_text())
            failed_evidence = [
                key
                for key, passed in comparison["evidence_checks"].items()
                if not passed
            ]
            self.assertEqual(result, 1)
            self.assertEqual(
                failed_evidence,
                ["wave1_first_scored_four_way_intersection"],
            )
            self.assertLess(
                comparison["wave_first_scored_intersections"][0][
                    "four_way_intersection_s"
                ],
                0,
            )
            self.assertEqual(
                comparison["classification"], "INVALID_CROSSBAND_EVIDENCE"
            )

    def test_same_card_token_mismatch_invalidates_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build_crossover(root, 1.10)
            candidate = GATES.arm_dir(root, 2, 0, "middle", "mtp3") / "exact-tokens.json"
            value = json.loads(candidate.read_text())
            value["rows"][0]["token_ids"][0] += 1
            write_json(candidate, value)
            output = root / "comparison.json"
            result = GATES.compare_crossover(
                argparse.Namespace(
                    root=root,
                    suite=SUITE,
                    prompt_builder=PROMPT_BUILDER,
                    output=output,
                )
            )
            comparison = json.loads(output.read_text())
            self.assertEqual(result, 1)
            self.assertEqual(comparison["classification"], "INVALID_CROSSBAND_EVIDENCE")
            self.assertFalse(comparison["evidence_passed"])


if __name__ == "__main__":
    unittest.main()
