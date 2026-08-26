#!/usr/bin/env python3
"""Focused inert tests for the superseding official FP8 TP1 fit/depth R2 packet."""

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LANE = REPO / "experiments/qwen38-27b-b70"
R1 = LANE / "data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r1-prereg.json"
R2 = LANE / "data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r2-prereg.json"
RUNNER = HERE / "run-20260826-qwen38-official-fp8-tp1-fit-depth-r2.sh"
VERIFIER = HERE / "verify-20260826-qwen38-official-fp8-tp1-fit-depth-r1.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r1 = json.loads(R1.read_text())
        cls.r2 = json.loads(R2.read_text())
        cls.runner = RUNNER.read_text()

    def test_r1_is_immutable_and_explicitly_superseded_not_run(self):
        supersedes = self.r2["supersedes"]
        self.assertEqual(supersedes["campaign_id"], self.r1["campaign_id"])
        self.assertEqual(supersedes["state"], "superseded-not-run")
        self.assertEqual(supersedes["manifest_sha256"], sha256(R1))
        self.assertEqual(
            supersedes["runner_sha256"],
            sha256(HERE / "run-20260826-qwen38-official-fp8-tp1-fit-depth-r1.sh"),
        )

    def test_exact_model_image_ladder_and_only_budget_correction(self):
        self.assertEqual(self.r2["model"]["revision"], self.r1["model"]["revision"])
        self.assertEqual(self.r2["model"]["target_path"], self.r1["model"]["target_path"])
        self.assertEqual(self.r2["model"]["direct_manifest"], self.r1["model"]["direct_manifest"])
        for key in ("image", "vllm_version", "vllm_source"):
            self.assertEqual(self.r2["runtime"][key], self.r1["runtime"][key])
        self.assertEqual(self.r2["fit_ladder"], self.r1["fit_ladder"])
        r1_server = dict(self.r1["server_contract"])
        r2_server = dict(self.r2["server_contract"])
        self.assertEqual(r1_server.pop("gpu_memory_utilization"), 0.98)
        self.assertEqual(r2_server.pop("gpu_memory_utilization"), 0.96)
        self.assertEqual(r2_server, r1_server)
        self.assertEqual(self.r2["failure_policy"], self.r1["failure_policy"])
        self.assertEqual(self.r2["publication"], self.r1["publication"])
        self.assertEqual(self.r2["execution_contract"]["descending_order"], [8192, 4096, 2048])
        self.assertEqual(
            self.r2["execution_contract"]["only_configuration_delta_from_r1"],
            "gpu_memory_utilization 0.98 -> 0.96",
        )

    def test_r19_r20_r21_evidence_is_hash_bound(self):
        expected = {
            "r19": ("19ec8da82d8d3c0328084e0fcea53c2d14833d357a1a2387b1b71370c07b3125", "0.98"),
            "r20": ("466e1c7f783af8eda13c4bb1f28cfd8952c4c820bc84712156d318be2b6c5142", "0.96"),
            "r21": ("1673675327a0decfa994f1a99e97ce4e295fe9ac3235a53b10a18dc54e253e7e", "enforce-eager"),
        }
        for key, (digest, phrase) in expected.items():
            row = self.r2["rebased_fit_evidence"][key]
            path = REPO / row["path"]
            self.assertEqual(row["sha256"], digest)
            self.assertEqual(sha256(path), digest)
            self.assertIn(phrase, row["finding"])
        self.assertIn("0.96", self.r2["rebased_fit_evidence"]["frozen_conclusion"])
        self.assertIn("No R21 concurrency", self.r2["rebased_fit_evidence"]["frozen_conclusion"])

    def test_reused_verifier_is_exact_and_runner_is_inert(self):
        verifier = self.r2["frozen_inputs"]["strict_verifier_reused_exact"]
        self.assertEqual(verifier["path"], VERIFIER.relative_to(REPO).as_posix())
        self.assertEqual(verifier["sha256"], sha256(VERIFIER))
        result = subprocess.run(["bash", str(RUNNER)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["gpu_actions"], 0)
        self.assertEqual(plan["network_actions"], 0)
        self.assertEqual(plan["download_actions"], 0)
        self.assertEqual(plan["verification_actions"], 0)
        self.assertEqual(plan["readiness"]["expected_files"], 66)
        self.assertEqual(plan["readiness"]["complete_size_matched_files"], 66)

    def test_fresh_r2_identities_and_frozen_runner_policy(self):
        lifecycle = self.r2["lifecycle"]
        self.assertEqual(lifecycle["output_root"], "/mnt/fast-ai/bench-results/qwen38-official-fp8-tp1-fit-depth-20260826-r2")
        self.assertEqual(lifecycle["cache_root"], "/mnt/fast-ai/vllm-cache/qwen38-official-fp8-f01e-tp1-fit-depth-r2")
        self.assertEqual(lifecycle["container_prefix"], "qwen38-official-fp8-tp1-fit-r2")
        self.assertEqual(lifecycle["port"], 19456)
        self.assertIn("--gpu-memory-utilization 0.96", self.runner)
        self.assertNotIn("--gpu-memory-utilization 0.98", self.runner)
        self.assertIn("--enforce-eager", self.runner)
        self.assertIn("'8192:8448:8192,4096,2048' '4096:4352:4096,2048' '2048:2304:2048'", self.runner)
        self.assertIn("qwen38-official-fp8-tp1-fit-r2-${depth}", self.runner)
        self.assertNotIn("docker pull", self.runner)
        self.assertNotIn("snapshot_download", self.runner)
        syntax = subprocess.run(["bash", "-n", str(RUNNER)], text=True, capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)


if __name__ == "__main__":
    unittest.main()
