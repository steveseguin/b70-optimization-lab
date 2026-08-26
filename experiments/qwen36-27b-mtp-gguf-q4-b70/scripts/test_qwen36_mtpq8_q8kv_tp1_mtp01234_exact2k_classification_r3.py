#!/usr/bin/env python3
"""CPU-only fail-closed tests for Q8-KV exact-2K classification R3."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3.py"
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load(RUNNER_PATH, "qwen36_q8kv_exact2k_r3_test_runner")
VALIDATOR = load(VALIDATOR_PATH, "qwen36_q8kv_exact2k_r3_test_validator")
GATE_NAMES = {
    "cached_tokens_zero", "completion_tokens_exact", "context_capacity_covers_prompt_and_output",
    "done_seen", "endpoint_is_v1_completions", "finish_reason_length", "llama_cache_zero_if_reported",
    "llama_prompt_not_truncated", "llama_stop_is_limit", "metric_events_exact",
    "metric_intervals_exact", "metric_span_positive", "no_context_shift_reported",
    "request_disables_prompt_cache", "request_disables_prompt_truncation", "request_disables_special_tokens",
    "request_ignores_eos", "request_prompt_depth_exact", "request_prompt_hash_exact",
    "request_prompt_is_flat_integer_array", "request_returns_token_ids", "returned_prompt_ids_exact_if_reported",
    "stream_token_ids_exact", "usage_prompt_tokens_exact", "usage_total_tokens_exact",
}


class R3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="q8kv-exact2k-r3-"))
        self.root = self.temp / "root"; self.root.mkdir()
        self.manifest = RUNNER.load_manifest()
        self.runtime = RUNNER.runtime_manifest(self.manifest)
        execution = RUNNER.R1.Execution(self.runtime)
        env = RUNNER.CORE.oneapi_environment(Path(self.runtime["runtime"]["binary"]).parent)
        dsos = self.runtime["runtime"]["effective_local_shared_libraries"]
        ldd = [f"\t{row['soname']} => {row['path']} (0x1)" for row in dsos]
        self.write(self.root / "identity.json", {
            "campaign_id": RUNNER.CAMPAIGN_ID, "git_head": "1" * 40, "origin_main": "1" * 40,
            "model": {k: self.runtime["model"][k] for k in ("path", "size_bytes", "sha256", "repository", "revision")},
            "runtime": {
                **{k: self.runtime["runtime"][k] for k in ("binary", "binary_sha256", "manifest", "manifest_sha256", "source_commit")},
                "version": self.runtime["runtime"]["reported_version"], "local_dsos": dsos, "ldd": ldd,
            },
            "fixture_sha256": self.runtime["fixture"]["sha256"],
            "server_argv": {arm: execution.server_argv_for_mtp(route) for arm, route in RUNNER.ARM_PLAN},
            "runtime_environment": {key: env[key] for key in VALIDATOR.ENV_KEYS},
            "explicitly_unset_environment": VALIDATOR.EXPECTED_UNSET,
            "failed_r1_parent_hashes": {
                "terminal": self.manifest["failed_r1_parent"]["raw"]["terminal-receipt.json"],
                "identity": self.manifest["failed_r1_parent"]["raw"]["identity.json"],
            },
            "failed_r2_parent_hashes": {
                "terminal": self.manifest["failed_r2_parent"]["terminal_sha256"],
                "identity": self.manifest["failed_r2_parent"]["identity_sha256"],
            },
        })
        base = list(range(128))
        variants = {"control-mtp0a": base, "candidate-mtp1": base,
                    "candidate-mtp2": base[:26] + [900] + base[27:],
                    "candidate-mtp3": base[:26] + [900] + base[27:],
                    "candidate-mtp4": base[:26] + [900] + base[27:], "control-mtp0b": base}
        prompt_hash = self.runtime["fixture"]["prompt_token_ids_sha256"][1]
        for arm, route in RUNNER.ARM_PLAN:
            arm_dir = self.root / arm; arm_dir.mkdir()
            self.write(arm_dir / "models.json", {"data": [{"id": self.runtime["server_contract"]["model_alias"]}]})
            self.write(arm_dir / "cleanup.json", VALIDATOR.EXPECTED_CLEANUP)
            self.write(arm_dir / "arm-result.json", {"status": "completed-awaiting-classification", "error": None, "cleanup": VALIDATOR.EXPECTED_CLEANUP})
            log = "server healthy\n"
            if route > 0:
                log += "".join(f"draft acceptance = 0.85714 ( 60 accepted / 70 generated)\n" for _ in RUNNER.REPEATS)
            (arm_dir / "server.log").write_text(log, encoding="utf-8")
            for repeat in RUNNER.REPEATS:
                directory = arm_dir / f"repeat-{repeat}"; directory.mkdir()
                tokens = variants[arm]
                self.write(directory / "exact-depth.json", {
                    "schema": "openai-token-depth-benchmark-v1", "status": "passed",
                    "run_identity": {"model": self.runtime["server_contract"]["model_alias"], "depth": 2048,
                        "active_context_tokens": 2048, "case_id": "depth-2048", "configured_context_capacity": 33024,
                        "max_tokens": 128, "metric_events": 100, "metric_intervals": 99, "endpoint": "/v1/completions"},
                    "fixture": {"fixture_id": self.runtime["fixture"]["fixture_id"], "fixture_sha256": self.runtime["fixture"]["sha256"],
                        "selected_case_sha256": "d4fc9f41aecece5ca9cdcdcc21ef602c26f709235448badb0c258627bd7410f8",
                        "prompt_token_ids_sha256": prompt_hash},
                    "request": {"model": self.runtime["server_contract"]["model_alias"], "prompt_token_count": 2048,
                        "prompt_token_ids_sha256": prompt_hash, "max_tokens": 128, "seed": 1, "temperature": 0, "top_p": 1,
                        "cache_prompt": False, "add_special_tokens": False, "ignore_eos": True, "truncate_prompt_tokens": None,
                        "return_token_ids": True, "return_tokens": True, "stream": True, "stream_options": {"include_usage": True}},
                    "gate": {"passed": True, "checks": {name: True for name in GATE_NAMES}},
                    "metric_window": {"timestamped_events": 100, "inter_token_intervals": 99, "conventional_99_interval_tok_s": 10.0},
                    "response": {"token_ids": tokens, "output_token_ids_sha256": VALIDATOR.R2V.token_ids_sha256(tokens),
                        "llama_cache_n": 0, "usage": {"prompt_tokens": 2048, "completion_tokens": 128,
                        "total_tokens": 2176, "prompt_tokens_details": {"cached_tokens": 0}}},
                })
                (directory / "exact-depth.stdout.json").write_text("{}\n", encoding="utf-8")
                if route > 0:
                    self.write(directory / "draft-counters.json", {"active_context_tokens": 2048, "repeat": repeat,
                        "rows_before": repeat - 1, "rows_after": repeat,
                        "new_rows": [{"accepted": 60, "generated": 70, "ratio": 0.85714}]})

    def tearDown(self) -> None:
        shutil.rmtree(self.temp)

    @staticmethod
    def write(path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def result(self) -> dict:
        return VALIDATOR.validate(self.root, RUNNER.MANIFEST)

    def test_valid_fixture_key_and_generated_command(self) -> None:
        fixture = json.loads(RUNNER.CORE.referenced_path(self.runtime["fixture"]["path"]).read_text())
        self.assertEqual([c["id"] for c in fixture["cases"]].count(RUNNER.CASE_ID), 1)
        fake_run = type("Run", (), {"port": RUNNER.PORT})()
        command = RUNNER.repeat_command(fake_run, self.runtime, self.root)
        self.assertEqual(command[command.index("--case-id") + 1], "depth-2048")

    def test_valid_evidence_is_c(self) -> None:
        result = self.result()
        self.assertEqual((result["overall_classification"], result["packet_grade"]), ("deterministic-route-divergence", "C"))
        self.assertTrue(all(result["strict_r3_checks"].values()))

    def test_wrong_model_or_fa_fails_exact_argv(self) -> None:
        value = json.loads((self.root / "identity.json").read_text()); argv = value["server_argv"]["candidate-mtp2"]
        argv[argv.index("-m") + 1] = "/tmp/wrong.gguf"; argv[argv.index("-fa") + 1] = "off"; self.write(self.root / "identity.json", value)
        self.assert_invalid("exact_server_argv")

    def test_missing_frozen_request_identity_fails(self) -> None:
        path = self.root / "candidate-mtp1/repeat-1/exact-depth.json"
        value = json.loads(path.read_text()); del value["request"]["seed"]; self.write(path, value)
        self.assert_invalid("candidate-mtp1_repeat1_receipt")

    def test_failed_lifetime_and_extra_repeat_fail(self) -> None:
        path = self.root / "candidate-mtp2/arm-result.json"; value = json.loads(path.read_text())
        value["status"] = "failed-preserve"; value["error"] = "boom"; self.write(path, value)
        (self.root / "candidate-mtp2/repeat-4").mkdir()
        result = self.result()
        self.assertFalse(result["strict_r3_checks"]["candidate-mtp2_successful_lifetime"])
        self.assertFalse(result["strict_r3_checks"]["candidate-mtp2_exact_inventory"])
        self.assert_invalid_routes(result)

    def test_counter_must_chain_and_equal_log(self) -> None:
        path = self.root / "candidate-mtp3/repeat-2/draft-counters.json"; value = json.loads(path.read_text())
        value["rows_before"], value["rows_after"] = 0, 1; self.write(path, value)
        self.assert_invalid("candidate-mtp3_repeat2_counter")

    def test_global_environment_failure_invalidates_route_labels(self) -> None:
        path = self.root / "identity.json"; value = json.loads(path.read_text())
        value["runtime_environment"]["GGML_SYCL_ENABLE_GRAPH"] = "1"; self.write(path, value)
        result = self.assert_invalid("complete_primary_identity")
        self.assert_invalid_routes(result)

    def test_version_ldd_and_proxy_identity_are_required(self) -> None:
        path = self.root / "identity.json"; value = json.loads(path.read_text())
        value["runtime"]["version"] = "wrong"; value["runtime"]["ldd"] = []
        value["explicitly_unset_environment"] = []; self.write(path, value)
        result = self.result()
        self.assertFalse(result["strict_r3_checks"]["complete_primary_identity"])
        self.assertFalse(result["strict_r3_checks"]["runtime_ldd_closure"])
        self.assert_invalid_routes(result)

    def assert_invalid(self, key: str) -> dict:
        result = self.result(); self.assertFalse(result["strict_r3_checks"][key])
        self.assertEqual((result["overall_classification"], result["packet_grade"]), ("invalid-evidence", "D"))
        self.assert_invalid_routes(result); return result

    def assert_invalid_routes(self, result: dict) -> None:
        self.assertEqual({row["classification"] for row in result["route_comparisons"]}, {"invalid-evidence"})


if __name__ == "__main__":
    unittest.main()
