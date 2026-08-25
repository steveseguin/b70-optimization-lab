from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
VALIDATOR_PATH = HERE / "validate-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.py"
RUNNER_PATH = HERE / "run-20260825-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-r1.sh"
MANIFEST_PATH = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-q4km-f16-tp1-mtp1-parent-sentinel-prereg.json"

SPEC = importlib.util.spec_from_file_location("qwen36_mtp1_parent_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def receipt(output_hash: str) -> dict:
    return {
        "schema": "openai-token-depth-benchmark-v1",
        "status": "passed",
        "run_identity": {
            "model": "qwen36-q4km-f16-tp1",
            "depth": 8192,
            "active_context_tokens": 8192,
            "configured_context_capacity": 12288,
            "case_id": "depth-8192",
            "max_tokens": 128,
            "metric_events": 100,
            "metric_intervals": 99,
        },
        "fixture": {
            "fixture_sha256": "85b1050c88b4c1e6cb9c4ce7f1580284cd2aa68243dad0d0dff16460decbe5ac",
            "prompt_token_ids_sha256": "6baa17bea14f0ecad7e4edf54a05256eafaef1d447a447569fd303371c671741",
        },
        "gate": {"passed": True},
        "metric_window": {
            "timestamped_events": 100,
            "inter_token_intervals": 99,
            "conventional_99_interval_tok_s": 30.0,
        },
        "response": {"output_token_ids_sha256": output_hash},
    }


def usage_row() -> dict:
    return {"usage": {"prompt_tokens_details": {"cached_tokens": 0}}}


class ParentSentinelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        manifest = json.loads(MANIFEST_PATH.read_text())
        for arm in ("control-mtp0", "candidate-mtp1"):
            (self.root / arm).mkdir()
            (self.root / arm / "models.json").write_text(
                json.dumps({"data": [{"id": "qwen36-q4km-f16-tp1"}]}),
                encoding="utf-8",
            )
        output_hash = "1" * 64
        for arm in ("control-mtp0", "candidate-mtp1"):
            (self.root / arm / "exact-depth.json").write_text(
                json.dumps(receipt(output_hash)), encoding="utf-8"
            )
        (self.root / "control-mtp0/server.log").write_text("target only\n")
        (self.root / "candidate-mtp1/server.log").write_text(
            "draft acceptance = 0.75000 ( 96 accepted / 127 generated)\n"
        )
        quality = {
            "pass_all": True,
            "exact_cases": [usage_row() for _ in range(4)],
            "repeat_case": {"repeats": 2, "runs": [usage_row(), usage_row()]},
            "long_context_case": {"pass": True, **usage_row()},
        }
        (self.root / "candidate-mtp1/quality.json").write_text(
            json.dumps(quality), encoding="utf-8"
        )
        identity_lines = [
            manifest["runtime"]["binary_sha256"],
            manifest["model"]["sha256"],
            manifest["fixture"]["sha256"],
        ]
        ldd_lines = []
        for row in manifest["runtime"]["effective_local_shared_libraries"]:
            identity_lines.extend(
                (
                    f'dso={row["soname"]}|{row["path"]}|{row["sha256"]}',
                    f'ldd_resolution={row["soname"]}|{row["path"]}',
                )
            )
            ldd_lines.append(f'\t{row["soname"]} => {row["path"]} (0x1)')
        identity_lines.extend(("ldd_begin", *ldd_lines, "ldd_end"))
        (self.root / "identity.txt").write_text(
            "\n".join(identity_lines) + "\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_valid_packet_expands_without_speed_floor(self) -> None:
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertTrue(result["gate"]["passed"])
        self.assertEqual(result["status"], "passed-expand-mtp1-depth-curve")
        self.assertIsNone(result["speed_floor"])

    def test_target_output_mismatch_fails_closed(self) -> None:
        path = self.root / "candidate-mtp1/exact-depth.json"
        path.write_text(json.dumps(receipt("2" * 64)), encoding="utf-8")
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["candidate_target_output_parity"])

    def test_missing_dso_identity_capture_fails_closed(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        missing = manifest["runtime"]["effective_local_shared_libraries"][0]["sha256"]
        path = self.root / "identity.txt"
        path.write_text(path.read_text().replace(missing, ""), encoding="utf-8")
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["runtime_dso_hashes_captured"])

    def test_bare_dso_hashes_without_paths_or_ldd_fail_closed(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        identity_lines = [
            manifest["runtime"]["binary_sha256"],
            manifest["model"]["sha256"],
            manifest["fixture"]["sha256"],
            *(
                row["sha256"]
                for row in manifest["runtime"]["effective_local_shared_libraries"]
            ),
        ]
        (self.root / "identity.txt").write_text(
            "\n".join(identity_lines) + "\n", encoding="utf-8"
        )
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["runtime_dso_hashes_captured"])
        self.assertFalse(
            result["gate"]["checks"]["runtime_ldd_resolutions_captured"]
        )

    def test_unexpected_local_build_tree_dso_fails_closed(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        build_bin = Path(
            manifest["runtime"]["effective_local_shared_libraries"][0]["path"]
        ).parent
        path = self.root / "identity.txt"
        text = path.read_text()
        text = text.replace(
            "ldd_begin",
            (
                f"dso=libunexpected.so|{build_bin}/libunexpected.so|{'0' * 64}\n"
                f"ldd_resolution=libunexpected.so|{build_bin}/libunexpected.so\n"
                "ldd_begin"
            ),
        )
        text = text.replace(
            "ldd_end",
            f"libunexpected.so => {build_bin}/libunexpected.so (0x2)\nldd_end",
        )
        path.write_text(text, encoding="utf-8")
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(result["gate"]["checks"]["runtime_dso_hashes_captured"])
        self.assertFalse(
            result["gate"]["checks"]["runtime_ldd_resolutions_captured"]
        )
        self.assertFalse(result["gate"]["checks"]["no_unexpected_local_runtime_dso"])

    def test_wrong_readiness_model_alias_fails_closed(self) -> None:
        path = self.root / "candidate-mtp1/models.json"
        path.write_text(json.dumps({"data": [{"id": "wrong-model"}]}), encoding="utf-8")
        result = VALIDATOR.validate(self.root, MANIFEST_PATH)
        self.assertFalse(result["gate"]["passed"])
        self.assertFalse(
            result["gate"]["checks"]["candidate_readiness_model_alias_captured"]
        )

    def test_packet_has_all_locks_and_no_site_authority(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        self.assertEqual(len(manifest["lifecycle"]["required_locks"]), 4)
        self.assertFalse(
            manifest["frozen_interpretation"]["site_or_family_edit_authorized"]
        )
        runner = RUNNER_PATH.read_text()
        for lock in manifest["lifecycle"]["required_locks"]:
            self.assertIn(lock, runner)
        self.assertIn("set -o noclobber", runner)
        self.assertIn("--spec-draft-n-max 1", runner)
        self.assertIn('help_text="$($SERVER --help 2>&1)"', runner)
        self.assertNotIn("$SERVER --help 2>&1 | grep", runner)
        self.assertIn('"llama-batched-bench"', runner)
        self.assertIn('"VLLM::EngineCore"', runner)
        self.assertGreaterEqual(runner.count("require_idle"), 4)

    def test_process_classifier_is_identity_based_and_filename_safe(self) -> None:
        runner = RUNNER_PATH.read_text()
        start = runner.index("def is_active_model_process(comm, argv):")
        end = runner.index("\n\nmatches = []", start)
        namespace = {
            "Path": Path,
            "llama_executables": {
                "llama-bench",
                "llama-batched-bench",
                "llama-server",
            },
            "llama_comms": {
                "llama-bench",
                "llama-batched-bench",
                "llama-batched-b",
                "llama-server",
            },
            "vllm_engine_names": {"VLLM::EngineCore", "VLLM::EngineCor"},
        }
        exec(runner[start:end], namespace)
        classify = namespace["is_active_model_process"]

        self.assertTrue(classify("llama-server", ["/some/path/llama-server"]))
        self.assertTrue(classify("python3", ["python3", "-m", "vllm.entrypoints.openai.api_server"]))
        self.assertTrue(classify("vllm", ["vllm", "serve", "model-id"]))
        self.assertTrue(classify("VLLM::EngineCor", ["VLLM::EngineCore"]))
        self.assertFalse(
            classify(
                "sha256sum",
                ["sha256sum", "/evidence/a-llama-server-result.json"],
            )
        )
        self.assertFalse(
            classify(
                "python3",
                ["python3", "audit.py", "/notes/llama-bench-failure.md"],
            )
        )
        self.assertIn('raw.split(b"\\0")', runner)
        self.assertNotIn("any(marker in cmdline", runner)

    def test_all_effective_local_dsos_are_hash_gated_and_current(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        runner = RUNNER_PATH.read_text()
        libraries = manifest["runtime"]["effective_local_shared_libraries"]
        self.assertEqual(len(libraries), 8)
        for row in libraries:
            path = Path(row["path"])
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            self.assertEqual(digest.hexdigest(), row["sha256"])
            self.assertIn(row["soname"], runner)
            self.assertIn(row["path"], runner)
            self.assertIn(row["sha256"], runner)
        self.assertIn("effective_library_capture", manifest["runtime"])
        self.assertIn('ldd_text="$(ldd "$SERVER")"', runner)
        self.assertEqual(runner.count("require_ldd_target lib"), 8)
        self.assertEqual(runner.count('echo "dso=lib'), 8)
        self.assertIn("effective local build-tree DSO set mismatch", runner)

    def test_shutdown_is_bounded_term_then_kill(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        runner = RUNNER_PATH.read_text()
        self.assertIn("terminate_server_bounded()", runner)
        self.assertIn('kill -TERM "$pid"', runner)
        self.assertIn('wait_for_exit_bounded "$pid" 300', runner)
        self.assertIn('kill -KILL "$pid"', runner)
        self.assertIn('wait_for_exit_bounded "$pid" 100', runner)
        self.assertIn('terminate_server_bounded "$server_pid"', runner)
        self.assertIn("never unbounded wait", manifest["lifecycle"]["server_shutdown"])

    def test_readiness_retries_cannot_poison_final_models_artifact(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        runner = RUNNER_PATH.read_text()
        self.assertIn(
            'until curl -fsS --connect-timeout 2 --max-time 5 "$endpoint" > /dev/null; do',
            runner,
        )
        self.assertNotIn(
            'until curl -fsS "$endpoint" > "$RUN_ROOT/$arm/models.json"; do',
            runner,
        )
        self.assertIn(
            'curl -fsS --connect-timeout 2 --max-time 15 "$endpoint" -o "$models_tmp"',
            runner,
        )
        self.assertIn('ln "$models_tmp" "$RUN_ROOT/$arm/models.json"', runner)
        self.assertIn('unlink "$models_tmp"', runner)
        self.assertIn("ready endpoint did not return the frozen model alias", runner)
        self.assertIn("exclusive hard link", manifest["lifecycle"]["readiness_capture"])
        self.assertEqual(
            manifest["lifecycle"]["readiness_timeouts_seconds"],
            {
                "outer_deadline": 300,
                "probe_connect": 2,
                "probe_total": 5,
                "capture_connect": 2,
                "capture_total": 15,
            },
        )

    def test_signals_keep_nonzero_status_through_exit_cleanup(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text())
        runner = RUNNER_PATH.read_text()
        trap_lines = (
            "trap cleanup EXIT",
            "trap 'exit 130' INT",
            "trap 'exit 143' TERM",
        )
        for line in trap_lines:
            self.assertIn(line, runner)
        self.assertNotIn("trap cleanup EXIT INT TERM", runner)

        for signal, expected in (("INT", 130), ("TERM", 143)):
            script = "\n".join(
                (
                    "cleanup() { printf 'cleanup_rc=%s\\n' \"$?\"; }",
                    *trap_lines,
                    f"kill -{signal} $$",
                )
            )
            result = subprocess.run(
                ["bash", "-c", script],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, expected)
            self.assertEqual(result.stdout, f"cleanup_rc={expected}\n")
        self.assertIn("EXIT-only cleanup", manifest["lifecycle"]["signal_exit_status"])


if __name__ == "__main__":
    unittest.main()
