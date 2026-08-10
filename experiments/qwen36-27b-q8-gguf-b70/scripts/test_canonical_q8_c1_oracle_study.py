#!/usr/bin/env python3
"""Offline regression tests for the canonical-Q8 Phase-1 study harness."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ANALYZER = HERE / "canonical-q8-c1-oracle-study.py"
RUNNER = HERE / "run-canonical-q8-c1-oracle-four-gpu-wave.sh"
MATRIX_CLIENT = HERE / "capture-c2-token-matrix.py"
OLD_ORACLE = Path(
    "/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/"
    "goal1-formal-c2-gpu0-short-diag-20260809T171516.435188879Z/"
    "sequential-oracle/oracle.json"
)
OFFICIAL_C1 = Path(
    "/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/runs/"
    "goal1-isolated-baseline-gpu0-short-20260809T163733.326112517Z"
)


def load_analyzer():
    spec = importlib.util.spec_from_file_location("canonical_c1_study", ANALYZER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUDY = load_analyzer()
MATRIX = STUDY.load_module(MATRIX_CLIENT, "canonical_c2_handoff_regression")


class OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = json.loads(OLD_ORACLE.read_text())

    def failed_fields(self, value: dict) -> list[str]:
        fields, _ = STUDY.validate_oracle(
            value, STUDY.MODEL_SHA256, STUDY.RUNTIME_SHA256, STUDY.SUITE_SHA256
        )
        return [name for name, passed in fields.items() if not passed]

    def test_sealed_old_oracle_and_official_packet_pass(self) -> None:
        fields, rows = STUDY.validate_oracle(
            self.oracle,
            STUDY.MODEL_SHA256,
            STUDY.RUNTIME_SHA256,
            STUDY.SUITE_SHA256,
        )
        self.assertTrue(all(fields.values()), fields)
        official = STUDY.validate_official_c1_packet(
            OFFICIAL_C1,
            STUDY.OFFICIAL_C1_RESULT_SHA256,
            STUDY.OFFICIAL_C1_MANIFEST_SHA256,
            STUDY.OFFICIAL_C1_MARKER_SHA256,
            rows,
        )
        self.assertTrue(official["passed"], official)

    def test_identity_and_gate_mutations_fail(self) -> None:
        mutations = (
            lambda value: value["run_identity"].__setitem__("seed", True),
            lambda value: value["run_identity"].pop("slot_ids"),
            lambda value: value["intrinsic_gate"].__setitem__("rows_passed", False),
            lambda value: value["decode_occupancy"].__setitem__(
                "tokens_predicted_delta", 0
            ),
            lambda value: value["decode_occupancy"].__setitem__(
                "predicted_tokens_per_llama_decode", 0.5
            ),
        )
        for mutate in mutations:
            value = copy.deepcopy(self.oracle)
            mutate(value)
            self.assertTrue(self.failed_fields(value))

    def test_phase1_oracle_requires_no_sleep_identity(self) -> None:
        value = copy.deepcopy(self.oracle)
        value["run_identity"]["server_benchmark_identity"]["sleep_idle_seconds"] = "60"
        self.assertIn("server_benchmark_identity_exact", self.failed_fields(value))

    def test_phase2_handoff_requires_matching_no_sleep_identity(self) -> None:
        phase1_oracle_identity = copy.deepcopy(self.oracle["run_identity"])
        source_attestation = json.loads(
            Path(self.oracle["run_identity"]["server_attestation_path"]).read_text()
        )
        matched = MATRIX.attest_server(
            source_attestation,
            phase1_oracle_identity,
            STUDY.RUNTIME_SHA256,
        )
        self.assertTrue(all(matched.values()), matched)

        sleep_enabled = copy.deepcopy(source_attestation)
        sleep_enabled["expected_identity"]["sleep_idle_seconds"] = "60"
        sleep_enabled["identity_fields"]["sleep_idle_seconds"] = True
        sleep_enabled["argv_fields"]["--sleep-idle-seconds 60"] = True
        sleep_enabled["passed"] = True
        mismatch = MATRIX.attest_server(
            sleep_enabled,
            phase1_oracle_identity,
            STUDY.RUNTIME_SHA256,
        )
        self.assertFalse(mismatch["oracle_server_identity_exact"])
        self.assertFalse(all(mismatch.values()))
        analyzer_text = ANALYZER.read_text()
        self.assertIn(
            '"sleep_idle_server_argument_forbidden": True',
            analyzer_text,
        )
        self.assertIn(
            '"fresh_phase1_cohort_required": True',
            analyzer_text,
        )

    def test_row_semantic_and_canary_mutations_fail(self) -> None:
        mutations = (
            lambda value: value["rows"][0].__setitem__("stream_cache_n", 1),
            lambda value: value["rows"][0].__setitem__("replay_truncated", True),
            lambda value: value["semantic_retrieval"][0]["token_ids"].__setitem__(
                0, 99
            ),
            lambda value: value["canaries"][0].__setitem__("slot_id", False),
        )
        for mutate in mutations:
            value = copy.deepcopy(self.oracle)
            mutate(value)
            self.assertTrue(self.failed_fields(value))

        value = copy.deepcopy(self.oracle)
        tokens = value["external_baseline_canaries"][0]["token_ids"]
        tokens[0] = 99
        value["external_baseline_canaries"][0]["token_ids_sha256"] = hashlib.sha256(
            json.dumps(tokens, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertIn("external_canaries_exact", self.failed_fields(value))


class MarkerTests(unittest.TestCase):
    FLAT = (
        "SYCL_Q8_0_C2_CANONICAL_MMVQ first-hit: layout=flat "
        "path=reordered_single_col_mmvq reorder_ready=1 calls_per_dispatch=2 "
        "src0=weight src0_ne=[64,128,1,1] src1_ne=[64,2,1,1] "
        "dst_ne=[128,2,1,1]"
    )
    SUMMARY = (
        "SYCL_Q8_0_C2_CANONICAL_MMVQ summary: flat_dispatches=3 "
        "recurrent_dispatches=0 flat_multicol_suppressed=3 "
        "recurrent_dmmv_suppressed=0 reorder_ready_dispatches=3 "
        "single_col_mmvq_calls=6 violations=0"
    )

    @staticmethod
    def prefix(line_count: int, markers: list[str]) -> dict:
        return {
            "line_count": line_count,
            "canonical_marker_lines": markers,
        }

    def test_selector_off_absent_startup_and_zero_routes_pass(self) -> None:
        log = b"QWEN36_SERVER_PROCESS_BINDING pid=123\n"
        boundary = self.prefix(1, [])
        fields, _ = STUDY.parse_selector_markers(log, boundary, boundary, 0, "123")
        self.assertTrue(all(fields.values()), fields)

    def test_selector_off_rejects_every_canonical_route_marker(self) -> None:
        boundary = self.prefix(1, [])
        for marker in (
            self.FLAT,
            self.SUMMARY,
            "SYCL_Q8_0_C2_CANONICAL_MMVQ violation: injected",
        ):
            with self.subTest(marker=marker.split()[1]):
                log = f"QWEN36_SERVER_PROCESS_BINDING pid=123\n{marker}\n".encode()
                fields, _ = STUDY.parse_selector_markers(
                    log, boundary, boundary, 0, "123"
                )
                self.assertFalse(fields["selector_off_zero_canonical_route_markers"])
                self.assertFalse(all(fields.values()))

    def test_selector_on_first_hit_only_contract_without_summary(self) -> None:
        log = f"QWEN36_SERVER_PROCESS_BINDING pid=123\n{self.FLAT}\n".encode()
        boundary = self.prefix(2, [self.FLAT])
        fields, _ = STUDY.parse_selector_markers(log, boundary, boundary, 1, "123")
        self.assertTrue(all(fields.values()), fields)

    def test_selector_on_optional_summary_is_internal_check_only(self) -> None:
        log = (
            f"QWEN36_SERVER_PROCESS_BINDING pid=123\n{self.FLAT}\n{self.SUMMARY}\n"
        ).encode()
        boundary = self.prefix(2, [self.FLAT])
        fields, observed = STUDY.parse_selector_markers(
            log, boundary, boundary, 1, "123"
        )
        self.assertTrue(all(fields.values()), fields)
        self.assertTrue(observed["summary_present"])
        self.assertIn("totals are not used or claimed", observed["attribution_guard"])

        early_boundary = self.prefix(3, [self.FLAT, self.SUMMARY])
        fields, _ = STUDY.parse_selector_markers(
            log, early_boundary, early_boundary, 1, "123"
        )
        self.assertFalse(fields["summary_after_postcapture_if_present"])
        self.assertFalse(fields["selector_on_postcapture_exact_flat_marker_only"])
        self.assertFalse(all(fields.values()))

        malformed = log.replace(b"src1_ne=[64,2,1,1]", b"src1_ne=[64,9,1,1]")
        fields, _ = STUDY.parse_selector_markers(
            malformed,
            self.prefix(2, [self.FLAT.replace("64,2", "64,9")]),
            self.prefix(2, [self.FLAT.replace("64,2", "64,9")]),
            1,
            "123",
        )
        self.assertFalse(fields["selector_on_first_hit_shapes_exact"])

    def test_optional_startup_is_strict_and_ordered(self) -> None:
        boundary = self.prefix(3, [self.FLAT])
        exact = (
            "QWEN36_SERVER_PROCESS_BINDING pid=123\n"
            "  GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: 1\n"
            f"{self.FLAT}\n"
        ).encode()
        fields, _ = STUDY.parse_selector_markers(exact, boundary, boundary, 1, "123")
        self.assertTrue(all(fields.values()), fields)
        wrong = exact.replace(
            b"GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: 1",
            b"GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: 0",
        )
        fields, _ = STUDY.parse_selector_markers(wrong, boundary, boundary, 1, "123")
        self.assertFalse(fields["startup_marker_optional_but_exact"])

    def test_selector_on_rejects_duplicate_recurrent_or_late_first_hit(self) -> None:
        recurrent = (
            self.FLAT.replace("layout=flat", "layout=recurrent")
            .replace("src1_ne=[64,2,1,1]", "src1_ne=[64,1,2,1]")
            .replace("dst_ne=[128,2,1,1]", "dst_ne=[128,1,2,1]")
        )
        boundary = self.prefix(2, [self.FLAT])
        variants = (
            f"QWEN36_SERVER_PROCESS_BINDING pid=123\n{self.FLAT}\n{self.FLAT}\n",
            f"QWEN36_SERVER_PROCESS_BINDING pid=123\n{self.FLAT}\n{recurrent}\n",
        )
        for log in variants:
            with self.subTest(log=log.splitlines()[-1]):
                fields, _ = STUDY.parse_selector_markers(
                    log.encode(), boundary, boundary, 1, "123"
                )
                self.assertFalse(all(fields.values()))

        late_prefix = self.prefix(1, [])
        fields, _ = STUDY.parse_selector_markers(
            f"QWEN36_SERVER_PROCESS_BINDING pid=123\n{self.FLAT}\n".encode(),
            late_prefix,
            boundary,
            1,
            "123",
        )
        self.assertFalse(fields["selector_on_prerelease_exact_flat_hit"])

    def test_selector_on_rejects_bad_optional_summaries(self) -> None:
        boundary = self.prefix(2, [self.FLAT])
        variants = (
            self.SUMMARY.replace("flat_dispatches=3", "flat_dispatches=x"),
            self.SUMMARY + "\n" + self.SUMMARY,
            self.SUMMARY.replace("single_col_mmvq_calls=6", "single_col_mmvq_calls=5"),
            self.SUMMARY.replace("flat_dispatches=3", "flat_dispatches=0")
            .replace("flat_multicol_suppressed=3", "flat_multicol_suppressed=0")
            .replace("reorder_ready_dispatches=3", "reorder_ready_dispatches=0")
            .replace("single_col_mmvq_calls=6", "single_col_mmvq_calls=0"),
            self.SUMMARY.replace("recurrent_dispatches=0", "recurrent_dispatches=1")
            .replace("recurrent_dmmv_suppressed=0", "recurrent_dmmv_suppressed=1")
            .replace("reorder_ready_dispatches=3", "reorder_ready_dispatches=4")
            .replace("single_col_mmvq_calls=6", "single_col_mmvq_calls=8"),
            self.SUMMARY.replace("violations=0", "violations=1"),
        )
        for summary in variants:
            with self.subTest(summary=summary[-48:]):
                log = (
                    f"QWEN36_SERVER_PROCESS_BINDING pid=123\n{self.FLAT}\n{summary}\n"
                ).encode()
                fields, _ = STUDY.parse_selector_markers(
                    log, boundary, boundary, 1, "123"
                )
                self.assertFalse(all(fields.values()), fields)


class ManifestAndHealthTests(unittest.TestCase):
    @staticmethod
    def write_manifest(directory: Path, paths: list[str], name: str) -> None:
        lines = []
        for relative in sorted(paths):
            digest = hashlib.sha256((directory / relative).read_bytes()).hexdigest()
            lines.append(f"{digest}  ./{relative}\n")
        (directory / name).write_text("".join(lines))

    @staticmethod
    def xpu_sample(gpu: int, used_mib: str = "0") -> str:
        return (
            "+----------------------+-------+\n"
            f"| Device ID            | {gpu}     |\n"
            f"| GPU Memory Used (MiB)| {used_mib}     |\n"
            "+----------------------+-------+\n"
        )

    def test_exhaustive_manifest_and_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("a")
            (root / "b.txt").write_text("b")
            self.write_manifest(root, ["a.txt", "b.txt"], "artifacts.sha256")
            self.assertTrue(STUDY.parse_manifest(root, "artifacts.sha256")[0])
            (root / "uncovered.txt").write_text("x")
            self.assertFalse(STUDY.parse_manifest(root, "artifacts.sha256")[0])
            (root / "uncovered.txt").unlink()
            os.symlink("a.txt", root / "link")
            self.assertFalse(STUDY.parse_manifest(root, "artifacts.sha256")[0])

    def test_global_health_manifest_is_evidence_backed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = {"postwave-group-members-before-reap.txt"}
            for prefix in ("preprobe", "postprobe"):
                names.update(
                    {
                        f"{prefix}-group-members.txt",
                        f"{prefix}-lane-listeners.txt",
                        f"{prefix}-lane-listeners.stderr",
                        f"{prefix}-processes.txt",
                        f"{prefix}-processes.stderr",
                        f"{prefix}-log-error-scan.txt",
                        f"{prefix}-log-error-scan.stderr",
                        f"{prefix}-kernel-journal.txt",
                        f"{prefix}-kernel-journal.stderr",
                        f"{prefix}-device-error-scan.txt",
                        f"{prefix}-device-error-scan.stderr",
                        f"{prefix}-passive-status.env",
                    }
                )
            names.update(
                {f"xpu-smi-final-gpu{gpu}.txt" for gpu in range(4)}
                | {"xpu-final-used.tsv", "global-cleanup-status.env"}
            )
            for name in names:
                (root / name).write_text("")
            for prefix in ("preprobe", "postprobe"):
                (root / f"{prefix}-passive-status.env").write_text(
                    "passive_fault_detected=0\n"
                )
                (root / f"{prefix}-kernel-journal.txt").write_text("clean journal\n")
            for gpu in range(4):
                (root / f"xpu-smi-final-gpu{gpu}.txt").write_text(self.xpu_sample(gpu))
            (root / "xpu-final-used.tsv").write_text(
                "".join(f"gpu={gpu}\tused_mib=0\n" for gpu in range(4))
            )
            (root / "global-cleanup-status.env").write_text("clean\n")
            self.write_manifest(root, sorted(names), "global-health-evidence.sha256")
            manifest = root / "global-health-evidence.sha256"
            health = {
                "evidence_manifest_path": str(manifest.resolve()),
                "evidence_manifest_sha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
            }
            fields, _ = STUDY.validate_global_health_evidence(root, health)
            self.assertTrue(all(fields.values()), fields)
            (root / "preprobe-group-members.txt").write_text("survivor\n")
            fields, _ = STUDY.validate_global_health_evidence(root, health)
            self.assertFalse(all(fields.values()))

            (root / "preprobe-group-members.txt").write_text("")
            (root / "xpu-smi-final-gpu0.txt").write_text(self.xpu_sample(3))
            self.write_manifest(root, sorted(names), "global-health-evidence.sha256")
            health["evidence_manifest_sha256"] = hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest()
            fields, _ = STUDY.validate_global_health_evidence(root, health)
            self.assertFalse(fields["xpu_evidence_exact"])

            (root / "xpu-smi-final-gpu0.txt").write_text(self.xpu_sample(0, "1"))
            self.write_manifest(root, sorted(names), "global-health-evidence.sha256")
            health["evidence_manifest_sha256"] = hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest()
            fields, _ = STUDY.validate_global_health_evidence(root, health)
            self.assertFalse(fields["xpu_evidence_exact"])

    def test_xpu_stats_parser_rejects_malformed_or_ambiguous_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "stats.txt"
            path.write_text(self.xpu_sample(2, "43.0"))
            self.assertEqual(STUDY.parse_xpu_stats_file(path), (2, 43))
            for payload in (
                "sample\n",
                self.xpu_sample(2, "N/A"),
                self.xpu_sample(2, "43.5"),
                self.xpu_sample(2) + "| Device ID | 2 |\n",
                self.xpu_sample(2) + "| GPU Memory Used (MiB) | 0 |\n",
            ):
                path.write_text(payload)
                self.assertIsNone(STUDY.parse_xpu_stats_file(path))


class RunnerStaticTests(unittest.TestCase):
    @staticmethod
    def shell_function(name: str, following_name: str) -> str:
        runner_text = RUNNER.read_text()
        start = runner_text.index(f"{name}() {{\n")
        end = runner_text.index(f"\n{following_name}() {{", start)
        return runner_text[start:end]

    @staticmethod
    def run_bash(script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", script, "bash", *arguments],
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def shell_slice(start_marker: str, end_marker: str) -> str:
        runner_text = RUNNER.read_text()
        start = runner_text.index(start_marker)
        end = runner_text.index(end_marker, start)
        return runner_text[start:end]

    def test_shell_xpu_parser_binds_device_and_memory(self) -> None:
        runner_text = RUNNER.read_text()
        start = runner_text.index("parse_gpu_used_mib() {\n")
        end = runner_text.index("\n}\n\ncapture_model_stat()", start) + 3
        function_text = runner_text[start:end]
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "stats.txt"
            sample.write_text(ManifestAndHealthTests.xpu_sample(2, "43.0"))
            command = function_text + '\nparse_gpu_used_mib "$1" "$2"'
            valid = subprocess.run(
                ["bash", "-c", command, "bash", str(sample), "2"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertEqual(valid.stdout, "43\n")
            wrong_gpu = subprocess.run(
                ["bash", "-c", command, "bash", str(sample), "1"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(wrong_gpu.returncode, 0)
            sample.write_text(ManifestAndHealthTests.xpu_sample(2, "43.5"))
            fractional = subprocess.run(
                ["bash", "-c", command, "bash", str(sample), "2"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(fractional.returncode, 0)

    def test_owned_child_group_uses_argument_not_caller_gpu(self) -> None:
        function = self.shell_function("owned_child_group", "recorded_session_alive")
        script = f"""
