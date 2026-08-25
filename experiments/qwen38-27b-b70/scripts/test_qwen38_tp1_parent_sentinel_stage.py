#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONTEXT = load("qwen38_context_gate", "qwen38_tp1_context_gate.py")
LAUNCHER = load(
    "qwen38_parent_launcher",
    "run-20260825-qwen38-tp1-parent-sentinel-stage.py",
)


class ContextGateTests(unittest.TestCase):
    def good_row(self):
        return {
            "text_preview": "MARKER then explanation",
            "prompt_tokens": 2048,
            "cached_tokens": 0,
            "completion_tokens": 128,
            "stream_token_id_count": 128,
            "tok_s_1_100_intervals_after_ttft": 1.0,
        }

    def test_marker_and_actual_prompt_tokens_fail_closed(self) -> None:
        prompt = {"expected_prefix": "MARKER", "actual_prompt_tokens": 2048}
        self.assertEqual(CONTEXT.validate_context_row(self.good_row(), prompt, 100), [])
        bad = self.good_row()
        bad["text_preview"] = "wrong"
        bad["prompt_tokens"] = 2047
        failures = CONTEXT.validate_context_row(bad, prompt, 100)
        self.assertIn("retrieval-marker-mismatch", failures)
        self.assertIn("actual-prompt-token-count-mismatch", failures)

    def test_p1_depth_order_stops_before_32k_after_8k_failure(self) -> None:
        calls: list[str] = []

        def post_stream(**kwargs):
            prompt = kwargs["prompt"]
            calls.append(prompt)
            marker = f"MARK-{prompt}"
            return {
                "text_preview": marker if prompt == "2k" else "wrong marker",
                "prompt_tokens": {"2k": 2048, "8k": 8192, "32k": 32000}[prompt],
                "completion_tokens": 128,
                "stream_token_id_count": 128,
                "token_id_offsets_s": [index / 100 for index in range(128)],
                "token_ids": list(range(128)),
                "usage": {"prompt_tokens_details": {"cached_tokens": 0}},
            }

        fake_base = types.SimpleNamespace(
            post_stream=post_stream,
            safe_request_id=lambda value: value,
            cached_tokens=lambda row: row["usage"]["prompt_tokens_details"]["cached_tokens"],
            event_window_rates=lambda _offsets, _count: (10.0, 9.9),
            stats=lambda values: {"count": len(values)},
        )
        prompts = [
            {
                "id": f"context-{depth}-middle",
                "prompt": label,
                "requested_prompt_tokens": tokens,
                "actual_prompt_tokens": tokens,
                "expected_prefix": f"MARK-{label}",
            }
            for depth, label, tokens in (
                (2048, "2k", 2048),
                (8192, "8k", 8192),
                (32000, "32k", 32000),
            )
        ]
        suite = {
            "suite_id": "qwen38-b2dd-tp1-context-sentinels-v1",
            "evidence_semantics": {
                "fills_exact_active_context_axis": False,
                "input_32000_fills_active_context_32768": False,
            },
            "prompts": prompts,
        }
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            suite_path = root / "suite.json"
            output = root / "bench.json"
            suite_path.write_text(json.dumps(suite))
            argv = [
                "context-gate",
                "--base-url", "http://127.0.0.1:1",
                "--model", "test",
                "--api-mode", "chat",
                "--suite", str(suite_path),
                "--max-tokens", "128",
                "--metric-tokens", "100",
                "--seed", "1",
                "--timeout", "1",
                "--out", str(output),
                "--return-token-ids",
                "--request-extra-json", '{"ignore_eos":true}',
            ]
            with mock.patch.object(CONTEXT, "load_base_helper", return_value=fake_base), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                rc = CONTEXT.main()
            result = json.loads(output.read_text())
        self.assertEqual(rc, 2)
        self.assertEqual(calls, ["2k", "8k"])
        self.assertEqual(result["context_retrieval_gate"]["rows_completed"], 2)
        self.assertEqual(
            result["context_retrieval_gate"]["first_failure"]["prompt_id"],
            "context-8192-middle",
        )


