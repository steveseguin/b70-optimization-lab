#!/usr/bin/env python3

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
import subprocess
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "run-20260825-qwen38-b2dd9ce73d-tp1-exact-depth-r1.py"
SPEC = importlib.util.spec_from_file_location("qwen38_b2dd_exact_depth", SCRIPT)
assert SPEC and SPEC.loader
LAUNCHER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAUNCHER
SPEC.loader.exec_module(LAUNCHER)


class PacketTests(unittest.TestCase):
    def test_frozen_dependencies_and_manifest_validate(self) -> None:
        observed = LAUNCHER.verify_dependencies()
        self.assertEqual(observed[str(LAUNCHER.FIXTURE)], LAUNCHER.FIXTURE_SHA256)
        self.assertEqual(
            observed[str(LAUNCHER.BUILD_RECORD)],
            "d56dc84c1137d741042b2e295c6b1f6a40bf28a3c56e0c52761dd725e3a5caa0",
        )

    def test_plan_is_inert_and_discloses_ready_pinned_image(self) -> None:
        plan = LAUNCHER.plan_payload(1)
        self.assertTrue(plan["default_is_inert"])
        self.assertEqual(plan["depths"], list(LAUNCHER.DEPTHS))
        self.assertEqual(plan["depth_zero_state"], "missing")
        self.assertEqual(
            plan["runtime_availability"],
            "ready-exact-b2dd-image-loaded",
        )
        self.assertIsNone(plan["speed_floor"])
        self.assertIn(LAUNCHER.CAMPAIGN_ID, plan["ack"])

    def test_retry_layout_changes_root_cache_and_port(self) -> None:
        first = LAUNCHER.layout(1)
        second = LAUNCHER.layout(2)
        self.assertIn("-r1/", str(first.output))
        self.assertIn("-r2/", str(second.output))
        self.assertIn("-r2/", str(second.cache))
        self.assertEqual(second.port, first.port + 10)

    def test_wrong_ack_stops_before_dependencies_or_gpu_gates(self) -> None:
        with mock.patch.object(LAUNCHER, "verify_dependencies") as dependencies:
            with self.assertRaises(LAUNCHER.CampaignError):
                LAUNCHER.execute(1, "wrong")
        dependencies.assert_not_called()

    def test_graph_identity_is_explicit_and_no_speed_floor_exists(self) -> None:
        env = LAUNCHER.stage_environment()
        self.assertEqual(env["SOURCE_IMAGE_TAG"], LAUNCHER.IMAGE_TAG)
        self.assertEqual(env["EXPECTED_IMAGE_ID"], LAUNCHER.IMAGE_ID)
        self.assertEqual(env["PULL_SOURCE_IMAGE"], "0")
        self.assertEqual(env["VLLM_XPU_GRAPH"], "1")
        self.assertEqual(env["REQUIRE_GRAPH_CAPTURE"], "1")
        self.assertEqual(env["CACHE_POLICY"], "fresh")
        self.assertEqual(env["QUALITY_REQUIRE_BASELINE"], "1")
        extra = json.loads(env["EXTRA_VLLM_ARGS_JSON"])
        config = extra[extra.index("--compilation-config") + 1]
        self.assertEqual(json.loads(config)["cudagraph_mode"], "FULL_AND_PIECEWISE")
        self.assertIsNone(LAUNCHER.plan_payload(1)["speed_floor"])

    def test_helper_rejects_identity_drift(self) -> None:
        args = types.SimpleNamespace(
            api_mode="chat",
            suite=LAUNCHER.FIXTURE,
            max_tokens=127,
            metric_tokens=100,
            seed=1,
            return_token_ids=True,
            prompt_id=[],
            request_extra_json=json.dumps(
                {
                    "chat_template_kwargs": {"enable_thinking": False},
                    "ignore_eos": True,
                }
            ),
        )
        with self.assertRaises(LAUNCHER.CampaignError):
            LAUNCHER.validate_helper_args(args)

    def test_unavailable_or_wrong_b2dd_image_fails_before_a_run(self) -> None:
        missing = subprocess.CompletedProcess([], 1, "", "not found")
        wrong = subprocess.CompletedProcess([], 0, "sha256:wrong\n", "")
        with mock.patch.object(LAUNCHER.COMMON, "docker_command", return_value=missing):
            with self.assertRaisesRegex(LAUNCHER.CampaignError, "unavailable"):
                LAUNCHER.verify_local_image_available()
        with mock.patch.object(LAUNCHER.COMMON, "docker_command", return_value=wrong):
            with self.assertRaisesRegex(LAUNCHER.CampaignError, "wrong image ID"):
                LAUNCHER.verify_local_image_available()