set -u
declare -a CHILD_PIDS=([0]=100 [1]=200)
declare -a CHILD_START_TICKS=([0]=10 [1]=20)
declare -a CHILD_PGIDS=([0]=100 [1]=200)
declare -a CHILD_SIDS=([0]=100 [1]=200)
gpu=1
pid_running() {{ [[ "$1" == 100 ]]; }}
process_start_ticks() {{ [[ "$1" == 100 ]] && printf '10\\n'; }}
ps() {{
  if [[ "$*" == *"pgid="* ]]; then printf '100\\n'
  elif [[ "$*" == *"sid="* ]]; then printf '100\\n'
  else return 2
  fi
}}
group_alive() {{ [[ "$1" == 100 ]]; }}
{function}
owned_child_group 0
"""
        result = self.run_bash(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_recorded_session_alive_exact_rc_semantics(self) -> None:
        function = self.shell_function(
            "recorded_session_alive", "signal_recorded_session"
        )
        script = f"""
set -u
declare -a CHILD_PGIDS=([0]=100 [1]=200)
declare -a CHILD_SIDS=([0]=100 [1]=200)
gpu=1
PS_MODE="$1"
ps() {{
  case "$PS_MODE" in
    active) printf '100 100 S\\n' ;;
    none) printf '200 200 S\\n' ;;
    error) return 2 ;;
  esac
}}
{function}
recorded_session_alive 0
"""
        active = self.run_bash(script, "active")
        none = self.run_bash(script, "none")
        error = self.run_bash(script, "error")
        self.assertEqual(active.returncode, 0, active.stderr)
        self.assertEqual(none.returncode, 1, none.stderr)
        self.assertEqual(
            error.returncode,
            0,
            "a process-query error must conservatively report the session alive",
        )

    def test_signal_recorded_session_uses_argument_sid(self) -> None:
        function = self.shell_function(
            "signal_recorded_session", "capture_recorded_group_members"
        )
        script = f"""
