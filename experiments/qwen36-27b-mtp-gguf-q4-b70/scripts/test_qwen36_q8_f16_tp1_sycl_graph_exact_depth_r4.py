#!/usr/bin/env python3
"""Focused CPU-only tests for the R4 phase-aware cache-8 wrapper."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


RUNNER = Path(__file__).with_name("run-20260825-qwen36-q8-f16-tp1-sycl-graph-exact-depth-r4.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("qwen36_q8_f16_sycl_graph_depth_r4_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def summary(**changes: int) -> str:
    values = {
        "device": 0, "requested": 24, "compatibility_rejected": 0,
        "device_unsupported": 0, "cache_entries": 8, "cache_limit": 8,
        "cache_hit": 0, "cache_miss": 24, "cache_full": 16,
        "direct_replay": 0, "recorded": 8, "created": 8, "updated": 0,
        "recreated": 0, "replayed": 8,
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


class R4PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_runner()
        cls.manifest = cls.module.load_manifest()
        cls.module.validate_manifest(cls.manifest)

    def test_distinct_create_only_identity_cache8_and_verbose_argv(self) -> None:
        self.assertTrue(self.module.CAMPAIGN_ID.endswith("exact-depth-20260825-r4"))
        self.assertTrue(str(self.module.RUN_ROOT).endswith("exact-depth-20260825-r4"))
        self.assertEqual(self.module.ACK, f"RUN {self.module.CAMPAIGN_ID}")
        self.assertEqual(self.manifest["environment"]["GGML_SYCL_GRAPH_CACHE_SIZE"], "8")
        self.assertEqual(self.manifest["graph_evidence"]["per_context_requirements"]["cache_limit"], 8)
        self.assertEqual(self.manifest["argv_template"][-3:], ["-v", "-o", "json"])
        self.assertTrue(self.manifest["lifecycle"]["artifacts_are_create_only"])

    def test_all_non_delta_identity_and_authority_are_preserved(self) -> None:
        base = self.module.ORIGINAL_R3_LOAD_MANIFEST()
        for key in ("selectors", "source", "model", "runtime", "argv_template", "interpretation"):
            self.assertEqual(self.manifest[key], base[key])
        self.assertEqual(self.manifest["environment"], base["environment"])
        self.assertEqual(len(self.manifest["runtime"]["effective_shared_libraries"]), 32)

    def test_partial_prefill_then_decode_passes_and_retains_raw_phases(self) -> None:
        decode = summary(
            requested=641, cache_entries=3, cache_hit=638, cache_miss=3,
            cache_full=0,
            direct_replay=638, recorded=3, created=3, replayed=641,
        )
        prefill = summary()
        result = self.module.parse_graph_summary(prefill + "\n" + decode)
        self.assertEqual(result["summary_count"], 2)
        self.assertEqual(result["requested"], 665)
        self.assertEqual(result["cache_hit"], 638)
        self.assertEqual(result["direct_replay"], 638)
        self.assertEqual(result["created"], 11)
        self.assertEqual(result["replayed"], 649)
        self.assertEqual(result["cache_full"], 16)
        self.assertEqual(result["cache_entries"], 8)
        self.assertEqual(result["cache_limit"], 8)
        self.assertEqual(result["phases"]["prefill"]["cache_full"], 16)
        self.assertEqual(result["phases"]["decode"]["cache_hit"], 638)
        self.assertEqual(result["prefill_graph_classification"], "mixed-partial-cache-full")
        self.assertFalse(result["prefill_fully_graph_certified"])
        self.assertEqual(result["decode_graph_classification"], "verified-capture-and-replay")
        metadata = self.module.R1.metadata(
            self.manifest, [], {depth: result for depth in self.module.R1.DEPTHS}
        )
        retained = metadata["graph"]["capture"]["per_context"]["0"]
        self.assertEqual(retained["phases"]["prefill"]["cache_full"], 16)
        self.assertFalse(retained["prefill_fully_graph_certified"])

    def test_exactly_two_ordered_summaries_are_required(self) -> None:
        decode = summary(
            requested=30, cache_hit=6, cache_miss=24, cache_full=0,
            direct_replay=6, recorded=24, created=24, replayed=30,
        )
        with self.assertRaisesRegex(self.module.GateError, "exactly two"):
            self.module.parse_graph_summary(summary())
        with self.assertRaisesRegex(self.module.GateError, "exactly two"):
            self.module.parse_graph_summary(summary() + "\n" + decode + "\n" + decode)

    def test_prefill_and_decode_each_fail_closed(self) -> None:
        valid_decode = summary(
            requested=30, cache_hit=6, cache_miss=24, cache_full=0, direct_replay=6,
            recorded=24, created=24, replayed=30,
        )
        invalid_prefill = [
            summary(cache_limit=32), summary(device_unsupported=1),
            summary(updated=1), summary(requested=25), summary(recorded=7),
            summary(replayed=7), summary(cache_full=15),
        ]
        for invalid in invalid_prefill:
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(self.module.GateError, "prefill"):
                    self.module.parse_graph_summary(invalid + "\n" + valid_decode)
        invalid_decode = [
            summary(requested=30, cache_hit=6, cache_miss=24, cache_full=1,
                    direct_replay=6, recorded=24, created=24, replayed=30),
            summary(requested=30, cache_hit=0, cache_miss=30, cache_full=0,
                    direct_replay=0, recorded=30, created=30, replayed=30),
            summary(requested=30, cache_hit=6, cache_miss=24, cache_full=0,
                    direct_replay=5, recorded=24, created=24, replayed=30),
        ]
        for invalid in invalid_decode:
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(self.module.GateError, "decode"):
                    self.module.parse_graph_summary(summary() + "\n" + invalid)

    def test_manifest_rejects_extra_runtime_change(self) -> None:
        bad = copy.deepcopy(self.manifest)
        bad["environment"]["GGML_SYCL_ENABLE_GRAPH"] = "0"
        with self.assertRaises(self.module.GateError):
            self.module.validate_manifest(bad)

    def test_check_is_inert(self) -> None:
        output = self.module.RUN_ROOT
        self.assertFalse(output.exists())
        checked = subprocess.run(
            [sys.executable, "-B", str(RUNNER), "--check"],
            check=True, text=True, capture_output=True,
        )
        payload = json.loads(checked.stdout)
        self.assertEqual(payload["status"], "PASS")
        self.assertFalse(payload["launched"])
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
