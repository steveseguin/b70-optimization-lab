#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
LEGACY = TOOLS / "run_laguna_replemb_measurement_leg.sh"
SUCCESSOR = TOOLS / "run_laguna_worker_proof_measurement_leg.sh"
VALIDATOR = TOOLS / "validate_laguna_worker_selector_evidence.py"
REPO = TOOLS.parents[2]
BASE_RUNTIME_LOCK = (
    REPO / "data/laguna-exact-small-portfolio-runtime-lock-20260801.json"
)
SUCCESSOR_RUNTIME_LOCK = (
    REPO / "data/laguna-exact-small-worker-proof-runtime-lock-20260803.json"
)
NOTE = (
    TOOLS.parent
    / "notes/2026-08-02-exact-small-worker-proof-successor-preregistration.md"
)
EXPECTED_LEGACY_SHA256 = (
    "3791fb261c0bc31f3628de079931c465020143e81a832105ccc2aa8b1252797f"
)
EXPECTED_VALIDATOR_SHA256 = (
    "b7bb4e5ee439262b2db0e01a26ae7da29f71fb011320a2907f154d534457b500"
)
EXPECTED_VLLM_COMMIT = "d6a509e6f5bddd4c426ff970da4243c3af3e5306"
EXPECTED_KERNEL_COMMIT = "46a6393fc188c11661ddab9cf1320d2f3de45087"
EXPECTED_RUNTIME_LOCK_SHA256 = (
    "90591f46c8b9204d6e967a825a57a8d2e7c58d0a055ab43a1caafe232314993f"
)
EXPECTED_GROUPED_GEMM_SHA256 = (
    "5d2d29e63f40c62d31b61808d74a0ef7ba71f2c6a62754c3220ed4d0c8281d4b"
)
EXPECTED_HELPER_SHA256 = (
    "f928404212a6886ac4408b6a478617ca5a586b43ddd3e60b7c19256aac32d049"
)
EXPECTED_EXECUTOR_SHA256 = (
    "e7a0a503a82bc5252cedba686bc080ed193d9bc1b5ed086855415b372111c54b"
)