set -u
declare -a CHILD_SIDS=([0]=100 [1]=200)
gpu=1
ps() {{ printf '111 100 S\\n222 200 S\\n333 100 Z\\n'; }}
kill() {{ printf '%s\\n' "$*"; }}
{function}
signal_recorded_session 0 TERM
"""
        result = self.run_bash(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "-TERM -- -111\n")

    def test_failure_handoff_margin_guard_and_deadline(self) -> None:
        runner_lines = RUNNER.read_text().splitlines()
        assignment = next(
            line
            for line in runner_lines
            if line.startswith('FAILURE_HANDOFF_MARGIN_S="${')
        )
        guard = next(
            line
            for line in runner_lines
            if line.startswith("(( FAILURE_HANDOFF_MARGIN_S >= 40 ")
        )
        deadline = next(
            line.strip()
            for line in runner_lines
            if "SECONDS + PASSIVE_DRAIN_S + FAILURE_HANDOFF_MARGIN_S" in line
        )
        script = f"""
die() {{ exit 2; }}
FAILURE_HANDOFF_MARGIN_S="$1"
{assignment}
KEEP_AWAKE_REQUEST_TIMEOUT_S=15
{guard}
PASSIVE_DRAIN_S=60
start=$SECONDS
{deadline}
printf '%s\\n' "$((quiet_deadline - start))"
"""
        default = self.run_bash(script, "")
        weakened = self.run_bash(script, "39")
        minimum = self.run_bash(script, "40")
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(default.stdout, "100\n")
        self.assertEqual(weakened.returncode, 2)
        self.assertEqual(minimum.returncode, 0, minimum.stderr)
        self.assertEqual(minimum.stdout, "100\n")

    def test_transition_cleanup_requires_bound_pid_identity(self) -> None:
        functions = self.shell_slice("pid_running() {\n", "group_alive() {\n")
        script = f"""
