#!/usr/bin/env python3
"""CPU-only tests for the A29 M1 MoE selection receipt."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


TOOL = Path(__file__).with_name("verify-moe-m1-selection.py")
SPEC = importlib.util.spec_from_file_location("q38_m1_selection", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def config_map() -> dict[str, dict[str, int]]:
    base = {
        "BLOCK_SIZE_M": 16,
        "BLOCK_SIZE_N": 64,
        "BLOCK_SIZE_K": 128,
        "GROUP_SIZE_M": 1,
        "SPLIT_K": 1,
        "num_warps": 4,
        "num_stages": 4,
    }
    result = {str(key): dict(base) for key in MODULE.EXPECTED_KEYS}
    result["1"]["num_warps"] = 8
    return result


class M1SelectionTest(unittest.TestCase):
    def test_exact_map_selects_m1_warps8(self) -> None:
        configs = MODULE.normalize_map(config_map())
        key = MODULE.select_key(configs, 1)
        self.assertEqual(key, 1)
        self.assertEqual(configs[key]["num_warps"], 8)

    def test_m4_candidate_is_rejected(self) -> None:
        raw = config_map()
        raw["4"]["num_warps"] = 8
        with self.assertRaisesRegex(MODULE.SelectionContractError, "M1-only"):
            MODULE.normalize_map(raw)

    def test_missing_key_is_rejected(self) -> None:
        raw = config_map()
        del raw["128"]
        with self.assertRaisesRegex(
            MODULE.SelectionContractError, "unexpected tuning keys"
        ):
            MODULE.normalize_map(raw)

    def test_receipt_writer_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps({"old": True}), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.SelectionContractError, "overwrite"):
                MODULE.write_exclusive(path, {"new": True})


if __name__ == "__main__":
    unittest.main()
