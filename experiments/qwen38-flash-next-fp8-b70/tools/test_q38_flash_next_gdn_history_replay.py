#!/home/steve/.venvs/vllm-xpu/bin/python
"""CPU-only contract tests for the Flash-Next GDN history replay gate."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("check-q38-flash-next-gdn-history-replay.py")
SPEC = importlib.util.spec_from_file_location("q38_gdn_history_replay", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ContractTests(unittest.TestCase):
    def test_exact_tp4_local_shapes(self) -> None:
        self.assertEqual(MODULE.LOCAL_K_HEADS, 4)
        self.assertEqual(MODULE.LOCAL_V_HEADS, 12)
        self.assertEqual(MODULE.QKVZ_COLS, 4096)
        self.assertEqual(MODULE.BA_COLS, 24)
        self.assertEqual(MODULE.CONV_COLS, 2560)
        self.assertEqual(MODULE.CONV_HISTORY, 3)
        self.assertEqual(MODULE.TOTAL_TOKENS, 4096)

    def test_lifecycle_contract(self) -> None:
        shape = MODULE.shape_contract()
        self.assertEqual(shape["has_initial_state_by_chunk"][0], False)
        self.assertTrue(all(shape["has_initial_state_by_chunk"][1:]))
        self.assertEqual(len(shape["has_initial_state_by_chunk"]), 64)
        self.assertEqual(shape["conv_state_shape"], [2, 3, 2560])
        self.assertEqual(shape["ssm_state_shape"], [2, 12, 128, 128])
        self.assertFalse(shape["model_weights_loaded"])

    def test_operator_abi_is_frozen_at_23_arguments(self) -> None:
        self.assertEqual(len(MODULE.EXPECTED_OPERATOR_ARGUMENTS), 23)
        self.assertEqual(MODULE.EXPECTED_OPERATOR_ARGUMENTS[0], "core_attn_out")
        self.assertEqual(MODULE.EXPECTED_OPERATOR_ARGUMENTS[-1], "reorder_input")

    def test_mismatch_classifier_prioritizes_entering_state(self) -> None:
        self.assertEqual(
            MODULE.classify_mismatch(["core", "pre_ssm"]),
            "entering-cache-state-diverged",
        )
        self.assertEqual(
            MODULE.classify_mismatch(["core", "post_ssm"]),
            "native-op-diverged-from-identical-trajectory",
        )
        self.assertEqual(
            MODULE.classify_mismatch(["nonselected_ssm"]),
            "out-of-scope-cache-row-mutated",
        )

    def test_smoke_and_qualification_are_bounded(self) -> None:
        self.assertEqual(MODULE.TRAJECTORIES, {"smoke": 2, "qualification": 100})
        self.assertEqual(MODULE.REPLAY_REPEATS, 16)
        self.assertEqual(
            MODULE.TRAJECTORIES["qualification"] * MODULE.CHUNKS,
            6400,
        )


if __name__ == "__main__":
    unittest.main()