set -u
{functions}
sleep 30 &
child=$!
identity="$(process_identity "$child")" || exit 10
read -r parent ticks <<< "$identity"
[[ "$parent" == "$$" ]] || exit 11
bound_pid_running "$child" "$parent" "$ticks" || exit 12
if bound_pid_running "$child" "$((parent + 1))" "$ticks"; then exit 13; fi
if bound_pid_running "$child" "$parent" "$((ticks + 1))"; then exit 14; fi
if bound_pid_running "$child" "" "$ticks"; then exit 15; fi
kill -TERM "$child"
wait "$child" 2>/dev/null || true
if bound_pid_running "$child" "$parent" "$ticks"; then exit 16; fi
"""
        result = self.run_bash(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = RUNNER.read_text()
        transition = text[text.index("transition_deadline=$((SECONDS + 10))") :]
        transition = transition[: transition.index('die "child $gpu did not enter')]
        self.assertNotIn('[[ -z "$launch_ticks"', transition)
        for signal_line in ('kill -TERM "$launch_pid"', 'kill -KILL "$launch_pid"'):
            self.assertIn(signal_line, transition)
            self.assertIn(
                'bound_pid_running "$launch_pid" "$launch_ppid" "$launch_ticks"',
                transition,
            )
        self.assertIn("signals_sent=0", transition)

    def test_phase1_pins_server_sleep_disabled(self) -> None:
        text = RUNNER.read_text()
        self.assertIn("  SLEEP_IDLE_SECONDS=-1 \\\n", text)
        self.assertNotIn("--sleep-idle-seconds", text)
        self.assertNotIn("PHASE1_SLEEP_IDLE_SECONDS", text)
        self.assertNotIn("keep-awake", text)
        self.assertNotIn("intentional idle unload", text)

    def test_log_prefix_snapshot_waits_for_stable_complete_line(self) -> None:
        stable = self.shell_function("stable_log_size", "wait_for_stable_line_boundary")
        wait = self.shell_function("wait_for_stable_line_boundary", "seal_directory")
        copy = self.shell_function("copy_file_new", "stable_log_size")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stable_log = root / "stable.log"
            partial_log = root / "partial.log"
            growing_log = root / "growing.log"
            snapshot = root / "snapshot.log"
            stable_log.write_bytes(b"first complete line\n")
            partial_log.write_bytes(b"partial final line")
            growing_log.write_bytes(b"initial line\n")
            script = f"""