SPEC = importlib.util.spec_from_file_location("worker_selector_validator", VALIDATOR)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WorkerProofMeasurementLegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SUCCESSOR.read_text(encoding="utf-8")
        cls.legacy_source = LEGACY.read_text(encoding="utf-8")

    def test_consumed_leg_is_still_exactly_frozen(self) -> None:
        self.assertEqual(_sha256(LEGACY), EXPECTED_LEGACY_SHA256)

    def test_successor_is_executable_and_bash_syntax_is_valid(self) -> None:
        self.assertTrue(os.access(SUCCESSOR, os.X_OK))
        completed = subprocess.run(
            ["bash", "-n", str(SUCCESSOR)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_successor_pins_all_worker_proof_sources(self) -> None:
        self.assertEqual(_sha256(VALIDATOR), EXPECTED_VALIDATOR_SHA256)
        expected_literals = {
            "expected_worker_selector_validator": EXPECTED_VALIDATOR_SHA256,
            "expected_worker_evidence_vllm": EXPECTED_VLLM_COMMIT,
            "expected_worker_evidence_kernel": EXPECTED_KERNEL_COMMIT,
            "expected_worker_evidence_helper": EXPECTED_HELPER_SHA256,
            "expected_worker_evidence_executor": EXPECTED_EXECUTOR_SHA256,
            "expected_runtime_lock": EXPECTED_RUNTIME_LOCK_SHA256,
            "expected_grouped_gemm": EXPECTED_GROUPED_GEMM_SHA256,
        }
        for name, value in expected_literals.items():
            with self.subTest(name=name):
                self.assertIn(f"readonly {name}={value}", self.source)
        self.assertIn(
            '[[ "$expected_vllm" == "$expected_worker_evidence_vllm" ]]',
            self.source,
        )
        self.assertIn(
            '[[ "$expected_kernels" == "$expected_worker_evidence_kernel" ]]',
            self.source,
        )
        self.assertIn(
            "readonly vllm_root=/home/steve/src/"
            "laguna-vllm-worker-selector-evidence-20260803",
            self.source,
        )
        self.assertIn(
            "readonly kernel_root=/home/steve/src/"
            "laguna-xpu-kernels-exact-small-portfolio-20260801",
            self.source,
        )
        self.assertIn(
            'readonly runtime_lock="$repo_root/data/'
            'laguna-exact-small-worker-proof-runtime-lock-20260803.json"',
            self.source,
        )
        self.assertNotIn("REPRO_", self.source)
        ambient_check = self.source.index('ambient_sensitive="$(compgen -e')
        python_export = self.source.index(
            "export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1"
        )
        capture_helper = self.source.index("capture_idle() {")
        self.assertLess(ambient_check, python_export)
        self.assertLess(python_export, capture_helper)
        self.assertIn(
            "/^(PYTHON|VLLM|LAGUNA|", self.source[ambient_check:python_export]
        )

        capture_end = self.source.index("verify_idle_interval()", capture_helper)
        capture = self.source[capture_helper:capture_end]
        self.assertIn("/usr/bin/env -i", capture)
        self.assertIn('PYTHONPATH="$script_dir"', capture)
        self.assertIn('"$venv_python" -S "$idle_wrapper"', capture)
        for path in (
            '"$worker_selector_validator"',
            '"$worker_evidence_helper"',
            '"$worker_evidence_executor"',
        ):
            with self.subTest(path=path):
                self.assertIn(f"check_hash {path}", self.source)

    def test_successor_runtime_lock_changes_only_worker_proof_provenance(self) -> None:
        base = json.loads(BASE_RUNTIME_LOCK.read_text(encoding="utf-8"))
        successor = json.loads(SUCCESSOR_RUNTIME_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(_sha256(SUCCESSOR_RUNTIME_LOCK), EXPECTED_RUNTIME_LOCK_SHA256)
        base["scope"] = successor["scope"]
        base["source"]["vllm"] = successor["source"]["vllm"]
        self.assertEqual(successor, base)
        self.assertEqual(successor["source"]["vllm"]["commit"], EXPECTED_VLLM_COMMIT)
        self.assertEqual(
            successor["source"]["vllm"]["worker_evidence_helper_sha256"],
            EXPECTED_HELPER_SHA256,
        )
        self.assertEqual(
            successor["source"]["vllm"]["multiproc_executor_sha256"],
            EXPECTED_EXECUTOR_SHA256,
        )

    def test_service_launch_arms_info_emission_with_all_exact_selectors(self) -> None:
        launch_start = self.source.index("setsid /usr/bin/env -i")
        launch_end = self.source.index('  "$serve_script" "$run_dir"', launch_start)
        launch = self.source[launch_start:launch_end]
        self.assertIn("LAGUNA_EXACT_SMALL_WORKER_SELECTOR_EVIDENCE=1", launch)
        self.assertIn("VLLM_LOGGING_LEVEL=INFO", launch)
        for name in validator.EXPECTED_SELECTORS:
            with self.subTest(name=name):
                self.assertIn(f"{name}=", launch)

    def test_validator_runs_after_health_and_before_metrics_or_inference(self) -> None:
        health = self.source.index(
            "curl -fsS http://127.0.0.1:18080/health >/dev/null || "
            'die "service startup timed out"'
        )
        proof = self.source.index(
            '"$venv_python" -I -S "$worker_selector_validator"', health
        )
        metrics = self.source.index(
            "curl -fsS http://127.0.0.1:18080/metrics > "
            '"$run_dir/metrics-before-suite.prom"',
            proof,
        )
        smoke_request = self.source.index(
            '  "$venv_python" "$segmented_smoke_runner"', proof
        )
        scored_request = self.source.index(
            '"$venv_python" "$benchmark" --base-url', proof
        )
        self.assertLess(health, proof)
        self.assertLess(proof, metrics)
        self.assertLess(proof, smoke_request)
        self.assertLess(proof, scored_request)

    def test_validator_uses_paired_outputs_and_lock_bound_dso_identity(self) -> None:
        validator_command = self.source.index(
            '"$venv_python" -I -S "$worker_selector_validator"'
        )
        proof_start = self.source.rfind(
            'check_hash "$venv_python"', 0, validator_command
        )
        proof_end = self.source.index(
            "verify_exact_small_route_evidence()", proof_start
        )
        proof = self.source[proof_start:proof_end]
        expected_fragments = (
            '--server-log "$run_dir/server.log"',
            '--selector-output "$run_dir/exact-small-worker-selectors.jsonl"',
            '--map-output "$run_dir/exact-small-worker-grouped-gemm-maps.jsonl"',
            '--expected-dso "$kernel_package/libgrouped_gemm_xe_2.so"',
            '--expected-dso-sha256 "$expected_grouped_gemm"',
            "PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1",
            '"$venv_python" -I -S "$worker_selector_validator"',
            'check_hash "$venv_python" "$expected_python"',
            'check_hash "$worker_selector_validator" '
            '"$expected_worker_selector_validator"',
            '/usr/bin/wc -l < "$run_dir/exact-small-worker-selectors.jsonl"',
            '/usr/bin/wc -l < "$run_dir/exact-small-worker-grouped-gemm-maps.jsonl"',
            "worker selector or mapped-DSO evidence output is incomplete",
        )
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, proof)
        self.assertNotIn("--proc-root", proof)
        self.assertNotIn("PYTHONPATH", proof)
        self.assertNotIn("|| true", proof)

    def test_legacy_worker_selector_and_pid_proof_is_removed(self) -> None:
        proof_start = self.source.index(
            'grep -Fx "LAGUNA_EXACT_SMALL_WORKER_SELECTOR_EVIDENCE=1"'
        )
        proof_end = self.source.index(
            "verify_exact_small_route_evidence()", proof_start
        )
        proof = self.source[proof_start:proof_end]
        forbidden = (
            "portfolio_workers",
            "pgrep -f 'VLLM::Worker'",
            "/proc/$worker_pid/environ",
            "worker-environment-",
            "grouped_maps",
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, proof)
        self.assertIn("portfolio_workers", self.legacy_source)
        self.assertIn("/proc/$worker_pid/environ", self.legacy_source)

    def test_identity_records_contract_and_proof_hashes(self) -> None:
        contract = validator.SELECTOR_CONTRACT_SHA256
        self.assertRegex(
            self.source,
            re.escape("readonly expected_worker_selector_contract=") + contract,
        )
        for field in (
            "worker_selector_evidence=1",
            "worker_logging_level=INFO",
            "worker_selector_contract_sha256=%s",
            "worker_selector_validator_sha256=%s",
            "worker_evidence_helper_sha256=%s",
            "worker_evidence_executor_sha256=%s",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.source)

    def test_note_records_current_component_hashes(self) -> None:
        note = NOTE.read_text(encoding="utf-8")
        for path in (SUCCESSOR_RUNTIME_LOCK, SUCCESSOR, Path(__file__)):
            with self.subTest(path=path):
                self.assertIn(_sha256(path), note)


if __name__ == "__main__":
    unittest.main()
