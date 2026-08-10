#!/usr/bin/env python3
"""Synthetic offline tests for four-service evidence and performance gates."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("embedded_mtp_four_service_realistic_gates.py")
SUITE = SCRIPT.parents[3] / "repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
SPEC = importlib.util.spec_from_file_location("four_service_gates", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
gates = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gates)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Fixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.port_base = 23000
        suite = json.loads(SUITE.read_text())
        prompts = suite["prompts"]
        self.control_rows = []
        self.reference_rows = []
        self.capture_rows = []
        for index, prompt in enumerate(prompts):
            full_token_ids = [index * 1000 + position for position in range(100)]
            positions = [
                position
                for position in range(100)
                if not (index == 8 and position == 89)
            ]
            token_ids = [full_token_ids[position] for position in positions]
            content = f"exact-content-{index}"
            offsets = [position / 40 for position in positions]
            common = {
                "prompt_index": index,
                "prompt_id": prompt["id"],
                "prompt_sha256": hashlib.sha256(prompt["prompt"].encode()).hexdigest(),
                "rendered_prompt_sha256": hashlib.sha256(
                    f"rendered-{index}".encode()
                ).hexdigest(),
                "prompt_tokens": 20,
                "completion_tokens": 100,
                "stream_complete_positions": positions,
                "token_id_offsets_s": offsets,
                "token_ids": token_ids,
                "content": content,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "usage": {"prompt_tokens": 20},
                "timings": {"prompt_n": 20},
            }
            self.reference_rows.append(copy.deepcopy(common))
            self.control_rows.append(
                {
                    "prompt_id": prompt["id"],
                    "token_ids": full_token_ids,
                    "token_count": 100,
                    "content": content,
                    "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "rendered_prompt_sha256": common["rendered_prompt_sha256"],
                    "usage": {"prompt_tokens": 20},
                    "timings": {"prompt_n": 20},
                }
            )
            service = index % 4
            model = f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{service}"
            row = copy.deepcopy(common)
            row.update(
                {
                    "wave_index": index // 4,
                    "service_index": service,
                    "gpu_index": service,
                    "base_url": f"http://127.0.0.1:{self.port_base + service}",
                    "model": model,
                    "request_id": f"request-{index}",
                    "request_started_epoch_s": 1000 + index // 4 * 20 + service * 0.01,
                    "request_ended_epoch_s": 1010 + index // 4 * 20 + service * 0.01,
                    "elapsed_s": 10.0,
                    "stream_token_id_count": len(token_ids),
                    "cached_tokens": 0,
                    "content": content,
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "usage": {
                        "completion_tokens": 100,
                        "prompt_tokens": 20,
                        "total_tokens": 120,
                        "prompt_tokens_details": {"cached_tokens": 0},
                    },
                    "timings": {
                        "cache_n": 0,
                        "prompt_n": 20,
                        "predicted_n": 100,
                        "draft_n": 300,
                        "draft_n_accepted": 180,
                    },
                    "request_payload": {
                        "model": model,
                        "prompt": f"rendered-{index}",
                        "max_tokens": 512,
                        "temperature": 0,
                        "top_p": 1,
                        "seed": 1,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                        "cache_prompt": False,
                        "verbose": True,
                        "return_tokens": True,
                        "ignore_eos": False,
                        "id_slot": 0,
                    },
                    "final_event_count": 1,
                    "done_count": 1,
                    "usage_event_count": 1,
                    "final_timings_event_count": 1,
                    "final_verbose_tokens": [],
                    "final_verbose_content": "",
                    "final_verbose": {
                        "stop": True,
                        "id_slot": 0,
                        "truncated": False,
                        "tokens_predicted": 100,
                        "stop_type": "limit",
                    },
                    "finish_reasons": ["length"],
                    "response_ids": [f"response-{index}"],
                }
            )
            self.capture_rows.append(row)

        self.isolated = root / "isolated.json"
        self.control = root / "control.json"
        self.sealed_gate = root / "sealed-gate.json"
        self.comparison = root / "comparison.json"
        self.identity = root / "identity.json"
        self.completion = root / "completion.json"
        write_json(
            self.isolated,
            {
                "run_identity": {
                    "suite_sha256": gates.SUITE_SHA256,
                    "generation_requests_per_prompt": 1,
                    "replay_requests": 0,
                },
                "realistic_final_gate": {"passed": True},
                "rows": self.reference_rows,
            },
        )
        write_json(self.control, {"rows": self.control_rows})
        write_json(
            self.sealed_gate,
            {
                "passed": True,
                "mode": "mtp3",
                "model_sha256": gates.MODEL_SHA256,
                "runtime_sha256": gates.RUNTIME_SHA256,
                "suite_sha256": gates.SUITE_SHA256,
                "input_sha256": digest(self.isolated),
                "checks": {
                    "scored_gate_identity_log_binding": True,
                    "scored_gate_passed": True,
                    "server_identity_mode": True,
                    "server_model_sha256": True,
                    "server_runtime_sha256": True,
                    "fresh_once": True,
                    "one_scored_request_per_prompt": True,
                },
                "control_checks": {
                    "observed_control_forensic_sha256": digest(self.control),
                    "full_candidate_control_token_ids_exact": True,
                    "full_candidate_control_content_exact": True,
                    "full_candidate_control_exact": True,
                },
            },
        )
        write_json(
            self.comparison,
            {
                "classification": "PASS_REALISTIC_MTP_WIN",
                "quality_reference": "matched_fresh_control_v1",
                "evidence_passed": True,
                "performance_passed": True,
                "realistic_policy_passed": True,
            },
        )
        write_json(
            self.identity,
            {
                "source_run_manifest_verified": True,
                "source_run_unchanged": True,
                "candidate_control_full_token_content_exact": True,
                "quality_reference": "matched_fresh_control_v1",
            },
        )
        write_json(
            self.completion,
            {
                "status": "PASS_REALISTIC_MTP_WIN",
                "evidence_valid": True,
                "comparison_sha256": digest(self.comparison),
                "supplemental_identity_sha256": digest(self.identity),
            },
        )
        gates.ISOLATED_CANDIDATE_SHA256 = digest(self.isolated)
        gates.MATCHED_CONTROL_FORENSIC_SHA256 = digest(self.control)
        gates.SEALED_MTP3_GATE_SHA256 = digest(self.sealed_gate)
        gates.SUPPLEMENT_COMPARISON_SHA256 = digest(self.comparison)
        gates.SUPPLEMENT_COMPLETION_SHA256 = digest(self.completion)
        gates.SUPPLEMENT_IDENTITY_SHA256 = digest(self.identity)
        self.write_run()

    def write_run(self) -> None:
        services = [
            {
                "service_index": index,
                "gpu_index": index,
                "base_url": f"http://127.0.0.1:{self.port_base + index}",
                "model": f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{index}",
            }
            for index in range(4)
        ]
        config_path = self.root / "service-config.json"
        write_json(config_path, {"schema": gates.CONFIG_SCHEMA, "services": services})
        prepared_path = self.root / "prepared.json"
        prepared_rows = [
            {
                "prompt_index": row["prompt_index"],
                "prompt_id": row["prompt_id"],
                "prompt_sha256": row["prompt_sha256"],
                "rendered_prompt": f"rendered-{row['prompt_index']}",
                "rendered_prompt_sha256": row["rendered_prompt_sha256"],
                "wave_index": row["wave_index"],
                "service_index": row["service_index"],
                "gpu_index": row["gpu_index"],
                "base_url": row["base_url"],
                "model": row["model"],
            }
            for row in self.capture_rows
        ]
        write_json(
            prepared_path,
            {
                "schema": f"{gates.CAPTURE_SCHEMA}-prepared",
                "suite_path": str(SUITE.resolve()),
                "suite_sha256": gates.SUITE_SHA256,
                "config_path": str(config_path.resolve()),
                "config_sha256": digest(config_path),
                "service_count": 4,
                "wave_count": 3,
                "generation_requests": 0,
                "rows": prepared_rows,
            },
        )
        waves = []
        for wave in range(3):
            starts = [1000 + wave * 20 + service * 0.01 for service in range(4)]
            ends = [value + 10 for value in starts]
            waves.append(
                {
                    "wave_index": wave,
                    "prompt_indices": list(range(wave * 4, wave * 4 + 4)),
                    "service_indices": [0, 1, 2, 3],
                    "request_ids": [f"request-{wave * 4 + service}" for service in range(4)],
                    "latest_request_start_epoch_s": max(starts),
                    "earliest_request_end_epoch_s": min(ends),
                    "four_way_overlap_s": min(ends) - max(starts),
                }
            )
        write_json(
            self.root / "capture.json",
            {
                "schema": gates.CAPTURE_SCHEMA,
                "run_identity": {
                    "config_sha256": digest(config_path),
                    "prepared_path": str(prepared_path.resolve()),
                    "prepared_sha256": digest(prepared_path),
                    "suite_sha256": gates.SUITE_SHA256,
                    "prompt_count": 12,
                    "service_count": 4,
                    "wave_count": 3,
                    "requests_per_wave": 4,
                    "generation_requests_per_prompt": 1,
                    "generation_requests_total": 12,
                    "replay_requests": 0,
                    "max_tokens": 512,
                    "seed": 1,
                    "temperature": 0,
                    "top_p": 1,
                    "ignore_eos": False,
                    "request_extra": {
                        "cache_prompt": False,
                        "id_slot": 0,
                        "ignore_eos": False,
                        "return_tokens": True,
                        "verbose": True,
                    },
                },
                "fresh_response_validity": {
                    "valid": True,
                    "each_prompt_run_once": True,
                    "cached_tokens_all_zero": True,
                    "history_acceleration": False,
                    "ngram_history_acceleration": False,
                    "response_reuse": False,
                    "context_checkpoints_or_prefix_reuse": False,
                },
                "stream_position_evidence": {"all_generated_positions_present": True},
                "metric_accounting": {
                    "schema": "realistic-window-accounting-v2-oracle-aligned",
                    "timestamped_events": 100,
                    "inter_token_intervals": 99,
                    "timing_source": "llamacpp_oai_completion_verbose_token_ids",
                },
                "waves": waves,
                "rows": self.capture_rows,
            },
        )
        journal = []
        for row in self.capture_rows:
            for event in ("request_started", "request_completed"):
                journal.append(
                    {
                        "event": event,
                        "request_id": row["request_id"],
                        "wave_index": row["wave_index"],
                        "service_index": row["service_index"],
                        "prompt_index": row["prompt_index"],
                        "prompt_id": row["prompt_id"],
                    }
                )
        (self.root / "capture-journal.jsonl").write_text(
            "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in journal)
        )
        for service in range(4):
            directory = self.root / f"gpu{service}"
            directory.mkdir(exist_ok=True)
            pid = 1000 + service
            (directory / "server.pid").write_text(f"{pid}\n")
            alias = f"qwen36-27b-mtp-q8-vdr2-realistic-scale-gpu{service}"
            write_json(
                directory / "server-identity.json",
                {
                    "mode": "mtp3",
                    "gpu_index": service,
                    "ze_affinity_mask": str(service),
                    "model": gates.MODEL_PATH,
                    "model_sha256": gates.MODEL_SHA256,
                    "runtime_sha256": gates.RUNTIME_SHA256,
                    "argv": [
                        gates.RUNTIME_PATH,
                        "--alias",
                        alias,
                        "--port",
                        str(self.port_base + service),
                        "-c",
                        "32768",
                        "-np",
                        "1",
                        "-b",
                        "1024",
                        "-ub",
                        "1024",
                        "--spec-type",
                        "draft-mtp",
                        "-lv",
                        "4",
                    ],
                },
            )
            server_gate = {
                "mode": "mtp3",
                "passed": True,
                "checks": {"full_offload_66": True, "fit_no_changes_exact": True},
                "fit_headroom_pairs_mib": [[1500, 1024]],
                "identity": str((directory / "server-identity.json").resolve()),
                "log": str((directory / "server.stdout.log").resolve()),
            }
            (directory / "server.stdout.log").write_text("synthetic server log\n")
            write_json(directory / "server-gate-pre.json", server_gate)
            write_json(directory / "server-gate-post.json", server_gate)
            write_json(
                directory / "metrics-gate.json",
                {
                    "mode": "mtp3",
                    "passed": True,
                    "checks": {"valid": True},
                    "counters": {
                        "draft_tokens": 900,
                        "accepted_tokens": 540,
                        "drafts": 300,
                    },
                },
            )
            write_json(
                directory / "residency.json",
                {
                    "gpu_index": service,
                    "pre_mib": 43,
                    "loaded_mib": 30000,
                    "loaded_delta_mib": 29957,
                },
            )
            write_json(
                directory / "cleanup.json",
                {
                    "schema": "qwen36-four-service-cleanup-v1",
                    "gpu_index": service,
                    "pid": pid,
                    "pre_mib": 43,
                    "forced_kill": False,
                    "survivor": False,
                    "port_closed": True,
                    "pid_dead": True,
                    "post_mib": 43,
                },
            )
        listener = "".join(
            f'LISTEN 0 128 127.0.0.1:{self.port_base + service} 0.0.0.0:* users:(("llama-server",pid={1000 + service},fd=3))\n'
            for service in range(4)
        )
        for wave in range(3):
            (self.root / f"listeners-wave{wave}.txt").write_text(listener)
        (self.root / "device-error-scan.txt").write_text("")
        (self.root / "server-error-scan.txt").write_text("")
        write_json(
            self.root / "model-integrity.json",
            {
                "schema": "qwen36-four-service-model-integrity-v1",
                "expected_sha256": gates.MODEL_SHA256,
                "stat_unchanged": True,
                "sha256_verified": True,
                "passed": True,
            },
        )
        runtime = {
            "passed": True,
            "binary": {
                "sha256": gates.RUNTIME_SHA256,
                "resolved_path": gates.RUNTIME_PATH,
            },
        }
        write_json(self.root / "runtime-bundle.json", runtime)
        write_json(
            self.root / "runtime-bundle-final.json",
            {
                **runtime,
                "reference_match": True,
                "reference_report": str((self.root / "runtime-bundle.json").resolve()),
            },
        )
        write_json(
            self.root / "xpu-smi-discovery.json",
            {
                "device_list": [
                    {
                        "device_id": service,
                        "device_function_type": "physical",
                        "device_name": "Intel(R) Arc(TM) Pro B70 Graphics",
                        "pci_bdf_address": f"0000:{service + 1:02x}:00.0",
                        "uuid": f"uuid-{service}",
                    }
                    for service in range(4)
                ]
            },
        )
        manifest_entries = []
        for index in range(10):
            path = self.root / f"harness-{index}.txt"
            path.write_text(f"harness-{index}\n")
            manifest_entries.append(f"{digest(path)}  {path}\n")
        (self.root / "harness-inputs.sha256").write_text("".join(manifest_entries))

    def args(self, output: str = "gate.json") -> argparse.Namespace:
        return argparse.Namespace(
            run_dir=self.root,
            suite=SUITE,
            isolated_candidate=self.isolated,
            matched_control_forensic=self.control,
            sealed_mtp3_gate=self.sealed_gate,
            supplement_comparison=self.comparison,
            supplement_completion=self.completion,
            supplement_identity=self.identity,
            port_base=self.port_base,
            output=self.root / output,
        )


class FourServiceGateTests(unittest.TestCase):
    def test_valid_prompt_balanced_scale_packet_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            self.assertEqual(gates.validate(fixture.args()), 0)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertTrue(result["passed"])
            self.assertEqual(
                result["classification"], "PASS_REALISTIC_MTP_FOUR_SERVICE_SCALE"
            )
            self.assertEqual(result["performance"]["retention"]["aggregate_d99"], 1.0)
            self.assertEqual(result["performance"]["retention"]["aggregate_full"], 1.0)
            self.assertEqual(
                result["performance"]["context"]["ideal_four_service_retention"],
                1.0,
            )
            self.assertEqual(
                result["performance"]["context"][
                    "prior_target_only_four_service_retention_expectation"
                ],
                0.997617,
            )
            self.assertEqual(
                result["performance"]["context"][
                    "preregistered_aggregate_retention_gate"
                ],
                0.95,
            )

    def test_full_token_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            fixture.capture_rows[0]["token_ids"][0] += 1
            fixture.write_run()
            self.assertEqual(gates.validate(fixture.args()), 1)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertFalse(result["passed"])
            self.assertFalse(
                result["rows"][0]["checks"]["stream_token_ids_match_control_positions"]
            )

    def test_observed_position_pattern_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            capture_path = fixture.root / "capture.json"
            capture = json.loads(capture_path.read_text())
            row = capture["rows"][0]
            for key in ("stream_complete_positions", "token_id_offsets_s", "token_ids"):
                del row[key][50]
            row["stream_token_id_count"] -= 1
            write_json(capture_path, capture)
            self.assertEqual(gates.validate(fixture.args()), 1)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertFalse(
                result["rows"][0]["checks"][
                    "observed_position_pattern_equal_retained_isolated"
                ]
            )

    def test_utf8_stream_id_gap_uses_sealed_position_binding_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            self.assertEqual(gates.validate(fixture.args()), 0)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertTrue(result["passed"])
            self.assertEqual(result["rows"][8]["stream_missing_positions"], [89])
            self.assertTrue(
                result["rows"][8]["checks"][
                    "token_identity_bound_via_sealed_position_policy"
                ]
            )
            self.assertFalse(
                result["token_identity_policy"][
                    "current_missing_position_ids_directly_observed"
                ]
            )

    def test_slow_prompt_and_counter_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            fixture.capture_rows[0]["token_id_offsets_s"] = [
                position / 20 for position in range(100)
            ]
            fixture.write_run()
            metrics = fixture.root / "gpu0/metrics-gate.json"
            value = json.loads(metrics.read_text())
            value["counters"]["accepted_tokens"] -= 1
            write_json(metrics, value)
            self.assertEqual(gates.validate(fixture.args()), 1)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertFalse(
                result["performance"]["checks"][
                    "each_prompt_d99_retention_at_least_080"
                ]
            )
            self.assertFalse(
                result["services"][0]["checks"]["metrics_response_join"]
            )

    def test_prepared_prompt_or_cleanup_identity_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            prepared_path = fixture.root / "prepared.json"
            prepared = json.loads(prepared_path.read_text())
            prepared["rows"][0]["rendered_prompt"] += "-tampered"
            write_json(prepared_path, prepared)
            capture_path = fixture.root / "capture.json"
            capture = json.loads(capture_path.read_text())
            capture["run_identity"]["prepared_sha256"] = digest(prepared_path)
            write_json(capture_path, capture)
            cleanup_path = fixture.root / "gpu0/cleanup.json"
            cleanup = json.loads(cleanup_path.read_text())
            cleanup["pid"] += 1
            write_json(cleanup_path, cleanup)
            self.assertEqual(gates.validate(fixture.args()), 1)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertFalse(
                result["rows"][0]["checks"]["prepared_prompt_bound"]
            )
            self.assertFalse(result["services"][0]["checks"]["cleanup"])

    def test_self_consistent_but_reference_different_prompt_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            prepared_path = fixture.root / "prepared.json"
            prepared = json.loads(prepared_path.read_text())
            rendered = "different-rendered-prompt"
            rendered_sha = hashlib.sha256(rendered.encode()).hexdigest()
            prepared["rows"][0]["rendered_prompt"] = rendered
            prepared["rows"][0]["rendered_prompt_sha256"] = rendered_sha
            write_json(prepared_path, prepared)
            capture_path = fixture.root / "capture.json"
            capture = json.loads(capture_path.read_text())
            capture["run_identity"]["prepared_sha256"] = digest(prepared_path)
            capture["rows"][0]["rendered_prompt_sha256"] = rendered_sha
            capture["rows"][0]["request_payload"]["prompt"] = rendered
            write_json(capture_path, capture)
            self.assertEqual(gates.validate(fixture.args()), 1)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertTrue(result["rows"][0]["checks"]["prepared_prompt_bound"])
            self.assertFalse(
                result["rows"][0]["checks"][
                    "rendered_prompt_equal_sealed_reference"
                ]
            )

    def test_duplicate_service_pid_and_negative_memory_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            (fixture.root / "gpu1/server.pid").write_text("1000\n")
            cleanup_path = fixture.root / "gpu1/cleanup.json"
            cleanup = json.loads(cleanup_path.read_text())
            cleanup["pid"] = 1000
            write_json(cleanup_path, cleanup)
            for wave in range(3):
                listener_path = fixture.root / f"listeners-wave{wave}.txt"
                listener_path.write_text(
                    listener_path.read_text().replace("pid=1001", "pid=1000")
                )
            residency_path = fixture.root / "gpu0/residency.json"
            residency = json.loads(residency_path.read_text())
            residency["pre_mib"] = -1
            residency["loaded_delta_mib"] = residency["loaded_mib"] + 1
            write_json(residency_path, residency)
            cleanup_path = fixture.root / "gpu0/cleanup.json"
            cleanup = json.loads(cleanup_path.read_text())
            cleanup["pre_mib"] = -1
            cleanup["post_mib"] = -1
            write_json(cleanup_path, cleanup)
            self.assertEqual(gates.validate(fixture.args()), 1)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertFalse(result["evidence_checks"]["four_distinct_service_pids"])
            self.assertFalse(result["services"][0]["checks"]["residency"])
            self.assertFalse(result["services"][0]["checks"]["cleanup"])

    def test_valid_negative_retains_evidence_classification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            for row in fixture.capture_rows:
                row["token_id_offsets_s"] = [
                    position / 30 for position in row["stream_complete_positions"]
                ]
            fixture.write_run()
            self.assertEqual(gates.validate(fixture.args()), 0)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertTrue(result["evidence_valid"])
            self.assertFalse(result["performance_passed"])
            self.assertFalse(result["passed"])
            self.assertEqual(
                result["classification"],
                "VALID_REALISTIC_MTP_FOUR_SERVICE_SCALE_RETENTION_FAIL",
            )

    def test_missing_four_way_overlap_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary))
            capture_path = fixture.root / "capture.json"
            value = json.loads(capture_path.read_text())
            value["rows"][7]["request_started_epoch_s"] = 1031.0
            value["rows"][7]["request_ended_epoch_s"] = 1041.0
            write_json(capture_path, value)
            self.assertEqual(gates.validate(fixture.args()), 1)
            result = json.loads((fixture.root / "gate.json").read_text())
            self.assertFalse(result["waves"][1]["checks"]["genuine_overlap"])
            self.assertFalse(
                result["waves"][1]["checks"]["summary_extrema_match_rows"]
            )


if __name__ == "__main__":
    unittest.main()