set -u
WAVE_ABORT_FILE="$1/abort"
owned_server_running() {{ return 0; }}
{copy}
{stable}
{wait}
stable_size="$(wait_for_stable_line_boundary "$1/stable.log" 2)" || exit 10
printf 'appended after freeze' >> "$1/stable.log"
copy_file_new "$1/stable.log" "$1/snapshot.log" "$stable_size" || exit 11
[[ "$(cat "$1/snapshot.log")" == 'first complete line' ]] || exit 12
wait_for_stable_line_boundary "$1/partial.log" 1 >/dev/null 2>&1 && exit 13
(
  while :; do
    printf 'growing line\n' >> "$1/growing.log"
    sleep 0.05
  done
) &
writer=$!
set +e
wait_for_stable_line_boundary "$1/growing.log" 1 >/dev/null 2>&1
unstable_rc=$?
set -e
kill "$writer" 2>/dev/null || true
wait "$writer" 2>/dev/null || true
[[ "$unstable_rc" -ne 0 ]] || exit 14
"""
            result = self.run_bash(script, str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(snapshot.read_bytes(), b"first complete line\n")

    def test_log_prefix_stability_wait_aborts_on_peer_or_server_loss(self) -> None:
        stable = self.shell_function("stable_log_size", "wait_for_stable_line_boundary")
        wait = self.shell_function("wait_for_stable_line_boundary", "seal_directory")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "server.log"
            log.write_text("complete line\n")
            script = f"""
