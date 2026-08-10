#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
HELPER_PATH = HERE / "embedded_mtp_vdr2_gates.py"
RUNNER_PATH = HERE / "run-embedded-mtp-vdr2-diagnostic.sh"
SPEC = importlib.util.spec_from_file_location("embedded_mtp_vdr2_gates", HELPER_PATH)
assert SPEC is not None and SPEC.loader is not None
GATES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATES)

TRUNK_SHA = "f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce"
MTP_SHA = "9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8"
RUNTIME_SHA = "1a093f09122ceb2851157042c2bbc6281ddb9d4e2de50137502890f9b52fa7d7"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def baseline_oracle(model_sha: str = TRUNK_SHA) -> dict:
    return {
        "run_identity": {"model_sha256": model_sha},
        "intrinsic_gate": {"passed": True},
        "oracle_comparison": {"status": "BASELINE_CAPTURE_READY"},
        "rows": [{"prompt_id": "a", "token_ids": [1], "content_sha256": "c", "rendered_prompt_sha256": "r"}],
    }


def exact_capture(mode: str, interval: float = 18.2, native: float = 18.2) -> dict:
    rows = []
    for index, prompt_id in enumerate(("q27-q8-lc-04k-middle", "q27-q8-c2-04k-b")):
        stream_rate = native + index * 0.01
        replay_rate = native - 0.01 + index * 0.01
        stream_timing = {
            "predicted_n": 512,
            "predicted_ms": 512000 / stream_rate,
            "predicted_per_second": stream_rate,
        }
        replay_timing = {
            "predicted_n": 512,
            "predicted_ms": 512000 / replay_rate,
            "predicted_per_second": replay_rate,
        }
        if mode == "mtp3":
            stream_timing.update({"draft_n": 1200, "draft_n_accepted": 650})
            replay_timing.update({"draft_n": 1200, "draft_n_accepted": 650})
        rows.append(
            {
                "prompt_id": prompt_id,
                "token_count": 512,
                "cache_n": 0,
                "stream_cache_n": 0,
                "primary_metric": {"tok_s": interval + index * 0.01, "interval_count": 99},
                "full_512_metric": {"tok_s": interval + index * 0.01, "interval_count": 511},
                "stream_timings": stream_timing,
                "timings": replay_timing,
                "ttft_s": 7.0,
            }
        )
    canary_timing = {"predicted_per_second": native}
    if mode == "mtp3":
        canary_timing.update({"draft_n": 300, "draft_n_accepted": 160})
    return {
        "run_identity": {
            "model_sha256": MTP_SHA,
            "runtime_sha256": RUNTIME_SHA,
            "band": "short",
            "ctx_size": 32768,
            "max_tokens": 512,
            "cache_prompt": False,
            "require_exact_token_count": True,
            "require_full_512_metric": True,
            "require_post_512_canary": True,
            "ignore_eos": True,
            "slot_id": 0,
            "temperature": 0,
            "top_p": 1,
            "cache_type_k": "f16",
            "cache_type_v": "f16",
            "sycl_dnn_enabled": 0,
            "sycl_opt_enabled": 1,
        },
        "intrinsic_gate": {"passed": True},
        "oracle_comparison": {"status": "PASS_ORACLE_EXACT", "passed": True},
        "post_512_canary": {"passed": True, "timings": canary_timing},
        "rows": rows,
    }


def server_argv(mode: str) -> list[str]:
    argv = [
        "/runtime/llama-server", "-m", "/proc/self/fd/10", "--alias", "model",
        "--host", "127.0.0.1", "--port", "19950", "-dev", "SYCL0", "-ngl", "all",
        "-c", "32768", "-np", "1", "-b", "1024", "-ub", "1024", "-t", "8",
        "--threads-http", "6", "--poll", "50", "-lv", "4", "-ctk", "f16", "-ctv", "f16",
        "-fa", "on", "-fit", "on", "-fitp", "on", "-fitt", "1024",
    ]
    if mode == "control":
        argv += ["--spec-type", "none"]
    else:
        argv += [
            "--spec-type", "draft-mtp", "--spec-draft-n-max", "3", "--spec-draft-n-min", "0",
            "--spec-draft-p-split", "0.10", "--spec-draft-p-min", "0.00",
            "--spec-draft-backend-sampling", "--spec-draft-device", "SYCL0",
            "--spec-draft-ngl", "all", "--spec-draft-type-k", "f16",
            "--spec-draft-type-v", "f16",
        ]
    argv += [
        "--reasoning", "off", "--ctx-checkpoints", "0", "--cache-ram", "0",
        "--no-cache-idle-slots", "--no-context-shift", "--slots", "--metrics", "--jinja",
        "--no-kv-unified", "--cont-batching",
    ]
    return argv


