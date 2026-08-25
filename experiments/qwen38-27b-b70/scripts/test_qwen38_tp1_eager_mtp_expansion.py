#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
LAUNCHER_PATH = HERE / "run-20260825-qwen38-tp1-eager-mtp-expansion.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("qwen38_mtp_expansion", LAUNCHER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


L = load_launcher()


def measuring_host_evidence_available() -> bool:
    required = [L.BASELINE, *(L.PARENT_EVIDENCE.keys())]
    return all(path.is_file() for path in required)


class ExpansionContractTests(unittest.TestCase):
    @unittest.skipUnless(
        measuring_host_evidence_available(),
        "requires frozen measuring-host baseline and parent run evidence",
    )
    def test_frozen_manifest_dependencies_and_parent_pass(self) -> None:
        observed = L.verify_dependencies()
        self.assertEqual(observed[str(L.MANIFEST)], L.MANIFEST_SHA256)
        self.assertEqual(
            observed[str(L.P3_ROOT / "stage-receipt.json")],
            L.PARENT_EVIDENCE[L.P3_ROOT / "stage-receipt.json"],
        )

    def test_exact_stage_identities_and_order(self) -> None:
        self.assertEqual(list(L.STAGES), ["e1-mtp2-full", "e2-mtp4-full-actual"])
        self.assertEqual(L.STAGES["e1-mtp2-full"].mtp, 2)
        self.assertEqual(L.STAGES["e2-mtp4-full-actual"].mtp, 4)
        self.assertIsNone(L.STAGES["e1-mtp2-full"].required_stage)
        self.assertEqual(
            L.STAGES["e2-mtp4-full-actual"].required_stage, "e1-mtp2-full"
        )

    def test_e2_requires_same_attempt_e1_full_pass(self) -> None:
        stage = L.STAGES["e2-mtp4-full-actual"]
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "receipt.json"
            good = {
                "campaign_id": L.CAMPAIGN_ID,
                "stage_id": "e1-mtp2-full",
                "attempt": 2,
                "state": "passed",
                "terminal": True,
                "gates": {
                    "exact_run_identity": {"passed": True, "mtp_depth": 2},
                    "acceptance": {"passed": True},
                    "target_oracle": {"passed": True},
                    "quality": {"passed": True},
                },
            }
            path.write_text(json.dumps(good))
            with mock.patch.object(L, "receipt_path", return_value=path):
                L.verify_stage_order(stage, 2)
                good["gates"]["quality"]["passed"] = False
                path.write_text(json.dumps(good))
                with self.assertRaisesRegex(L.CampaignError, "requires.*MTP2 full"):
                    L.verify_stage_order(stage, 2)

    def test_retry_changes_root_cache_and_port_without_overwrite(self) -> None:
        stage = L.STAGES["e1-mtp2-full"]
        r1 = L.layout(stage, 1)
        r2 = L.layout(stage, 2)
        self.assertNotEqual(r1[0], r2[0])
        self.assertNotEqual(r1[1], r2[1])
        self.assertNotEqual(r1[2], r2[2])
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            (output / "stage-receipt.json").write_text("existing\n")
            with self.assertRaisesRegex(L.CampaignError, "refusing to overwrite"):
                L.write_receipt(output, {"replacement": True})

    def test_mtp4_is_exactly_one_actual_across_retry_identities(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "runs-r1"
            cache = Path(raw) / "cache-r1"
            with mock.patch.object(L, "ROOT_R1", root), mock.patch.object(
                L, "CACHE_R1", cache
            ):
                L.ensure_single_mtp4_actual()
                prior_output = L.layout(L.STAGES["e2-mtp4-full-actual"], 2)[0]
                prior_output.mkdir(parents=True)
                with self.assertRaisesRegex(L.CampaignError, "already has evidence"):
                    L.ensure_single_mtp4_actual()

    def test_default_and_wrong_ack_are_inert(self) -> None:
        default = subprocess.run(
            [sys.executable, "-B", str(LAUNCHER_PATH)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(default.returncode, 2)
        self.assertIn("choose exactly one", default.stderr)
        with mock.patch.object(L, "verify_dependencies") as verify:
            with self.assertRaises(L.CampaignError):
                L.execute(L.STAGES["e1-mtp2-full"], 1, "wrong")
        verify.assert_not_called()

    def test_execute_reaches_clean_pushed_live_main_gate_before_stage_or_launch(self) -> None:
        stage = L.STAGES["e1-mtp2-full"]
        ack = f"RUN {L.CAMPAIGN_ID} {stage.stage_id} r1"
        with mock.patch.object(L, "verify_dependencies", return_value={}), mock.patch.object(
            L.COMMON,
            "git_clean_pushed_main",
            side_effect=L.CampaignError("live main mismatch"),
        ) as git_gate, mock.patch.object(L, "verify_stage_order") as order, mock.patch.object(
            L.subprocess, "run"
        ) as launch:
            with self.assertRaisesRegex(L.CampaignError, "live main mismatch"):
                L.execute(stage, 1, ack)
        git_gate.assert_called_once_with()
        order.assert_not_called()
        launch.assert_not_called()

    def test_mtp4_single_actual_scan_occurs_inside_campaign_lock(self) -> None:
        stage = L.STAGES["e2-mtp4-full-actual"]
        ack = f"RUN {L.CAMPAIGN_ID} {stage.stage_id} r1"
        events: list[str] = []

        @contextmanager
        def locks():
            events.append("lock-enter")
            try:
                yield
            finally:
                events.append("lock-exit")

        def single_actual_gate() -> None:
            events.append("single-actual-scan")
            raise L.CampaignError("stop after atomic scan")

        with mock.patch.object(L, "verify_dependencies", return_value={}), mock.patch.object(
            L.COMMON, "campaign_locks", side_effect=locks
        ), mock.patch.object(
            L.COMMON, "git_clean_pushed_main", return_value="a" * 40
        ), mock.patch.object(
            L, "verify_stage_order"
        ), mock.patch.object(
            L, "ensure_single_mtp4_actual", side_effect=single_actual_gate
        ), mock.patch.object(
            L.subprocess, "run"
        ) as launch:
            with self.assertRaisesRegex(L.CampaignError, "atomic scan"):
                L.execute(stage, 1, ack)
        self.assertEqual(events, ["lock-enter", "single-actual-scan", "lock-exit"])
        launch.assert_not_called()

    def test_check_does_not_require_clean_git_or_launch(self) -> None:
        with mock.patch.object(L.COMMON, "git_clean_pushed_main") as git_gate, mock.patch.object(
            L.subprocess, "run"
        ) as launch:
            # verify_dependencies uses COMMON.command/subprocess, so exercise
            # the real --check separately; this assertion proves the action
            # dispatcher never enters the execution-only gates.
            with mock.patch.object(sys, "argv", ["expansion", "--plan"]):
                self.assertEqual(L.main(), 0)
        git_gate.assert_not_called()
        launch.assert_not_called()


class ExpansionGateTests(unittest.TestCase):
    def _write_identity(self, output: Path, mtp: int) -> None:
        values = {
            "tp": "1",
            "gpus": "0",
            "mtp": str(mtp),
            "kv": "f16",
            "max_model_len": "32768",
            "cache_policy": "fresh",
            "pull_source_image": "0",
            "expected_image_id": L.IMAGE_ID,
            "resolved_image_id": L.IMAGE_ID,
            "vllm_xpu_graph": "unset",
            "require_graph_capture": "0",
            "natural_eos": "1",
            "return_token_ids": "1",
            "quality": "1",
            "quality_require_baseline": "1",
            "quality_baseline_sha256": L.DEPENDENCIES[L.BASELINE],
            "pythonhashseed": "0",
            "source_image_tag": "neural-download/vllm-openai-xpu:vllm-b2dd9ce73d-kernel-1e90ffa672-official",
            "source_image_repository": "neural-download/vllm-openai-xpu",
            "image_acquisition": "offline-replay",
            "registry_digest": L.IMAGE_ID,
            "tag_image_id": L.IMAGE_ID,
            "source_identity_path": "/opt/neural-download/source-identity.json",
            "expected_source_identity_sha256": L.SOURCE_IDENTITY_SHA256,
            "gpu_memory_utilization": "0.90",
            "prompt_ids": "all",
            "quality_baseline_json": str(L.BASELINE),
            "extra_vllm_args_json": '["--pipeline-parallel-size","1","--data-parallel-size","1","--enable-chunked-prefill","--async-scheduling"]',
        }
        (output / "identity.env").write_text(
            "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
        )
        (output / "image-id.txt").write_text(L.IMAGE_ID + "\n")
        (output / "source-identity.json").write_text(
            json.dumps(
                {
                    "vllm": {"head": L.VLLM_HEAD},
                    "kernel": {"head": L.KERNEL_HEAD},
                }
            )
            + "\n"
        )
        (output / "server-args.txt").write_text(
            "\n".join(
                [
                    L.MODEL,
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                    "--trust-remote-code",
                    "--served-model-name",
                    "qwen38-rolling-nightly-strict",
                    "--tensor-parallel-size",
                    "1",
                    "--max-model-len",
                    "32768",
                    "--max-num-seqs",
                    "1",
                    "--max-num-batched-tokens",
                    "1024",
                    "--gpu-memory-utilization",
                    "0.90",
                    "--dtype",
                    "float16",
                    "--reasoning-parser",
                    "qwen3",
                    "--default-chat-template-kwargs",
                    '{"enable_thinking": false}',
                    "--enable-prompt-tokens-details",
                    "--no-enable-prefix-caching",
                    "--speculative-config",
                    json.dumps(
                        {
                            "method": "qwen3_next_mtp",
                            "num_speculative_tokens": mtp,
                        },
                        separators=(",", ":"),
                    ),
                    "--pipeline-parallel-size",
                    "1",
                    "--data-parallel-size",
                    "1",
                    "--enable-chunked-prefill",
                    "--async-scheduling",
                ]
            )
            + "\n"
        )
        expected_inputs = {
            str(L.COMMON.MODEL_MANIFEST): L.COMMON.DEPENDENCIES[
                L.COMMON.MODEL_MANIFEST
            ],
            str(L.SHORT_SUITE): L.DEPENDENCIES[L.SHORT_SUITE],
            str(L.COMMON.BENCH_HELPER): L.COMMON.DEPENDENCIES[
                L.COMMON.BENCH_HELPER
            ],
            str(L.COMMON.QUALITY_HELPER): L.COMMON.DEPENDENCIES[
                L.COMMON.QUALITY_HELPER
            ],
            str(L.COMMON.MODEL_VERIFIER): L.COMMON.DEPENDENCIES[
                L.COMMON.MODEL_VERIFIER
            ],
            str(L.RUNNER): L.DEPENDENCIES[L.RUNNER],
        }
        (output / "input-files.sha256").write_text(
            "".join(f"{digest}  {path}\n" for path, digest in expected_inputs.items())
        )

    def test_exact_mtp2_and_mtp4_identity(self) -> None:
        for stage_id, mtp in (("e1-mtp2-full", 2), ("e2-mtp4-full-actual", 4)):
            with self.subTest(stage=stage_id), tempfile.TemporaryDirectory() as raw:
                output = Path(raw)
                self._write_identity(output, mtp)
                with mock.patch.object(
                    L, "sha256_file", return_value=L.SOURCE_IDENTITY_SHA256
                ):
                    result = L.verify_exact_run_identity(L.STAGES[stage_id], output)
                self.assertTrue(result["passed"])
                self.assertEqual(result["mtp_depth"], mtp)
                self.assertEqual(result["graph_mode"], "off")

    def test_mtp_identity_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            self._write_identity(output, 4)
            with mock.patch.object(
                L, "sha256_file", return_value=L.SOURCE_IDENTITY_SHA256
            ), self.assertRaisesRegex(L.CampaignError, "identity mismatch"):
                L.verify_exact_run_identity(L.STAGES["e1-mtp2-full"], output)

    def test_frozen_run_input_manifest_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            self._write_identity(output, 2)
            with (output / "input-files.sha256").open("a") as stream:
                stream.write("0" * 64 + "  /unexpected\n")
            with mock.patch.object(
                L, "sha256_file", return_value=L.SOURCE_IDENTITY_SHA256
            ), self.assertRaisesRegex(L.CampaignError, "frozen inputs"):
                L.verify_exact_run_identity(L.STAGES["e1-mtp2-full"], output)

    def test_full_environment_is_graph_off_quality_enabled(self) -> None:
        for stage in L.STAGES.values():
            env = L.stage_environment(stage)
            self.assertEqual(env["QUALITY"], "1")
            self.assertEqual(env["QUALITY_REQUIRE_BASELINE"], "1")
            self.assertEqual(env["BENCH"], "1")
            self.assertEqual(env["NATURAL_EOS"], "1")
            self.assertEqual(env["MAX_TOKENS"], "512")
            self.assertEqual(env["REQUIRE_GRAPH_CAPTURE"], "0")
            for variable in L.COMMON.GRAPH_VARIABLES:
                self.assertNotIn(variable, env)

    def test_acceptance_requires_positive_draft_and_accept_delta(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            (output / "metrics.before.prom").write_text(
                'vllm:spec_decode_num_draft_tokens_total{engine="0"} 10\n'
                'vllm:spec_decode_num_accepted_tokens_total{engine="0"} 5\n'
            )
            (output / "metrics.after.prom").write_text(
                'vllm:spec_decode_num_draft_tokens_total{engine="0"} 110\n'
                'vllm:spec_decode_num_accepted_tokens_total{engine="0"} 65\n'
            )
            gate = L.acceptance_gate(output)
            self.assertTrue(gate["passed"])
            self.assertEqual(gate["draft_tokens"], 100)
            self.assertEqual(gate["accepted_tokens"], 60)
            (output / "metrics.after.prom").write_text(
                'vllm:spec_decode_num_draft_tokens_total{engine="0"} 110\n'
                'vllm:spec_decode_num_accepted_tokens_total{engine="0"} 5\n'
            )
            self.assertFalse(L.acceptance_gate(output)["passed"])

    def test_target_oracle_requires_all_25_hashes_and_token_sequences(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            output = base / "candidate"
            control_root = base / "control"
            output.mkdir()
            control_root.mkdir()
            suite = json.loads(L.SHORT_SUITE.read_text())
            control = {
                "rows": [
                    {
                        "prompt_id": prompt["id"],
                        "token_ids": [index, index + 1],
                        "sha256": f"{'0' * 62}{index:02x}",
                    }
                    for index, prompt in enumerate(suite["prompts"])
                ]
            }
            (control_root / "bench.json").write_text(json.dumps(control))
            (output / "bench.json").write_text(json.dumps(control))
            with mock.patch.object(L, "CONTROL_ROOT", control_root):
                gate = L.target_oracle_gate(output)
            self.assertTrue(gate["passed"])
            self.assertEqual(gate["exact_token_id_matches"], 25)
            self.assertEqual(gate["exact_output_hash_matches"], 25)
            control["rows"][0]["token_ids"][0] += 1
            (output / "bench.json").write_text(json.dumps(control))
            with mock.patch.object(L, "CONTROL_ROOT", control_root):
                self.assertFalse(L.target_oracle_gate(output)["passed"])

    @unittest.skipUnless(
        measuring_host_evidence_available(),
        "requires frozen measuring-host full-quality control",
    )
    def test_frozen_full_quality_control_passes_complete_gate(self) -> None:
        quality = L.COMMON.load_json(L.CONTROL_ROOT / "quality.json")
        passed, details = L.COMMON.full_quality_passes(quality)
        self.assertTrue(passed)
        self.assertEqual(details["exact_count"], 7)
        self.assertEqual(details["repeat_count"], 8)
        self.assertEqual(details["baseline_comparison_count"], 24)
        self.assertEqual(details["cached_zero_count"], 16)

    def test_evaluate_requires_all_gates_but_never_speed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            (output / "final.status").write_text("pass\n")
            (output / "canary.json").write_text(
                json.dumps({"content": "14", "cached_tokens": 0})
            )
            (output / "bench.json").write_text(
                json.dumps(
                    {
                        "realistic_final_gate": {
                            "passed": True,
                            "natural_eos_required": True,
                            "cached_tokens_all_zero": True,
                        },
                        "summary": {
                            "tok_s_1_100_intervals_after_ttft": {"median": 0.001}
                        },
                        "rows": [{} for _ in range(25)],
                    }
                )
            )
            (output / "quality.json").write_text("{}\n")
            with mock.patch.object(
                L,
                "verify_exact_run_identity",
                return_value={"passed": True, "mtp_depth": 2},
            ), mock.patch.object(
                L.COMMON,
                "full_quality_passes",
                return_value=(True, {"pass_all": True}),
            ), mock.patch.object(
                L,
                "acceptance_gate",
                return_value={"passed": True},
            ), mock.patch.object(
                L,
                "target_oracle_gate",
                return_value={"passed": True},
            ):
                state, terminal, gates = L.evaluate(
                    L.STAGES["e1-mtp2-full"], output, 0
                )
            self.assertEqual(state, "passed")
            self.assertTrue(terminal)
            self.assertFalse(gates["speed_gate_applied"])

    def test_remote_advance_is_recorded_but_local_state_alone_gates(self) -> None:
        gates: dict[str, object] = {}
        state, terminal = L.apply_post_git_gate(
            "passed",
            True,
            gates,
            {
                "local_lab_unchanged": True,
                "live_origin_advanced_during_stage": True,
            },
        )
        self.assertEqual((state, terminal), ("passed", True))
        self.assertTrue(gates["live_origin_advanced_during_stage"])
        self.assertTrue(gates["remote_movement_was_non_gating"])
        state, terminal = L.apply_post_git_gate(
            "passed",
            True,
            {},
            {"local_lab_unchanged": False, "live_origin_advanced_during_stage": False},
        )
        self.assertEqual((state, terminal), ("failed", False))


if __name__ == "__main__":
    unittest.main()