set -u
WAVE_ABORT_FILE="$1/abort"
{stable}
{wait}
owned_server_running() {{ return 1; }}
if wait_for_stable_line_boundary "$1/server.log" 2 >/dev/null 2>&1; then exit 10; fi
owned_server_running() {{ return 0; }}
: > "$WAVE_ABORT_FILE"
if wait_for_stable_line_boundary "$1/server.log" 2 >/dev/null 2>&1; then exit 11; fi
"""
            result = self.run_bash(script, str(root))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_prerelease_route_snapshot_precedes_binding_and_capture(self) -> None:
        text = RUNNER.read_text()
        prerelease = text.index(
            'copy_file_new "$RUN_DIR/server.stdout.log" '
            '"$RUN_DIR/prerelease-prefix.log"'
        )
        release = text.index(
            "jq -e '.released==true and .phase==\"canonical-q8-c1-oracle\"'"
        )
        binding = text.index('python3 "$ANALYZER" capture-live-binding', release)
        capture = text.index(
            'timeout --signal=TERM --kill-after=30 "$REQUEST_TIMEOUT_S"', binding
        )
        self.assertLess(prerelease, release)
        self.assertLess(release, binding)
        self.assertLess(binding, capture)

    def test_post_attestation_failure_trap_preserves_cause_and_seals(self) -> None:
        seal = self.shell_slice("seal_directory() {\n", "validate_lease_fd() {\n")
        owned = self.shell_slice(
            "  owned_server_running() {\n", "  publish_abort() {\n"
        )
        publish = self.shell_slice("  publish_abort() {\n", "  child_error() {\n")
        failure = self.shell_slice(
            "  child_failure() {\n", "  trap child_failure EXIT\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "lane"
            run_dir.mkdir()
            script = f"""