class AdapterTests(unittest.TestCase):
    def fixture(self, depth: int):
        selected = types.SimpleNamespace(
            depth=depth,
            case_id=f"depth-{depth}",
            prompt_token_ids=[depth],
            prompt_token_ids_sha256=f"prompt-{depth}",
        )
        return types.SimpleNamespace(selected=selected)

    def receipt(self, fixture):
        depth = fixture.selected.depth
        return {
            "gate": {"passed": True},
            "fixture": {
                "selected_case_sha256": f"case-{depth}",
                "prompt_token_ids_sha256": f"prompt-{depth}",
            },
            "metric_window": {
                "timestamped_events": 100,
                "inter_token_intervals": 99,
                "conventional_99_interval_tok_s": float(depth),
            },
            "response": {"output_token_ids_sha256": f"output-{depth}"},
        }

    def invoke(self, output: Path) -> int:
        argv = [
            "--base-url",
            "http://127.0.0.1:20858",
            "--model",
            "qwen38-rolling-nightly-strict",
            "--api-mode",
            "chat",
            "--suite",
            str(LAUNCHER.FIXTURE),
            "--max-tokens",
            "128",
            "--metric-tokens",
            "100",
            "--seed",
            "1",
            "--timeout",
            "900",
            "--out",
            str(output),
            "--return-token-ids",
            "--request-extra-json",
            '{"chat_template_kwargs":{"enable_thinking":false},"ignore_eos":true}',
        ]
        with (
            mock.patch.object(
                LAUNCHER.DEPTH,
                "load_fixture",
                side_effect=lambda _path, depth, _case: self.fixture(depth),
            ),
            mock.patch.object(
                LAUNCHER.DEPTH,
                "request_payload",
                side_effect=lambda **kwargs: {"prompt": kwargs["prompt_token_ids"]},
            ),
            mock.patch.object(
                LAUNCHER.DEPTH,
                "post_stream",
                return_value={"token_ids": list(range(128))},
            ),
            mock.patch.object(
                LAUNCHER.DEPTH,
                "build_receipt",
                side_effect=lambda **kwargs: self.receipt(kwargs["fixture"]),
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return LAUNCHER.bench_helper_main(argv)

    def test_adapter_runs_six_depths_in_one_server_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "bench.json"
            rc = self.invoke(output)
            aggregate = json.loads(output.read_text(encoding="utf-8"))
            detail_files = sorted((output.parent / "exact-depth").glob("*.json"))
        self.assertEqual(rc, 0)
        self.assertEqual(aggregate["status"], "passed")
        self.assertTrue(aggregate["one_server"])
        self.assertEqual(aggregate["passed_depths"], list(LAUNCHER.DEPTHS))
        self.assertEqual(aggregate["depth_zero_state"], "missing")
        self.assertEqual(len(detail_files), 6)

    def test_exact_depth_gate_requires_every_declared_depth(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            aggregate = {
                "schema": "neural.download.qwen38-exact-depth-battery.v1",
                "status": "passed",
                "fixture_sha256": LAUNCHER.FIXTURE_SHA256,
                "configured_context_capacity": LAUNCHER.MAX_MODEL_LEN,
                "one_server": True,
                "depth_zero_state": "missing",
                "depth_receipts": [
                    {"depth": depth, "gate_passed": True} for depth in LAUNCHER.DEPTHS
                ],
            }
            (output / "bench.json").write_text(json.dumps(aggregate))
            passed = LAUNCHER.exact_depth_gate(output)
            aggregate["depth_receipts"][-1]["gate_passed"] = False
            (output / "bench.json").write_text(json.dumps(aggregate))
            failed = LAUNCHER.exact_depth_gate(output)
        self.assertTrue(passed["passed"])
        self.assertFalse(failed["passed"])

    def test_atomic_receipt_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw)
            first = LAUNCHER.atomic_receipt(output, {"terminal": True})
            with self.assertRaises(LAUNCHER.CampaignError):
                LAUNCHER.atomic_receipt(output, {"terminal": True})
            self.assertEqual(json.loads(first.read_text()), {"terminal": True})


if __name__ == "__main__":
    unittest.main()
