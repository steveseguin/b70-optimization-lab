#!/usr/bin/env python3
"""CPU/static tests for the W13-N32 config-folder qualification."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADAPTER = load("q38_w13_folder_gate", HERE / "w13-m1-config-folder-gate.py")
SUMMARY = load(
    "q38_w13_folder_summary",
    HERE / "summarize-w13-m1-config-folder-qualification-a1.py",
)
A2_TEST = load(
    "q38_w13_a2_test",
    HERE / "test_summarize_w13_m1_xpu_graph_confirmation_a2.py",
)


def receipt(role: str) -> dict:
    folder = SUMMARY.BASE_FOLDER if role == "control" else SUMMARY.CANDIDATE_FOLDER
    return {
        "status": "pass",
        "classification": "qwen38_w13_m1_config_folder_selection_receipt",
        "role": role,
        "environment": {"VLLM_TUNED_CONFIG_FOLDER": str(folder.resolve())},
        "config": {
            "path": str((folder / SUMMARY.CONFIG_NAME).resolve()),
            "sha256": SUMMARY.BASE_HASH
            if role == "control"
            else SUMMARY.CANDIDATE_HASH,
            "base_sha256": SUMMARY.BASE_HASH,
            "candidate_sha256": SUMMARY.CANDIDATE_HASH,
        },
        "selected_batch_key": 1,
        "m1": {
            "w13": SUMMARY.PROTECTED
            if role == "control"
            else SUMMARY.PROTECTED | {"BLOCK_SIZE_N": 32},
            "w2": SUMMARY.PROTECTED,
        },
        "w2_unchanged": True,
        "source_sha256": SUMMARY.SOURCE_HASHES,
        "prerequisite": {
            "vllm_head": SUMMARY.VLLM_HEAD,
            "phase_config_patch_sha256": SUMMARY.PHASE_PATCH_HASH,
        },
        "verifier_sha256": SUMMARY.VERIFIER_HASH,
        "base_gate_sha256": SUMMARY.BASE_GATE_HASH,
    }


class ConfigFolderQualificationTests(unittest.TestCase):
    def write_matrix(self, root: Path) -> None:
        A2_TEST.ConfirmationA2SummaryTests().write_matrix(root)
        for path in root.glob("*.jsonl"):
            value = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
            role = "candidate" if path.name.endswith("-candidate.jsonl") else "control"
            value["folder_selection_receipt"] = receipt(role)
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")

    def test_summary_accepts_exact_24_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root)
            result = SUMMARY.summarize(root)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["gates"]["folder_selection_receipts_passed"], 24)
            self.assertTrue(result["gates"]["all_8_cells_exact"])

    def test_summary_fails_closed_on_one_wrong_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_matrix(root)
            path = root / "l0-r0-s20260827-candidate.jsonl"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["folder_selection_receipt"]["environment"][
                "VLLM_TUNED_CONFIG_FOLDER"
            ] = "/wrong"
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            result = SUMMARY.summarize(root)
            self.assertEqual(result["status"], "failed_closed")
            self.assertEqual(result["gates"]["folder_selection_receipts_passed"], 23)

    def test_selection_contract_rejects_candidate_as_control(self) -> None:
        base = {1: SUMMARY.PROTECTED}
        candidate = {1: SUMMARY.PROTECTED | {"W1_CONFIG": {"BLOCK_SIZE_N": 32}}}
        with self.assertRaises(ADAPTER.FolderSelectionError):
            ADAPTER.validate_selection(
                role="control",
                folder=ADAPTER.BASE_FOLDER,
                base=base,
                candidate=candidate,
                actual_w1=SUMMARY.PROTECTED | {"BLOCK_SIZE_N": 32},
                actual_w2=SUMMARY.PROTECTED,
            )

    def test_runner_has_unique_paths_and_actual_folder_env(self) -> None:
        runner = HERE / "run-q38-w13-m1-config-folder-qualification-a1.sh"
        completed = subprocess.run(
            [str(runner)],
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "Q38_W13_FOLDER_A1_SOURCE_ONLY": "1",
            },
            check=True,
            capture_output=True,
            text=True,
        )
        source = completed.stdout
        arm = source[source.index("run_arm() {") : source.index("validate_arm() {")]
        self.assertLess(arm.index("local folder role"), arm.index("local -a command"))
        self.assertIn('if [[ "$config" == "{}" ]]', arm)
        self.assertIn("VLLM_TUNED_CONFIG_FOLDER=${folder}", arm)
        self.assertIn('--folder-role "$role"', arm)
        self.assertIn('--tuned-config-folder "$folder"', arm)
        self.assertIn("w13-m1-xpu-graph-gate.py|w13-m1-config-folder-gate.py", source)
        self.assertIn("w13-m1-config-folder-gate.py' >", source)
        validate = source[source.index("validate_arm() {") :]
        self.assertNotIn("local folder role", validate)

    def test_existing_derived_sentinel_is_preserved(self) -> None:
        runner = HERE / "run-q38-w13-m1-config-folder-qualification-a1.sh"
        sentinel = Path("/dev/shm/q38-w13-m1-config-folder-qualification-a1-derived.sh")
        if sentinel.exists():
            self.skipTest("derived path already owned by another process")
        sentinel.write_text("do-not-delete\n", encoding="utf-8")
        try:
            completed = subprocess.run(
                [str(runner)],
                env={
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "Q38_W13_FOLDER_A1_SOURCE_ONLY": "1",
                },
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "do-not-delete\n")
        finally:
            if (
                sentinel.exists()
                and sentinel.read_text(encoding="utf-8") == "do-not-delete\n"
            ):
                sentinel.unlink()

    def test_validate_only_binds_transitive_dependencies(self) -> None:
        runner = HERE / "run-q38-w13-m1-config-folder-qualification-a1.sh"
        source = runner.read_text(encoding="utf-8")
        for dependency in (
            "expected_validator=2293b358",
            "expected_clearance=843fd84d",
            "expected_verifier=a464b0f6",
            "expected_base_gate=8828a3b4",
            "expected_phase_patch=ad820bad",
            "expected_base_map=91e5d8b6",
            "expected_candidate_map=a8f1f898",
        ):
            self.assertIn(dependency, source)
        completed = subprocess.run(
            [str(runner)],
            env={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "Q38_W13_FOLDER_A1_VALIDATE_ONLY": "1",
            },
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("validates without GPU work", completed.stdout)


if __name__ == "__main__":
    unittest.main()
