#!/usr/bin/env python3
"""Mutation tests for the TP1 E4M3 full-graph 4K quarantine evidence."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[3]
VALIDATOR = Path(__file__).with_name(
    "validate-20260826-qwen38-official-f01e-autoround-tp1-mtp0-e4m3kv-full-and-piecewise-4k-sentinel-r1-result.py"
)
spec = importlib.util.spec_from_file_location("tp1_e4m3_full_graph_result_validator", VALIDATOR)
assert spec and spec.loader
MODULE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MODULE)


class ResultValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads(MODULE.RESULT.read_text())

    def validate_mutated_result(self, mutation) -> None:
        value = deepcopy(self.result)
        mutation(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(value))
            with self.assertRaises(RuntimeError):
                MODULE.validate(result_path=path)

    def validate_mutated_raw(self, relative_path: str, mutation) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            shutil.copytree(MODULE.ROOT, root)
            path = root / relative_path
            value = json.loads(path.read_text())
            mutation(value)
            path.write_text(json.dumps(value))
            with self.assertRaises(RuntimeError):
                MODULE.validate(root=root)

    def test_clean_raw_evidence_passes(self) -> None:
        report = MODULE.validate()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["structural_quarantine_cells"], 1)
        self.assertEqual(report["measured_speed_cells"], 0)
        self.assertEqual(report["divergence_token"], 95)

    def test_result_speed_authority_and_selector_widening_fail(self) -> None:
        self.validate_mutated_result(
            lambda value: value["diagnostic_point"].__setitem__("site_speed_publication", True)
        )
        self.validate_mutated_result(
            lambda value: value["authority"].__setitem__("site_measured_speed_cells", 1)
        )
        self.validate_mutated_result(
            lambda value: value["authority"].__setitem__("other_depths_tp_mtp_graph_or_kv_inferred", True)
        )

    def test_result_divergence_quality_and_cleanup_mutations_fail(self) -> None:
        self.validate_mutated_result(
            lambda value: value["target_failure"]["first_divergence"].__setitem__("one_based", 96)
        )
        self.validate_mutated_result(
            lambda value: value["quality"].__setitem__("exact_cases", 6)
        )
        self.validate_mutated_result(
            lambda value: value["cleanup"].__setitem__("campaign_container_absent_at_terminal", False)
        )

    def test_raw_target_cache_quality_and_graph_mutations_fail(self) -> None:
        self.validate_mutated_raw(
            "target-verification.json",
            lambda value: value.__setitem__("passed", True),
        )
        self.validate_mutated_raw(
            "quality.json",
            lambda value: value["exact_cases"][0]["usage"]["prompt_tokens_details"].__setitem__("cached_tokens", 1),
        )
        self.validate_mutated_raw(
            "container-inspect.json",
            lambda value: value[0]["Config"]["Cmd"].__setitem__(
                value[0]["Config"]["Cmd"].index("--kv-cache-dtype") + 1, "float16"
            ),
        )


if __name__ == "__main__":
    unittest.main()
