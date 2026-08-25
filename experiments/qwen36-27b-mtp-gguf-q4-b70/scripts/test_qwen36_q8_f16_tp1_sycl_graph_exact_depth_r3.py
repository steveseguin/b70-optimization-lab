#!/usr/bin/env python3
"""Focused CPU-only tests for the R3 multi-summary graph-depth wrapper."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest


RUNNER = Path(__file__).with_name("run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r3.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_sycl_graph_depth_r3_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def summary(**changes: int) -> str:
    values = {
        "device": 0, "requested": 24, "compatibility_rejected": 0,
        "device_unsupported": 0, "cache_entries": 8, "cache_limit": 8,
        "cache_hit": 16, "cache_miss": 8, "cache_full": 0,
        "direct_replay": 16, "recorded": 8, "created": 8, "updated": 0,
        "recreated": 0, "replayed": 24,
    }
    values.update(changes)
    return (
        "[SYCL-GRAPH] summary device={device} requested={requested} "
        "compatibility_rejected={compatibility_rejected} device_unsupported={device_unsupported} "
        "cache_entries={cache_entries} cache_limit={cache_limit} cache_hit={cache_hit} "
        "cache_miss={cache_miss} cache_full={cache_full} direct_replay={direct_replay} "
        "recorded={recorded} created={created} updated={updated} recreated={recreated} "
        "replayed={replayed}"
    ).format(**values)


class R3PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_runner()
        cls.manifest = cls.module.load_manifest()
        cls.module.validate_manifest(cls.manifest)

    def test_distinct_create_only_identity_and_r2_argv(self) -> None:
        self.assertTrue(self.module.CAMPAIGN_ID.endswith("exact-depth-20260825-r3"))
        self.assertTrue(str(self.module.RUN_ROOT).endswith("exact-depth-20260825-r3"))
        self.assertEqual(self.module.ACK, f"RUN {self.module.CAMPAIGN_ID}")
        self.assertEqual(self.manifest["argv_template"][-3:], ["-v", "-o", "json"])
        self.assertTrue(self.manifest["lifecycle"]["artifacts_are_create_only"])

    def test_runtime_contexts_and_authority_are_preserved(self) -> None:
        base = self.module.ORIGINAL_R2_LOAD_MANIFEST()
        for key in ("selectors", "source", "model", "runtime", "environment", "argv_template", "interpretation"):
            self.assertEqual(self.manifest[key], base[key])
        self.assertEqual(self.manifest["selectors"]["active_context_tokens"], self.module.R1.DEPTHS)
        self.assertEqual(len(self.manifest["runtime"]["effective_shared_libraries"]), 32)

    def test_two_valid_summaries_aggregate_exactly(self) -> None:
        prompt = summary()
        decode = summary(
            requested=641, cache_entries=3, cache_hit=638, cache_miss=3,
            direct_replay=638, recorded=3, created=3, replayed=641,
        )
        result = self.module.parse_graph_summary(prompt + "\n" + decode)
        self.assertEqual(result["summary_count"], 2)
        self.assertEqual(result["requested"], 665)
        self.assertEqual(result["cache_hit"], 654)
        self.assertEqual(result["created"], 11)
        self.assertEqual(result["cache_entries"], 8)

    def test_zero_summaries_fail(self) -> None:
        with self.assertRaisesRegex(self.module.GateError, "one or more"):
            self.module.parse_graph_summary("")

    def test_any_invalid_summary_fails_the_whole_context(self) -> None:
        invalid_cases = [
            summary(compatibility_rejected=1),
            summary(updated=1),
            summary(requested=25),
            summary(direct_replay=15),
            summary(recorded=7),
            summary(replayed=23),
            summary(cache_hit=0, direct_replay=0, cache_miss=24, recorded=24, created=24),
        ]
        for invalid in invalid_cases:
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(self.module.GateError, "summary 2"):
                    self.module.parse_graph_summary(summary() + "\n" + invalid)

    def test_manifest_rejects_non_evidence_change(self) -> None:
        bad = copy.deepcopy(self.manifest)
        bad["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"] = "9"
        with self.assertRaises(self.module.GateError):
            self.module.validate_manifest(bad)


if __name__ == "__main__":
    unittest.main()