class LauncherTests(unittest.TestCase):
    def test_load_json_reads_once(self) -> None:
        path = mock.Mock()
        path.read_text.return_value = '{"ok":true}'
        self.assertEqual(LAUNCHER.load_json(path), {"ok": True})
        path.read_text.assert_called_once_with(encoding="utf-8")

    def test_repo_frozen_dependencies_and_protected_speeds_validate(self) -> None:
        repo_dependencies = {
            path: expected
            for path, expected in LAUNCHER.DEPENDENCIES.items()
            if path != LAUNCHER.BASELINE
        }
        real_command = LAUNCHER.command

        def repo_only_validator(args, **kwargs):
            if args == [str(LAUNCHER.VALIDATOR), "--validate"]:
                args = [str(LAUNCHER.VALIDATOR), "--validate-repo-only"]
            return real_command(args, **kwargs)

        with mock.patch.object(LAUNCHER, "DEPENDENCIES", repo_dependencies), mock.patch.object(
            LAUNCHER, "command", side_effect=repo_only_validator
        ):
            observed = LAUNCHER.verify_dependencies()
        self.assertEqual(
            observed[str(LAUNCHER.PROTECTED_MANIFEST.relative_to(LAUNCHER.REPO))],
            LAUNCHER.PROTECTED_MANIFEST_SHA256,
        )

    def test_external_baseline_hash_when_mounted(self) -> None:
        if not LAUNCHER.BASELINE.is_file():
            self.skipTest("measuring-host quality baseline is not mounted")
        self.assertEqual(
            LAUNCHER.sha256_file(LAUNCHER.BASELINE),
            LAUNCHER.DEPENDENCIES[LAUNCHER.BASELINE],
        )

    def test_graph_off_scrubs_every_graph_variable(self) -> None:
        poisoned = {variable: "poison" for variable in LAUNCHER.GRAPH_VARIABLES}
        with mock.patch.dict(LAUNCHER.os.environ, poisoned, clear=False):
            env = LAUNCHER.stage_environment(
                LAUNCHER.STAGES["p2-eager-control"], None
            )
        for variable in LAUNCHER.GRAPH_VARIABLES:
            self.assertNotIn(variable, env)
        self.assertEqual(env["REQUIRE_GRAPH_CAPTURE"], "0")
        self.assertNotIn("--compilation-config", json.loads(env["EXTRA_VLLM_ARGS_JSON"]))

    def test_frozen_image_and_graph_identity_are_explicit(self) -> None:
        env = LAUNCHER.stage_environment(
            LAUNCHER.STAGES["p1-context-spine"], Path("/tmp/context.json")
        )
        self.assertEqual(env["PULL_SOURCE_IMAGE"], "0")
        self.assertEqual(
            env["EXPECTED_IMAGE_ID"],
            "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296",
        )
        self.assertEqual(env["REQUIRE_GRAPH_CAPTURE"], "1")
        self.assertEqual(env["VLLM_XPU_GRAPH"], "1")

    def test_wrong_ack_stops_before_any_preflight_or_launch(self) -> None:
        stage = LAUNCHER.STAGES["p1-context-spine"]
        with mock.patch.object(LAUNCHER, "verify_dependencies") as verify:
            with self.assertRaises(LAUNCHER.CampaignError):
                LAUNCHER.execute(stage, 1, "wrong")
        verify.assert_not_called()

    def test_clean_pushed_main_requires_local_and_live_origin(self) -> None:
        head = "a" * 40

        def clean_command(args, **_kwargs):
            joined = " ".join(args)
            if "status --porcelain" in joined:
                stdout = ""
            elif "branch --show-current" in joined:
                stdout = "main\n"
            elif "rev-parse HEAD" in joined or "rev-parse origin/main" in joined:
                stdout = head + "\n"
            elif "ls-remote" in joined:
                stdout = f"{head}\trefs/heads/main\n"
            else:
                raise AssertionError(args)
            return subprocess.CompletedProcess(args, 0, stdout, "")

        with mock.patch.object(LAUNCHER, "command", side_effect=clean_command):
            self.assertEqual(LAUNCHER.git_clean_pushed_main(), head)

        def dirty_command(args, **kwargs):
            if "status" in args:
                return subprocess.CompletedProcess(args, 0, "dirty-file\n", "")
            return clean_command(args, **kwargs)

        with mock.patch.object(LAUNCHER, "command", side_effect=dirty_command):
            with self.assertRaisesRegex(LAUNCHER.CampaignError, "must be clean"):
                LAUNCHER.git_clean_pushed_main()

    def test_post_run_remote_advance_is_recorded_but_non_gating(self) -> None:
        launch_head = "a" * 40
        live_head = "b" * 40

        def post_command(args, **_kwargs):
            joined = " ".join(args)
            if "status --porcelain" in joined:
                stdout = ""
            elif "branch --show-current" in joined:
                stdout = "main\n"
            elif "rev-parse HEAD" in joined or "rev-parse origin/main" in joined:
                stdout = launch_head + "\n"
            elif "ls-remote" in joined:
                stdout = f"{live_head}\trefs/heads/main\n"
            else:
                raise AssertionError(args)
            return subprocess.CompletedProcess(args, 0, stdout, "")

        with mock.patch.object(LAUNCHER, "command", side_effect=post_command):
            snapshot = LAUNCHER.git_post_run_snapshot(launch_head)
        self.assertTrue(snapshot["local_lab_unchanged"])
        self.assertTrue(snapshot["live_origin_advanced_during_stage"])
        self.assertTrue(snapshot["remote_movement_is_non_gating_after_launch"])

    def test_post_run_local_change_remains_gating(self) -> None:
        launch_head = "a" * 40

        def post_command(args, **_kwargs):
            joined = " ".join(args)
            if "status --porcelain" in joined:
                stdout = "changed-file\n"
            elif "branch --show-current" in joined:
                stdout = "main\n"
            elif "rev-parse HEAD" in joined or "rev-parse origin/main" in joined:
                stdout = launch_head + "\n"
            elif "ls-remote" in joined:
                stdout = f"{launch_head}\trefs/heads/main\n"
            else:
                raise AssertionError(args)
            return subprocess.CompletedProcess(args, 0, stdout, "")

        with mock.patch.object(LAUNCHER, "command", side_effect=post_command):
            snapshot = LAUNCHER.git_post_run_snapshot(launch_head)
        self.assertFalse(snapshot["local_lab_unchanged"])
        self.assertFalse(snapshot["live_origin_advanced_during_stage"])

    def test_existing_runner_rc_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            (output / "final.status").write_text("pass\n")
            self.assertEqual(LAUNCHER.infer_existing_runner_rc(output), 0)
            (output / "final.status").write_text("fail rc=17\n")
            self.assertEqual(LAUNCHER.infer_existing_runner_rc(output), 17)
            (output / "final.status").write_text("unknown\n")
            with self.assertRaisesRegex(LAUNCHER.CampaignError, "unrecognized"):
                LAUNCHER.infer_existing_runner_rc(output)

    def test_existing_phase_statuses_require_zero(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            for phase in ("canary", "bench", "quality"):
                (output / f"{phase}.status").write_text(f"{phase}_rc=0\n")
            self.assertEqual(
                LAUNCHER.verify_existing_phase_statuses(
                    LAUNCHER.STAGES["p2-eager-control"], output
                ),
                {"canary": 0, "bench": 0, "quality": 0},
            )
            (output / "quality.status").write_text("quality_rc=2\n")
            with self.assertRaisesRegex(LAUNCHER.CampaignError, "did not pass"):
                LAUNCHER.verify_existing_phase_statuses(
                    LAUNCHER.STAGES["p2-eager-control"], output
                )

    def test_full_quality_requires_all_24_frozen_comparisons(self) -> None:
        cached_zero = {"usage": {"prompt_tokens_details": {"cached_tokens": 0}}}
        quality = {
            "pass_all": True,
            "baseline_status": "passed",
            "baseline_match_all": True,
            "baseline_comparisons": {f"gate-{index}": True for index in range(24)},
            "exact_cases": [cached_zero | {"pass": True} for _ in range(7)],
            "repeat_case": {
                "pass": True,
                "repeats": 8,
                "unique_hashes": ["stable"],
                "runs": [cached_zero for _ in range(8)],
            },
            "long_context_case": cached_zero | {"pass": True},
        }
        passed, details = LAUNCHER.full_quality_passes(quality)
        self.assertTrue(passed)
        self.assertEqual(details["baseline_comparison_count"], 24)
        quality["baseline_comparisons"].pop("gate-23")
        self.assertFalse(LAUNCHER.full_quality_passes(quality)[0])

    def test_default_invocation_is_inert(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(HERE / "run-20260825-qwen38-tp1-parent-sentinel-stage.py"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("choose exactly one", result.stderr)

    def test_existing_root_fails_before_docker_or_port_checks(self) -> None:
        stage = LAUNCHER.STAGES["p1-context-spine"]
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "already-there"
            output.mkdir()
            cache = Path(raw) / "cache"
            with mock.patch.object(LAUNCHER, "layout", return_value=(output, cache, 19850)), mock.patch.object(LAUNCHER, "docker_command") as docker:
                with self.assertRaisesRegex(LAUNCHER.CampaignError, "already exists"):
                    LAUNCHER.ensure_idle(stage, 1)
            docker.assert_not_called()

    def test_occupied_port_fails_closed(self) -> None:
        stage = LAUNCHER.STAGES["p1-context-spine"]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output, cache = root / "out", root / "cache"

            def fake_command(args, **_kwargs):
                if args[0] == "findmnt":
                    return subprocess.CompletedProcess(args, 0, "ext4\n", "")
                if args[0] == "ss":
                    return subprocess.CompletedProcess(args, 0, "LISTEN occupied\n", "")
                raise AssertionError(args)

            with mock.patch.object(LAUNCHER, "layout", return_value=(output, cache, 19850)), mock.patch.object(LAUNCHER, "docker_command", return_value=subprocess.CompletedProcess(["docker"], 0, "", "")), mock.patch.object(LAUNCHER, "command", side_effect=fake_command):
                with self.assertRaisesRegex(LAUNCHER.CampaignError, "already listening"):
                    LAUNCHER.ensure_idle(stage, 1)

    def test_retry_layout_changes_root_cache_and_port(self) -> None:
        stage = LAUNCHER.STAGES["p1-context-spine"]
        r1 = LAUNCHER.layout(stage, 1)
        r2 = LAUNCHER.layout(stage, 2)
        self.assertNotEqual(r1[0], r2[0])
        self.assertNotEqual(r1[1], r2[1])
        self.assertNotEqual(r1[2], r2[2])
        self.assertTrue(str(r2[0]).startswith("/home/steve/qwen38-current-main-runs/"))

    def test_graph_mtp_parent_depends_on_eager_control_not_eager_mtp2(self) -> None:
        stage = LAUNCHER.STAGES["p4-graph-mtp1"]
        self.assertEqual(stage.required_stage, "p2-eager-control")
        self.assertEqual(stage.required_state, "passed")

    def test_context_32k_failure_becomes_terminal_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            (output / "canary.json").write_text(
                json.dumps({"content": "14", "cached_tokens": 0})
            )
            (output / "final.status").write_text("fail rc=2\n")
            (output / "bench.json").write_text(
                json.dumps(
                    {
                        "context_retrieval_gate": {
                            "passed": False,
                            "rows_completed": 7,
                            "first_failure": {
                                "prompt_id": "context-32000-early",
                                "reasons": ["retrieval-marker-mismatch"],
                            },
                        }
                    }
                )
            )
            state, terminal, gates = LAUNCHER.evaluate(
                LAUNCHER.STAGES["p1-context-spine"], output, 1, 2
            )
            self.assertEqual(state, "boundary-detected")
            self.assertTrue(terminal)
            self.assertFalse(gates["speed_gate_applied"])
            self.assertIn("16K then 24K", LAUNCHER.next_action_for(
                LAUNCHER.STAGES["p1-context-spine"], state
            ))

    def test_e5m2_unsupported_requires_exact_image_and_dtype_rejection(self) -> None:
        stage = LAUNCHER.STAGES["p6-e5m2-kv-init"]
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            (output / "final.status").write_text("fail rc=2\n")
            (output / "image-id.txt").write_text(
                "sha256:059d4b3ee881c2a54d801518d59fd26b4e3c3af8840f4c18187c8b28000bc296\n"
            )
            (output / "server.log").write_text(
                "ValueError: kv_cache_dtype fp8_e5m2 is not supported on XPU\n"
            )
            state, terminal, gates = LAUNCHER.evaluate(stage, output, 1, 2)
            self.assertEqual(state, "unsupported")
            self.assertTrue(terminal)
            self.assertEqual(
                gates["unsupported_evidence"]["classification"],
                "explicit-fp8-e5m2-kv-dtype-rejection",
            )

            (output / "server.log").write_text("RuntimeError: worker init failed\n")
            state, terminal, gates = LAUNCHER.evaluate(stage, output, 1, 2)
            self.assertEqual(state, "failed")
            self.assertFalse(terminal)
            self.assertIsNone(gates["unsupported_evidence"])

    def test_sensitive_stage_requires_acceptance_and_exact_oracle_not_speed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "candidate"
            control = root / "control"
            output.mkdir()
            control.mkdir()
            rows = [
                {
                    "prompt_id": prompt_id,
                    "token_ids": [1, 2, 3],
                    "sha256": prompt_id + "-hash",
                }
                for prompt_id in (
                    "selection--incident-retrospective",
                    "selection--technical-guide",
                )
            ]
            bench = {
                "realistic_final_gate": {"passed": True},
                "summary": {"tok_s_1_100_intervals_after_ttft": {"median": 0.01}},
                "rows": rows,
            }
            (output / "bench.json").write_text(json.dumps(bench))
            (control / "bench.json").write_text(json.dumps(bench))
            (output / "canary.json").write_text(
                json.dumps({"content": "14", "cached_tokens": 0})
            )
            (output / "final.status").write_text("pass\n")
            (output / "metrics.before.prom").write_text(
                'vllm:spec_decode_num_draft_tokens_total{engine="0"} 10\n'
                'vllm:spec_decode_num_accepted_tokens_total{engine="0"} 5\n'
            )
            (output / "metrics.after.prom").write_text(
                'vllm:spec_decode_num_draft_tokens_total{engine="0"} 110\n'
                'vllm:spec_decode_num_accepted_tokens_total{engine="0"} 65\n'
            )
            fake_receipt = control / "stage-receipt.json"
            with mock.patch.object(LAUNCHER, "receipt_path", return_value=fake_receipt):
                state, terminal, gates = LAUNCHER.evaluate(
                    LAUNCHER.STAGES["p3-eager-mtp2"], output, 1, 0
                )
            self.assertEqual(state, "passed")
            self.assertTrue(terminal)
            self.assertTrue(gates["acceptance"]["passed"])
            self.assertTrue(gates["target_oracle"]["passed"])
            self.assertFalse(gates["speed_gate_applied"])


if __name__ == "__main__":
    unittest.main()
