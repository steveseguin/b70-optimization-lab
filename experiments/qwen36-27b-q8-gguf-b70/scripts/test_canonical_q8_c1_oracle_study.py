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

    def test_selector_off_startup_is_not_a_route_marker(self) -> None:
        log = (
            "QWEN36_SERVER_PROCESS_BINDING pid=123\n"
            "  GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: 0\n"
        ).encode()
        prefix = {"canonical_marker_lines": []}
        fields, _ = STUDY.parse_selector_markers(log, prefix, 0, "123")
        self.assertTrue(all(fields.values()), fields)

    def test_selector_on_exact_warmup_contract(self) -> None:
        prefix_lines = [self.FLAT]
        log = (
            "QWEN36_SERVER_PROCESS_BINDING pid=123\n"
            "  GGML_SYCL_Q8_0_C2_CANONICAL_MMVQ: 1\n"
            f"{self.FLAT}\n"
            "SYCL_Q8_0_C2_CANONICAL_MMVQ summary: flat_dispatches=3 "
            "recurrent_dispatches=0 flat_multicol_suppressed=3 "
            "recurrent_dmmv_suppressed=0 reorder_ready_dispatches=3 "
            "single_col_mmvq_calls=6 violations=0\n"
        ).encode()
        fields, _ = STUDY.parse_selector_markers(
            log, {"canonical_marker_lines": prefix_lines}, 1, "123"
        )
        self.assertTrue(all(fields.values()), fields)
        malformed = log.replace(b"src1_ne=[64,2,1,1]", b"src1_ne=[64,9,1,1]")
        fields, _ = STUDY.parse_selector_markers(
            malformed,
            {"canonical_marker_lines": [prefix_lines[0].replace("64,2", "64,9")]},
            1,
            "123",
        )
        self.assertFalse(fields["selector_on_first_hit_shapes_exact"])


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
            if line.startswith("(( FAILURE_HANDOFF_MARGIN_S >= 15 ))")
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
{guard}
PASSIVE_DRAIN_S=60
start=$SECONDS
{deadline}
printf '%s\\n' "$((quiet_deadline - start))"
"""
        default = self.run_bash(script, "")
        weakened = self.run_bash(script, "14")
        minimum = self.run_bash(script, "15")
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(default.stdout, "80\n")
        self.assertEqual(weakened.returncode, 2)
        self.assertEqual(minimum.returncode, 0, minimum.stderr)
        self.assertEqual(minimum.stdout, "75\n")

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
        noarg = subprocess.run(
            ["bash", str(RUNNER)], text=True, capture_output=True, check=False
        )
        self.assertEqual(noarg.returncode, 2)
        self.assertIn("--run-phase1", noarg.stderr)

    def test_lifecycle_static_fail_closed_contract(self) -> None:
        text = RUNNER.read_text()
        required = (
            'EXPECTED_ANALYZER_SHA256="43c707c0b8040d694efa89e13638820fff5eed4cc95fa9129bcd0110452d65d6"',
            '"${1:-}" != "--run-phase1"',
            'SESSION_GATE="$session_gate"',
            "recorded_session_alive",
            "signal_recorded_session",
            "$4==sid && $5 !~ /^Z/",
            "sort -n -u",
            "PASSIVE_DRAIN_S:-60",
            "FAILURE_HANDOFF_MARGIN_S:-20",
            "FAILURE_HANDOFF_MARGIN_S >= 15",
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
        )
        for needle in required:
            self.assertIn(needle, text)
        self.assertNotIn("PARALLEL_SLOTS=1", text)

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