set -Eeuo pipefail
RUN_DIR="$1"
WAVE_ABORT_FILE="$2"
GPU_INDEX=2
SELECTOR=1
PASSIVE_DRAIN_S=60
TERM_GRACE_S=90
KILL_GRACE_S=10
CHILD_STATE_ACTIVE=1
CHILD_FAILURE_REASON='post-attestation validation failed with rc=7'
CHILD_SERVER_PID=''
CHILD_SERVER_START_TICKS=''
CHILD_SERVER_PGID=''
CHILD_CLEANUP_FORCED=0
CHILD_CLEANUP_SURVIVOR=0
CHILD_NORMAL_COMPLETE=0
pid_running() {{ return 1; }}
process_start_ticks() {{ return 1; }}
{seal}
{owned}
{publish}
{failure}
trap child_failure EXIT
force_post_attestation_failure() {{
  local server_pid='out-of-scope-decoy'
  return 7
}}
force_post_attestation_failure
"""
            result = self.run_bash(script, str(run_dir), str(root / "abort"))
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertNotIn("unbound variable", result.stderr)
            cleanup = (run_dir / "cleanup-status.env").read_text()
            self.assertIn("exit_status=7\n", cleanup)
            self.assertIn(
                "failure_reason=post-attestation\\ validation\\ failed\\ with\\ rc=7\n",
                cleanup,
            )
            self.assertEqual((run_dir / "run-status.txt").read_text(), "FAIL\n")
            self.assertTrue((run_dir / "artifacts.sha256").is_file())
            subprocess.run(
                ["sha256sum", "-c", "artifacts.sha256"],
                cwd=run_dir,
                check=True,
                capture_output=True,
                text=True,
            )

    def test_shell_syntax_plan_and_default_fail_closed(self) -> None:
        subprocess.run(["bash", "-n", str(RUNNER)], check=True)
        plan = subprocess.run(
            ["bash", str(RUNNER), "--print-wave-plan"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.splitlines()
        self.assertEqual(len(plan), 4)
        self.assertIn("gpu=0\tselector=0", plan[0])
        self.assertIn("gpu=3\tselector=1", plan[3])
        self.assertTrue(all("c65536-np2-no-kv-unified" in row for row in plan))
        self.assertTrue(all("server_sleep=disabled" in row for row in plan))
        noarg = subprocess.run(
            ["bash", str(RUNNER)], text=True, capture_output=True, check=False
        )
        self.assertEqual(noarg.returncode, 2)
        self.assertIn("--run-phase1", noarg.stderr)

    def test_lifecycle_static_fail_closed_contract(self) -> None:
        text = RUNNER.read_text()
        required = (
            'EXPECTED_ANALYZER_SHA256="83e956070365a57d2e0d7910d72f9fa723538a661d91d3bb7ad51b45a3fc38a2"',
            'EXPECTED_LAUNCHER_SHA256="fa9475956c9de8dc225e23c13b25e5851bc545ae24ec1ede92939f3ae7f08010"',
            'EXPECTED_SERVER_ATTESTER_SHA256="3ca549cd971fd76b3152c8bb9e0a55689eb398051ee61a2ed2e532b3f8b2ec78"',
            '"${1:-}" != "--run-phase1"',
            'SESSION_GATE="$session_gate"',
            "recorded_session_alive",
            "signal_recorded_session",
            "$4==sid && $5 !~ /^Z/",
            "sort -n -u",
            "PASSIVE_DRAIN_S:-60",
            "FAILURE_HANDOFF_MARGIN_S:-40",
            "FAILURE_HANDOFF_MARGIN_S >= 40",
            "SECONDS + PASSIVE_DRAIN_S + FAILURE_HANDOFF_MARGIN_S",
            "phase_passive_scan preprobe",
            "phase_passive_scan postprobe",
            "preflight_pgrep_rc == 1",
            'parse_gpu_used_mib "$RUN_DIR/xpu-smi-before.txt" "$GPU_INDEX"',
            'parse_gpu_used_mib "$RUN_DIR/xpu-smi-loaded.txt" "$GPU_INDEX"',
            'parse_gpu_used_mib "$WAVE_DIR/xpu-smi-final-gpu${gpu}.txt" "$gpu"',
            "skipped: prior final XPU probe failed",
            "global-health-evidence.sha256",
            "global-cleanup-status.env",
            "--mode sequential-oracle",
            "CTX_SIZE=65536 PARALLEL_SLOTS=2",
            "KV_UNIFIED=0",
            "SLEEP_IDLE_SECONDS=-1",
            "PREFIX_STABILITY_TIMEOUT_S=10",
            "PREFIX_STABILITY_TIMEOUT_S >= 2",
            "PREFIX_STABILITY_TIMEOUT_S <= 15",
            "wait_for_stable_line_boundary",
            'copy_file_new "$RUN_DIR/server.stdout.log" "$RUN_DIR/prerelease-prefix.log"',
            'copy_file_new "$RUN_DIR/server.stdout.log" "$RUN_DIR/postcapture-prefix.log"',
            '--binding-before "$RUN_DIR/live-binding-before.json"',
            '--binding-after "$RUN_DIR/live-binding-after.json"',
        )
        for needle in required:
            self.assertIn(needle, text)
        self.assertNotIn("PARALLEL_SLOTS=1", text)
        self.assertNotIn("--binding-sleeping", text)
        self.assertNotIn("keep-awake", text)

    def test_isolated_session_detects_secondary_timeout_process_group(self) -> None:
        """Exercise the exact SID-wide cleanup premise without touching XPU."""

        child = subprocess.Popen(
            [
                "setsid",
                "--wait",
                "bash",
                "-c",
                "timeout 30 sleep 30 & wait",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        owned_sid: int | None = None
        owned_groups: set[int] = set()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    pgid = os.getpgid(child.pid)
                    sid = os.getsid(child.pid)
                except ProcessLookupError:
                    self.fail("isolated-session leader exited during transition")
                if pgid == child.pid and sid == child.pid:
                    owned_sid = sid
                    break
                time.sleep(0.02)
            self.assertEqual(owned_sid, child.pid)
            self.assertNotEqual(owned_sid, os.getsid(0))

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                table = subprocess.run(
                    ["ps", "-eo", "pid=,pgid=,sid=,stat="],
                    check=True,
                    text=True,
                    capture_output=True,
                ).stdout
                owned_groups = {
                    int(parts[1])
                    for line in table.splitlines()
                    if len(parts := line.split()) >= 4
                    and int(parts[2]) == owned_sid
                    and not parts[3].startswith("Z")
                }
                if len(owned_groups) >= 2:
                    break
                time.sleep(0.05)
            self.assertGreaterEqual(
                len(owned_groups),
                2,
                "GNU timeout must be represented by a secondary PGID in the SID",
            )
        finally:
            # Signal every PGID in the owned SID, with the session leader last.
            # The explicit self-SID inequality above prevents collateral cleanup.
            for group in sorted(owned_groups, key=lambda value: value == child.pid):
                try:
                    os.killpg(group, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                table = subprocess.run(
                    ["ps", "-eo", "pgid=,sid=,stat="],
                    check=True,
                    text=True,
                    capture_output=True,
                ).stdout
                residual_groups = {
                    int(parts[0])
                    for line in table.splitlines()
                    if len(parts := line.split()) >= 3
                    and owned_sid is not None
                    and int(parts[1]) == owned_sid
                    and not parts[2].startswith("Z")
                }
                for group in residual_groups:
                    try:
                        os.killpg(group, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