def server_log(mode: str) -> str:
    text = """
llama_model_loader: - kv 17: qwen35.block_count u32 = 65
print_info: n_layer               = 64
print_info: n_layer_all           = 65
print_info: n_layer_nextn         = 1
load_tensors: offloaded 66/66 layers to GPU
common_params_fit_impl: getting device memory data for initial parameters:
common_params_fit_impl: projected to use 29500 MiB of device memory vs. 32300 MiB of free device memory
common_params_fit_impl: will leave 2800 >= 1024 MiB of free device memory, no changes needed
llama_context: n_ctx              = 32768
llama_context: n_batch            = 1024
llama_context: n_ubatch           = 1024
server: initializing, n_slots = 1, n_ctx_slot = 32768, kv_unified = 'false'
llama_kv_cache:      SYCL0 KV buffer size = 2048.00 MiB
"""
    if mode == "control":
        text += "common_speculative_init: no implementations specified for speculative decoding\n"
    else:
        text += "common_speculative_init_result: creating MTP draft context against the target model '/proc/self/fd/10'\n"
        text += "llama_context: n_batch            = 1024\n"
        text += "llama_context: n_ubatch           = 1024\n"
        text += "llama_kv_cache:      SYCL0 KV buffer size = 128.00 MiB\n"
    return text


