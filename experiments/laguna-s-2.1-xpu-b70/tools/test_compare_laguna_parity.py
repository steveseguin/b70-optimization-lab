#!/usr/bin/env python3
"""Regression tests for model-order Laguna parity reporting."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import torch


SCRIPT = Path(__file__).with_name("compare_laguna_parity.py")


class CompareLagunaParityTest(unittest.TestCase):
    def test_global_first_divergence_uses_model_order_before_rank(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            eager_dir = root / "eager"
            candidate_dir = root / "candidate"
            eager_dir.mkdir()
            candidate_dir.mkdir()

            for rank in range(4):
                buffers = {
                    "_parity_embedding": torch.zeros(2, dtype=torch.bfloat16),
                    "layers.0.self_attn.o_proj._parity_output": torch.zeros(
                        2, dtype=torch.bfloat16
                    ),
                    "layers.0._parity_mlp_out": torch.zeros(
                        2, dtype=torch.bfloat16
                    ),
                }
                eager = {
                    "input_id": torch.tensor(20253),
                    "position": torch.tensor(420),
                    "hidden_states": torch.zeros(2, dtype=torch.bfloat16),
                    "logits": None,
                    "buffers": {name: value.clone() for name, value in buffers.items()},
                }
                candidate = {
                    **eager,
                    "buffers": {name: value.clone() for name, value in buffers.items()},
                }
                if rank == 0:
                    candidate["buffers"]["layers.0._parity_mlp_out"][0] = 1
                if rank == 1:
                    candidate["buffers"][
                        "layers.0.self_attn.o_proj._parity_output"
                    ][0] = 1
                torch.save(eager, eager_dir / f"eager-rank{rank}.pt")
                torch.save(candidate, candidate_dir / f"candidate-rank{rank}.pt")

            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(eager_dir), str(candidate_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(
                result["first_divergence"]["name"],
                "layers.0.self_attn.o_proj._parity_output",
            )
            self.assertEqual(result["first_divergence"]["ranks"], [1])
            self.assertIsNone(result["ranks"][0]["input_ids_equal"])
            self.assertIsNone(result["ranks"][0]["positions_equal"])


if __name__ == "__main__":
    unittest.main()
