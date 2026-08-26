#!/usr/bin/env python3
"""Static and mutation tests for the TP4/MTP1 PIECEWISE 4K result validator."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
VALIDATOR = HERE / "validate-20260826-qwen38-official-f01e-autoround-tp4-mtp1-f16-piecewise-4k-sentinel-r1-result.py"
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-piecewise-4k-sentinel-r1-result.json"
RAW = Path("/mnt/fast-ai/bench-results/qwen38-official-f01e-autoround-tp4-mtp1-f16-piecewise-4k-sentinel-20260826-r1")


class ResultValidatorTests(unittest.TestCase):
    def run_validator(self, result=RESULT, raw=RAW):
        return subprocess.run([str(VALIDATOR), "--result", str(result), "--raw-root", str(raw)], text=True, capture_output=True)

    def mutate_result(self, mutate):
        data = json.loads(RESULT.read_text())
        mutate(data)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, tmp)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink, missing_ok=True)
        return Path(tmp.name)

    def mutate_raw(self, rel, mutate):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(RAW, tmp / "raw")
        path = tmp / "raw" / rel
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data))
        return tmp / "raw"

    def test_original_passes(self):
        run = self.run_validator()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_decode_mutation_fails(self):
        result = self.mutate_result(lambda d: d["point"].__setitem__("decode_tok_s", 99.0))
        self.assertNotEqual(self.run_validator(result).returncode, 0)

    def test_acceptance_mutation_fails(self):
        raw = self.mutate_raw("verification-gates.json", lambda d: d["acceptance"].__setitem__("accepted_tokens", 57))
        self.assertNotEqual(self.run_validator(raw=raw).returncode, 0)

    def test_tp_mutation_fails(self):
        result = self.mutate_result(lambda d: d["config"].__setitem__("tp", 2))
        self.assertNotEqual(self.run_validator(result).returncode, 0)

    def test_publication_authority_mutation_fails(self):
        result = self.mutate_result(lambda d: d["authority"].__setitem__("site_or_family_publication_authorized", True))
        self.assertNotEqual(self.run_validator(result).returncode, 0)

    def test_depth_scope_mutation_fails(self):
        result = self.mutate_result(lambda d: d["authority"].__setitem__("selected_evidence_depths", [4096, 8192]))
        self.assertNotEqual(self.run_validator(result).returncode, 0)

    def test_parent_hash_mutation_fails(self):
        result = self.mutate_result(lambda d: d["parent_oracles"]["mtp0_eager"].__setitem__("output_token_ids_sha256", "0" * 64))
        self.assertNotEqual(self.run_validator(result).returncode, 0)

    def test_static_zero_publication_and_caveat(self):
        data = json.loads(RESULT.read_text())
        self.assertEqual(data["authority"]["site_cells"], 0)
        self.assertFalse(data["authority"]["site_or_family_publication_authorized"])
        self.assertEqual(data["historical_graph_corruption_caveat"]["first_divergence"]["one_based"], 99)
        self.assertEqual(data["graph_topology_and_cache"]["observed_rank_cache_namespaces"], [f"rank_{i}_0" for i in range(4)])


if __name__ == "__main__":
    unittest.main()