class EmbeddedMtpGateTests(unittest.TestCase):
    def test_oracle_derivation_changes_exactly_one_field(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.json"
            output = root / "derived.json"
            proof = root / "proof.json"
            write_json(source, baseline_oracle())
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            result = GATES.derive_oracle(
                argparse.Namespace(
                    source=source,
                    expected_source_sha256=source_sha,
                    expected_old_model_sha256=TRUNK_SHA,
                    model_sha256=MTP_SHA,
                    output=output,
                    proof=proof,
                )
            )
            self.assertEqual(result, 0)
            derived = json.loads(output.read_text())
            evidence = json.loads(proof.read_text())
            self.assertEqual(derived["run_identity"]["model_sha256"], MTP_SHA)
            self.assertEqual(evidence["changed_paths"], ["run_identity.model_sha256"])
            self.assertEqual(
                evidence["source_projection_without_model_sha256"],
                evidence["derived_projection_without_model_sha256"],
            )

    def test_metrics_control_and_candidate_counter_algebra(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            zero = """llamacpp:spec_decode_num_draft_tokens_total 0\nllamacpp:spec_decode_num_accepted_tokens_total 0\nllamacpp:spec_decode_num_drafts_total 0\n"""
            before = root / "before.prom"
            control_after = root / "control-after.prom"
            candidate_after = root / "candidate-after.prom"
            before.write_text(zero)
            control_after.write_text(zero)
            candidate_after.write_text(
                """llamacpp:spec_decode_num_draft_tokens_total 300
llamacpp:spec_decode_num_accepted_tokens_total 150
llamacpp:spec_decode_num_drafts_total 100
llamacpp:spec_decode_num_accepted_tokens_per_pos_total{position="0"} 80
llamacpp:spec_decode_num_accepted_tokens_per_pos_total{position="1"} 50
llamacpp:spec_decode_num_accepted_tokens_per_pos_total{position="2"} 20
"""
            )
            for mode, after in (("control", control_after), ("mtp3", candidate_after)):
                output = root / f"{mode}.json"
                result = GATES.gate_metrics(
                    argparse.Namespace(mode=mode, before=before, after=after, output=output)
                )
                self.assertEqual(result, 0)
                gate = json.loads(output.read_text())
                self.assertTrue(gate["passed"])
            candidate = json.loads((root / "mtp3.json").read_text())
            self.assertEqual(candidate["acceptance_ratio"], 0.5)
            self.assertEqual(candidate["accepted_per_verification"], 1.5)
            self.assertEqual(candidate["effective_tokens_per_target_verification"], 2.5)

            missing = root / "missing.prom"
            missing.write_text("# malformed or empty metrics response\n")
            with self.assertRaisesRegex(ValueError, "must be present exactly once"):
                GATES.gate_metrics(
                    argparse.Namespace(
                        mode="control", before=missing, after=missing,
                        output=root / "missing-gate.json",
                    )
                )

    def test_exact_and_comparison_cogate_native_timing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            gates = {}
            for mode, interval, native in (("control", 16.5, 16.6), ("mtp3", 18.2, 18.2)):
                capture = root / f"{mode}-capture.json"
                gate = root / f"{mode}-gate.json"
                write_json(capture, exact_capture(mode, interval, native))
                self.assertEqual(
                    GATES.gate_exact(
                        argparse.Namespace(
                            mode=mode,
                            input=capture,
                            model_sha256=MTP_SHA,
                            runtime_sha256=RUNTIME_SHA,
                            output=gate,
                        )
                    ),
                    0,
                )
                gates[mode] = gate
            control_metrics = root / "control-metrics.json"
            candidate_metrics = root / "candidate-metrics.json"
            write_json(
                control_metrics,
                {
                    "mode": "control",
                    "passed": True,
                    "counters": {"draft_tokens": 0, "accepted_tokens": 0, "drafts": 0},
                },
            )
            write_json(
                candidate_metrics,
                {
                    "passed": True,
                    "mode": "mtp3",
                    "counters": {"draft_tokens": 5100, "accepted_tokens": 2760, "drafts": 1840},
                    "acceptance_ratio": 0.5,
                    "accepted_per_verification": 1.5,
                    "effective_tokens_per_target_verification": 2.5,
                },
            )
            comparison = root / "comparison.json"
            self.assertEqual(
                GATES.compare_arms(
                    argparse.Namespace(
                        control_exact_gate=gates["control"],
                        candidate_exact_gate=gates["mtp3"],
                        control_metrics_gate=control_metrics,
                        candidate_metrics_gate=candidate_metrics,
                        official_interval_tok_s=16.587155022411466,
                        official_native_tok_s=16.621315139033597,
                        output=comparison,
                    )
                ),
                0,
            )
            self.assertEqual(json.loads(comparison.read_text())["classification"], "ADVANCE_FULL_VALIDATION")

            burst_only_capture = root / "burst-only.json"
            burst_only_gate = root / "burst-only-gate.json"
            write_json(burst_only_capture, exact_capture("mtp3", 18.2, 17.0))
            self.assertEqual(
                GATES.gate_exact(
                    argparse.Namespace(
                        mode="mtp3", input=burst_only_capture, model_sha256=MTP_SHA,
                        runtime_sha256=RUNTIME_SHA, output=burst_only_gate,
                    )
                ),
                0,
            )
            burst_comparison = root / "burst-comparison.json"
            GATES.compare_arms(
                argparse.Namespace(
                    control_exact_gate=gates["control"], candidate_exact_gate=burst_only_gate,
                    control_metrics_gate=control_metrics, candidate_metrics_gate=candidate_metrics,
                    official_interval_tok_s=16.587155022411466,
                    official_native_tok_s=16.621315139033597, output=burst_comparison,
                )
            )
            self.assertEqual(json.loads(burst_comparison.read_text())["classification"], "STOP_NO_MTP_WIN")

            wrong_mode_metrics = root / "wrong-mode-metrics.json"
            wrong_mode = json.loads(candidate_metrics.read_text())
            wrong_mode["mode"] = "control"
            write_json(wrong_mode_metrics, wrong_mode)
            invalid_comparison = root / "invalid-mode-comparison.json"
            self.assertEqual(
                GATES.compare_arms(
                    argparse.Namespace(
                        control_exact_gate=gates["control"], candidate_exact_gate=gates["mtp3"],
                        control_metrics_gate=control_metrics,
                        candidate_metrics_gate=wrong_mode_metrics,
                        official_interval_tok_s=16.587155022411466,
                        official_native_tok_s=16.621315139033597,
                        output=invalid_comparison,
                    )
                ),
                1,
            )
            self.assertEqual(
                json.loads(invalid_comparison.read_text())["classification"],
                "INVALID_EVIDENCE",
            )

            invalid_ttft = exact_capture("control", 16.5, 16.6)
            invalid_ttft["rows"][0]["ttft_s"] = None
            invalid_capture = root / "invalid-ttft.json"
            write_json(invalid_capture, invalid_ttft)
            self.assertEqual(
                GATES.gate_exact(
                    argparse.Namespace(
                        mode="control", input=invalid_capture, model_sha256=MTP_SHA,
                        runtime_sha256=RUNTIME_SHA, output=root / "invalid-ttft-gate.json",
                    )
                ),
                1,
            )

    def test_server_gate_enforces_embedded_no_sidecar_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for mode in ("control", "mtp3"):
                log = root / f"{mode}.log"
                identity = root / f"{mode}-identity.json"
                output = root / f"{mode}-gate.json"
                log.write_text(server_log(mode))
                write_json(
                    identity,
                    {"mode": mode, "model_load_path": "/proc/self/fd/10", "argv": server_argv(mode)},
                )
                self.assertEqual(
                    GATES.gate_server(
                        argparse.Namespace(mode=mode, log=log, identity=identity, output=output)
                    ),
                    0,
                )
                self.assertTrue(json.loads(output.read_text())["passed"])

            bad_identity = root / "bad-identity.json"
            argv = server_argv("mtp3") + ["--spec-draft-model", "/tmp/sidecar.gguf"]
            write_json(bad_identity, {"mode": "mtp3", "model_load_path": "/proc/self/fd/10", "argv": argv})
            self.assertEqual(
                GATES.gate_server(
                    argparse.Namespace(
                        mode="mtp3", log=root / "mtp3.log", identity=bad_identity,
                        output=root / "bad-gate.json",
                    )
                ),
                1,
            )

            adversarial_logs = {
                "fit-adjusted-extra": (
                    server_log("control")
                    + "common_params_fit_impl: adjusted n_ubatch to fit device memory\n",
                    "fit_no_changes_exact",
                ),
                "fit-no-change-missing": (
                    server_log("control").replace(
                        "common_params_fit_impl: will leave 2800 >= 1024 MiB of free device memory, no changes needed\n",
                        "common_params_fit_impl: reduced n_ubatch to fit device memory\n",
                    ),
                    "fit_no_changes_exact",
                ),
                "fit-impossible-inequality": (
                    server_log("control").replace(
                        "will leave 2800 >= 1024 MiB",
                        "will leave 1100 >= 1200 MiB",
                    ),
                    "fit_no_changes_exact",
                ),
                "n-batch-missing": (
                    server_log("control").replace(
                        "llama_context: n_batch            = 1024\n", ""
                    ),
                    "runtime_n_batch_1024",
                ),
                "n-batch-altered": (
                    server_log("control").replace(
                        "llama_context: n_batch            = 1024",
                        "llama_context: n_batch            = 512",
                    ),
                    "runtime_n_batch_1024",
                ),
                "n-ubatch-missing": (
                    server_log("control").replace(
                        "llama_context: n_ubatch           = 1024\n", ""
                    ),
                    "runtime_n_ubatch_1024",
                ),
                "n-ubatch-altered": (
                    server_log("control").replace(
                        "llama_context: n_ubatch           = 1024",
                        "llama_context: n_ubatch           = 512",
                    ),
                    "runtime_n_ubatch_1024",
                ),
            }
            for name, (log_text, expected_failed_check) in adversarial_logs.items():
                for mode in ("control", "mtp3"):
                    log = root / f"{name}-{mode}.log"
                    output = root / f"{name}-{mode}-gate.json"
                    log.write_text(
                        log_text.replace(
                            "common_speculative_init: no implementations specified for speculative decoding\n",
                            (
                                "common_speculative_init_result: creating MTP draft context against the target model '/proc/self/fd/10'\n"
                                "llama_context: n_batch            = 1024\n"
                                "llama_context: n_ubatch           = 1024\n"
                                "llama_kv_cache:      SYCL0 KV buffer size = 128.00 MiB\n"
                            ) if mode == "mtp3" else
                            "common_speculative_init: no implementations specified for speculative decoding\n",
                        )
                    )
                    result = GATES.gate_server(
                        argparse.Namespace(
                            mode=mode,
                            log=log,
                            identity=root / f"{mode}-identity.json",
                            output=output,
                        )
                    )
                    self.assertEqual(result, 1, f"{name}/{mode}")
                    gate = json.loads(output.read_text())
                    mode_failed_check = expected_failed_check
                    if mode == "mtp3":
                        mode_failed_check = {
                            "runtime_n_batch_1024": "target_context_n_batch_1024",
                            "runtime_n_ubatch_1024": "target_context_n_ubatch_1024",
                        }.get(expected_failed_check, expected_failed_check)
                    self.assertFalse(
                        gate["checks"][mode_failed_check], f"{name}/{mode}"
                    )

            mtp_marker = (
                "common_speculative_init_result: creating MTP draft context against the target model '/proc/self/fd/10'\n"
            )
            draft_pair = (
                "llama_context: n_batch            = 1024\n"
                "llama_context: n_ubatch           = 1024\n"
            )
            candidate_log = server_log("mtp3")
            candidate_context_adversaries = {
                "draft-pair-missing": (
                    candidate_log.replace(mtp_marker + draft_pair, mtp_marker, 1),
                    "draft_context_n_batch_1024",
                ),
                "draft-n-batch-altered": (
                    candidate_log.replace(
                        mtp_marker + draft_pair,
                        mtp_marker + draft_pair.replace("n_batch            = 1024", "n_batch            = 512"),
                        1,
                    ),
                    "draft_context_n_batch_1024",
                ),
                "draft-n-ubatch-altered": (
                    candidate_log.replace(
                        mtp_marker + draft_pair,
                        mtp_marker + draft_pair.replace("n_ubatch           = 1024", "n_ubatch           = 512"),
                        1,
                    ),
                    "draft_context_n_ubatch_1024",
                ),
                "extra-altered-draft-pair": (
                    candidate_log.replace(
                        mtp_marker + draft_pair,
                        mtp_marker + draft_pair + draft_pair.replace("1024", "512"),
                        1,
                    ),
                    "draft_context_n_batch_1024",
                ),
            }
            for name, (log_text, expected_failed_check) in candidate_context_adversaries.items():
                log = root / f"{name}.log"
                output = root / f"{name}-gate.json"
                log.write_text(log_text)
                result = GATES.gate_server(
                    argparse.Namespace(
                        mode="mtp3",
                        log=log,
                        identity=root / "mtp3-identity.json",
                        output=output,
                    )
                )
                self.assertEqual(result, 1, name)
                gate = json.loads(output.read_text())
                self.assertFalse(gate["checks"][expected_failed_check], name)

            extra_valid_dry_run_log = root / "extra-valid-draft-context.log"
            extra_valid_dry_run_gate = root / "extra-valid-draft-context-gate.json"
            extra_valid_dry_run_log.write_text(
                candidate_log.replace(
                    mtp_marker + draft_pair,
                    mtp_marker + draft_pair + draft_pair,
                    1,
                )
            )
            self.assertEqual(
                GATES.gate_server(
                    argparse.Namespace(
                        mode="mtp3",
                        log=extra_valid_dry_run_log,
                        identity=root / "mtp3-identity.json",
                        output=extra_valid_dry_run_gate,
                    )
                ),
                0,
            )

            wrong_model_identity = root / "wrong-model-identity.json"
            wrong_model_argv = server_argv("mtp3")
            wrong_model_argv[wrong_model_argv.index("-m") + 1] = "/proc/self/fd/11"
            write_json(
                wrong_model_identity,
                {"mode": "mtp3", "model_load_path": "/proc/self/fd/10", "argv": wrong_model_argv},
            )
            self.assertEqual(
                GATES.gate_server(
                    argparse.Namespace(
                        mode="mtp3", log=root / "mtp3.log", identity=wrong_model_identity,
                        output=root / "wrong-model-gate.json",
                    )
                ),
                1,
            )

            target_only_log = root / "target-only-kv.log"
            target_only_log.write_text(server_log("mtp3").rsplit(
                "llama_kv_cache:      SYCL0 KV buffer size = 128.00 MiB\n", 1
            )[0])
            self.assertEqual(
                GATES.gate_server(
                    argparse.Namespace(
                        mode="mtp3", log=target_only_log, identity=root / "mtp3-identity.json",
                        output=root / "target-only-kv-gate.json",
                    )
                ),
                1,
            )

    def test_runner_live_ack_gate_precedes_all_external_live_work(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            empty_path = Path(raw) / "empty-path"
            forbidden_run = Path(raw) / "must-not-exist"
            empty_path.mkdir()
            for wrong_ack_present in (False, True):
                environment = {
                    "PATH": str(empty_path),
                    "RUN_DIR": str(forbidden_run),
                }
                if wrong_ack_present:
                    environment["QWEN36_EMBEDDED_MTP_VDR2_LIVE_ACK"] = (
                        "INTENTIONALLY_WRONG_ACK_FOR_OFFLINE_TEST"
                    )
                result = subprocess.run(
                    ["/bin/bash", str(RUNNER_PATH)], text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=environment, check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("requires the exact acknowledgement", result.stderr)
                self.assertFalse(forbidden_run.exists())
        script = RUNNER_PATH.read_text()
        self.assertIn(
            'LIVE_ENABLE_STATE="REVIEWED_AND_FINAL_MODEL_SHA256_CONFIRMED"',
            script,
        )
        self.assertNotIn("--spec-draft-model", "\n".join(
            line for line in script.splitlines() if not line.lstrip().startswith("#")
        ))
        self.assertIn("--spec-type draft-mtp", script)
        self.assertIn("--spec-draft-ngl all", script)
        self.assertIn('server-gate-postcapture.json', script)


if __name__ == "__main__":
    unittest.main()
