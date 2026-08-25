#!/usr/bin/env python3
"""CPU-only contract tests for the b2dd TP1 target concurrency packet."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name(
    "run-20260825-qwen38-b2dd-tp1-target-concurrency-r1.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("qwen38_tp1_concurrency", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Qwen38ConcurrencyPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def synthetic_result(self, output: Path) -> None:
        arms = []
        for batch in self.module.BATCH_SIZES:
            for repeat in range(2):
                arm = {
                    "batch_size": batch,
                    "repeat": repeat,
                    "generated_output_tokens": batch * 512,
                    "request_metrics_timestamps_valid": True,
                    "aggregate_decode_tok_s": float(batch * 10),
                    "sequential_oracle_comparison": {
                        "identical_requests": batch,
                        "requests": batch,
                    },
                }
                if repeat == 1:
                    arm["repeat0_comparison"] = {
                        "identical_requests": batch,
                        "requests": batch,
                    }
                arms.append(arm)
        value = {
            "schema": "neural-download-vllm-decode-sweep-v1",
            "completed": True,
            "config": {
                "model": str(self.module.MODEL),
                "batch_sizes": list(self.module.BATCH_SIZES),
                "input_tokens": 128,
                "output_tokens": 512,
                "repeats": 2,
                "max_model_len": 1024,
                "max_num_seqs": 64,
                "max_num_batched_tokens": 8192,
                "kv_cache_dtype": "auto",
                "tensor_parallel_size": 1,
                "speculative_tokens": 0,
                "graph": False,
                "sequential_oracle": True,
                "record_token_ids": True,
            },
            "sequential_oracle": [
                {"request_index": index} for index in range(64)
            ],
            "quality_smoke": [{"literal_match": True} for _ in range(68)],
            "arms": arms,
        }
        (output / "sweep.json").write_text(json.dumps(value), encoding="utf-8")

    def test_static_dependencies_and_manifest_pass(self) -> None:
        observed = self.module.verify_dependencies()
        self.assertEqual(observed[str(self.module.MANIFEST.relative_to(self.module.REPO))], self.module.DEPENDENCIES[self.module.MANIFEST])

    def test_plan_is_inert_and_attempt_paths_are_distinct(self) -> None:
        first = self.module.plan(1)
        second = self.module.plan(2)
        self.assertFalse(first["launch_performed"])
        self.assertNotEqual(first["output"], second["output"])
        self.assertNotEqual(first["cache"], second["cache"])
        self.assertNotEqual(first["container"], second["container"])

    def test_docker_vector_is_target_only_eager_and_oracle_enabled(self) -> None:
        args = self.module.docker_args(Path("/tmp/output"), Path("/tmp/cache"), "container")
        joined = "\n".join(args)
        self.assertIn("--tensor-parallel-size\n1", joined)
        self.assertIn("--sequential-oracle", args)
        self.assertIn("--record-token-ids", args)
        self.assertIn("--quality-smoke", args)
        self.assertNotIn("--graph", args)
        self.assertNotIn("--speculative-tokens", args)
        self.assertIn("VLLM_XPU_ENABLE_XPU_GRAPH=0", args)

    def test_exact_synthetic_result_classifies_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.synthetic_result(output)
            state, gates = self.module.validate_result(output, 0)
        self.assertEqual(state, "complete-exact")
        self.assertTrue(gates["sequential_oracle_exact"])
        self.assertTrue(gates["repeat_exact"])

    def test_token_difference_is_measured_variant_not_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.synthetic_result(output)
            value = json.loads((output / "sweep.json").read_text(encoding="utf-8"))
            value["arms"][-1]["repeat0_comparison"]["identical_requests"] = 63
            (output / "sweep.json").write_text(json.dumps(value), encoding="utf-8")
            state, gates = self.module.validate_result(output, 0)
        self.assertEqual(state, "measured-output-variant")
        self.assertFalse(gates["repeat_exact"])

    def test_missing_or_incomplete_result_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            state, _ = self.module.validate_result(output, 0)
            self.assertEqual(state, "quarantined")
            self.synthetic_result(output)
            value = json.loads((output / "sweep.json").read_text(encoding="utf-8"))
            value["arms"].pop()
            (output / "sweep.json").write_text(json.dumps(value), encoding="utf-8")
            state, _ = self.module.validate_result(output, 0)
            self.assertEqual(state, "quarantined")


if __name__ == "__main__":
    unittest.main()
