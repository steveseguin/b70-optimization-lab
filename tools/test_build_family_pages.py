#!/usr/bin/env python3
"""Focused tests for the model-family coverage validator and renderer."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
from statistics import median
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("build-family-pages.py")
SPEC = importlib.util.spec_from_file_location("build_family_pages", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FamilyCoverageTest(unittest.TestCase):
    def test_home_benchmark_tables_separate_weights_from_generation_mode(self) -> None:
        index_html = (MODULE.ROOT / "index.html").read_text()
        self.assertNotIn("Compression &amp; speed-up", index_html)
        self.assertGreaterEqual(index_html.count(">Weights</abbr>"), 2)
        self.assertGreaterEqual(index_html.count(">Generation</abbr>"), 2)
        for mode in (
            '<td class="mut">no MTP</td>',
            "MTP &middot; depth 3",
            "DFlash &middot; depth 11",
            "DSpark &middot; depth 7",
        ):
            self.assertIn(mode, index_html)
        # The picker says it in plain words: every route states whether MTP is on.
        self.assertGreaterEqual(index_html.count("no MTP"), 9)
        self.assertIn("MTP / DFlash / DSpark = a small helper drafts words ahead", index_html)
        self.assertNotIn("status-ico", index_html)

    def test_home_picker_surfaces_existing_exact_32k_and_raw_aggregate_evidence(self) -> None:
        index_html = (MODULE.ROOT / "index.html").read_text()
        expected_context = {
            "packages/gemma4-26b-a4b-q8-b70/package.json": ("decode-vs-context", 114.8486529751413),
            "packages/lfm25-26b-q8-b70/package.json": ("decode-vs-context-depth", 89.93812),
            "packages/nemotron-35-lightning-30b-a3b-b70/package.json": ("decode-vs-context-depth", 64.622975),
            "packages/ornith-15-35b-a3b-q4km-b70/package.json": ("decode-vs-context-depth", 99.614237),
            "packages/ornith-15-9b-q8-b70/package.json": ("decode-vs-context-depth", 39.83848),
            "packages/qwen38-27b-q4km-tp1-b70/package.json": ("http-decode-vs-active-context", 24.488129029771436),
            "packages/qwen38-27b-q4km-mtp2-tp1-b70/package.json": ("http-decode-vs-active-context", 36.50506489790905),
            "packages/qwen38-27b-q4km-tp2-asrock-b70/package.json": ("http-decode-vs-active-context", 44.43728051677345),
            "packages/qwen38-27b-q8-tp2-b70/package.json": ("http-decode-vs-active-context", 33.848820185540816),
            "packages/qwen38-27b-fp8-tp2-b70/package.json": ("http-decode-vs-active-context", 31.48958732345858),
        }
        for manifest, (profile_id, expected) in expected_context.items():
            package = json.loads((MODULE.ROOT / manifest).read_text())
            profile = next(
                item
                for item in package["performance_profiles"]
                if item["id"] == profile_id
            )
            point = max(profile["points"], key=lambda item: item["context_tokens"])
            with self.subTest(package=package["id"]):
                self.assertGreaterEqual(point["context_tokens"], 32_000)
                self.assertAlmostEqual(point["value"], expected)
                self.assertRegex(
                    index_html,
                    rf">{expected:.2f}&dagger;(?:</a>)?</td>",
                )

        # Cells carry the number only; raw-engine vs HTTP lives in the tooltip.
        self.assertIn(">216.5&dagger;</a>", index_html)
        self.assertIn(">83.8&dagger;</a>", index_html)
        self.assertIn(">68.6&dagger;</a>", index_html)
        self.assertIn(">165.4&dagger;</a>", index_html)
        self.assertIn(">163.6&dagger;</a>", index_html)
        self.assertIn(">1,112.6&dagger;</a>", index_html)
        self.assertIn(">68.3&dagger;</a>", index_html)
        self.assertNotIn("raw&dagger;", index_html)
        self.assertNotIn("HTTP&dagger;", index_html)
        fp8_row = re.search(
            r"official FP8.*?</tr>", index_html, flags=re.DOTALL
        )
        self.assertIsNotNone(fp8_row)
        self.assertIn(">31.49&dagger;</a>", fp8_row.group(0))
        self.assertIn(">1,112.6&dagger;</a>", fp8_row.group(0))
        self.assertIn("128 active users", fp8_row.group(0))
        self.assertIn("256-token service profile", fp8_row.group(0))
        laguna_row = re.search(
            r"Laguna-S-2\.1.*?</tr>", index_html, flags=re.DOTALL
        )
        self.assertIsNotNone(laguna_row)
        self.assertNotIn(">31.49&dagger;</a>", laguna_row.group(0))
        self.assertIn("Multi-user greedy output is batch-shape-dependent", index_html)

    def test_fp8_tp2_concurrency_profiles_match_qualified_source(self) -> None:
        package = json.loads(
            (
                MODULE.ROOT
                / "packages/qwen38-27b-fp8-tp2-b70/package.json"
            ).read_text()
        )
        result = json.loads(
            (
                MODULE.ROOT
                / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p64-p2p1-confirmation-r10-result.json"
            ).read_text()
        )
        profiles = {item["id"]: item for item in package["performance_profiles"]}
        aggregate = profiles["http-output-audited-aggregate-vs-concurrent-users"]
        p50 = profiles["http-ttft-p50-vs-concurrent-users"]
        p95 = profiles["http-ttft-p95-vs-concurrent-users"]
        self.assertEqual(len(result["points"]), 7)
        for index, source in enumerate(result["points"]):
            self.assertEqual(
                aggregate["points"][index]["concurrent_sequences"],
                source["concurrent_users"],
            )
            self.assertEqual(
                aggregate["points"][index]["value"],
                source["median_aggregate_tok_s"],
            )
            self.assertEqual(
                aggregate["points"][index]["per_user_value"],
                source["median_per_user_tok_s"],
            )
            self.assertEqual(
                p50["points"][index]["value"],
                source["latency_ms"]["ttft_ms_p50"]["median"],
            )
            self.assertEqual(
                p95["points"][index]["value"],
                source["latency_ms"]["ttft_ms_p95"]["median"],
            )
        self.assertTrue(all(not point["queued_profile"] for point in result["points"]))

    def test_scoped_ornith_packet_and_family_stay_in_parity(self) -> None:
        family = json.loads((MODULE.ROOT / "families/ornith-1-5.json").read_text())
        package = json.loads(
            (
                MODULE.ROOT
                / "packages/ornith-15-35b-a3b-q4km-b70/package.json"
            ).read_text()
        )
        summary = json.loads(
            (
                MODULE.ROOT
                / "experiments/ornith-15-b70/data/2026-08-23-ornith35b-shared-gate-residual-rms-summary.json"
            ).read_text()
        )
        runs = {item["id"]: item for item in family["run_measurements"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        packets = {item["id"]: item for item in family["packets"]}

        current = runs["ornith-35b-twelve-feature-copyoff-one-card"]["metrics"][
            "decode_tok_s"
        ]
        self.assertEqual(
            current,
            summary["fresh_server"][
                "candidate_run_medians_conventional_tok_s"
            ],
        )
        self.assertIsNone(package["library"]["featured_metric"])
        self.assertAlmostEqual(sum(current) / len(current), 131.460231, places=6)
        index_html = (MODULE.ROOT / "index.html").read_text()
        self.assertNotIn(">131.46</td>", index_html)
        self.assertIn("natural-response hashes were not stable", index_html)
        self.assertNotIn(">132.79</td>", index_html)

        ratebars = [
            (float(rate), float(width))
            for rate, width in re.findall(
                r'(\d+\.\d+)<div class="ratebar(?: max)?" '
                r'style="width:(\d+(?:\.\d+)?)%"',
                index_html,
            )
        ]
        self.assertTrue(ratebars)
        self.assertIn((125.46, 100.0), ratebars)
        max_rate = max(rate for rate, _ in ratebars)
        for rate, width in ratebars:
            with self.subTest(rate=rate):
                self.assertEqual(width, round(100 * rate / max_rate, 1))
        self.assertEqual(
            packets["ornith-15-35b-a3b-q4km-b70"]["grades"]["evidence"][
                "grade"
            ],
            "B",
        )

        # Keep measurement IDs bound to their exact eleven/twelve-feature
        # evidence even while the strict package headline remains pending.
        self.assertEqual(
            runs["ornith-35b-optimized-one-card"]["metrics"]["decode_tok_s"],
            [130.159639, 128.977294],
        )
        self.assertEqual(
            runs["ornith-35b-optimized-one-card"]["conventional_metrics"][
                "decode_tok_s"
            ],
            [128.8580426010522, 127.68752111614396],
        )
        self.assertEqual(
            runs["ornith-35b-twelve-feature-copyoff-one-card"][
                "compatibility_metrics"
            ]["decode_tok_s"],
            [131.76906143822612, 133.80716195534055],
        )

        current_points = series[
            "ornith-35b-twelve-feature-copyoff-context-depth"
        ]["points"]
        profiles = {
            item["metric"]: item for item in package["performance_profiles"]
        }
        self.assertEqual(
            [
                {"context_tokens": point["x"], "value": point["decode_tok_s"], "samples": 5}
                for point in current_points
            ],
            profiles["decode"]["points"],
        )
        self.assertEqual(
            [
                {"context_tokens": point["x"], "value": point["prefill_tok_s"], "samples": 5}
                for point in current_points
            ],
            profiles["prefill"]["points"],
        )

        raw_prefix = MODULE.ROOT / "experiments/ornith-15-b70/data"
        candidate_raw = [
            json.loads((raw_prefix / name).read_text())
            for name in (
                "ornith-gate-resid-server-candidate-a.json",
                "ornith-gate-resid-server-candidate-b.json",
            )
        ]
        self.assertEqual(
            current,
            [
                median(
                    row["tok_s_1_100_intervals_after_ttft"]
                    for row in record["rows"]
                )
                for record in candidate_raw
            ],
        )
        self.assertEqual(
            runs["ornith-35b-twelve-feature-copyoff-one-card"][
                "compatibility_metrics"
            ]["decode_tok_s"],
            [
                median(row["tok_s_1_100_after_ttft"] for row in record["rows"])
                for record in candidate_raw
            ],
        )

        copy_raw = [
            json.loads((raw_prefix / name).read_text())
            for name in (
                "2026-08-23-ornith35b-copy-offload-B1-disabled.server.json",
                "2026-08-23-ornith35b-copy-offload-B2-disabled.server.json",
            )
        ]
        self.assertEqual(
            runs["ornith-35b-optimized-one-card"]["conventional_metrics"][
                "decode_tok_s"
            ],
            [
                median(
                    row["tok_s_1_100_intervals_after_ttft"]
                    for row in record["rows"]
                )
                for record in copy_raw
            ],
        )

        def raw_sweep_points(filename: str) -> list[dict[str, float | int]]:
            records = json.loads(
                (
                    MODULE.ROOT
                    / "repro/ornith-15-35b-a3b-q4km-b70"
                    / filename
                ).read_text()
            )
            depths = sorted({record["n_depth"] for record in records})
            return [
                {
                    "x": depth,
                    "decode_tok_s": next(
                        record["avg_ts"]
                        for record in records
                        if record["n_depth"] == depth and record["n_gen"] == 128
                    ),
                    "prefill_tok_s": next(
                        record["avg_ts"]
                        for record in records
                        if record["n_depth"] == depth
                        and record["n_prompt"] == 2048
                    ),
                }
                for depth in depths
            ]

        self.assertEqual(
            series["ornith-35b-context-depth"]["points"],
            raw_sweep_points("ornith-15-35b-a3b-q4km-eleven-feature.sweep.json"),
        )
        self.assertEqual(
            current_points,
            raw_sweep_points("ornith-15-35b-a3b-q4km-twelve-feature.sweep.json"),
        )

    def test_qwen_rolling_and_overlay_frontiers_are_append_only(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        runs = {item["id"]: item for item in family["run_measurements"]}
        protected = {
            "q38-a3561ef8-stock-tp1-graph-strict": [
                30.241645123711923,
                30.243714296955797,
            ],
            "q38-a3561ef8-stock-tp2-graph-strict": [48.49048978038331],
            "q38-a3561ef8-stock-tp4-graph-strict": [
                71.9001988117144,
                71.2457420049019,
            ],
            "q38-a3561ef8-tp2-winner-overlay-graph-strict": [
                49.00935245117815
            ],
            "q38-a3561ef8-tp4-winner-overlay-graph-diagnostic": [
                71.72254506718171
            ],
            "q38-a3561ef8-tp4-winner-overlay-graph-strict": [
                71.35287190161719,
                71.45427094575045,
            ],
            "q38-nightly-tp4-mtp2-screen": [31.16799415898192],
        }
        for measurement_id, expected in protected.items():
            with self.subTest(measurement_id=measurement_id):
                self.assertEqual(
                    runs[measurement_id]["metrics"]["decode_tok_s"], expected
                )

    def test_nine_family_backlog_is_published_without_invented_curves(self) -> None:
        # qwen-35b left the no-curve backlog on 2026-08-24: it gained a real
        # measured series (the published 1..64-user AutoRound aggregate sweep,
        # data/qwen36-35b-autoround-b70-concurrency-20260824.json), so the
        # no-invented-curves pin no longer applies to it.
        expected = {
            "deepseek-v4",
            "deepseek-coder-v2",
            "glm-4-7",
            "mistral-small-3-2",
            "nemotron-cascade-2",
            "phi-4",
            "qwen-14b",
            "qwen-30b-a3b",
        }
        catalog = json.loads(MODULE.CATALOG.read_text())
        family_ids = {entry["id"] for entry in catalog["families"]}
        self.assertEqual(len(family_ids), len(catalog["families"]))
        self.assertLessEqual(expected | {"qwen-35b"}, family_ids)
        model_index = (MODULE.ROOT / "models/index.html").read_text()
        for family_id in family_ids:
            self.assertIn(f'href="{family_id}.html"', model_index)

        registry = json.loads(MODULE.COVERAGE_REGISTRY.read_text())
        self.assertEqual(registry["planned_families"], [])
        coder_lane = next(
            lane
            for lane in registry["lanes"]
            if lane["id"] == "rapid-qwen3-coder-30b-a3b-udq4"
        )
        self.assertEqual(coder_lane["family_id"], "qwen-30b-a3b")

        for family_id in expected:
            with self.subTest(family_id=family_id):
                family = json.loads(
                    (MODULE.ROOT / f"families/{family_id}.json").read_text()
                )
                self.assertEqual(family.get("estimates"), [])
                self.assertFalse(family.get("series_measurements"))
                self.assertEqual(
                    (family.get("model_signals", {}).get("popularity") or {}).get(
                        "state"
                    ),
                    "not-scored",
                )

    def test_new_family_measurements_and_qwen_sibling_boundary_are_exact(self) -> None:
        expected = {
            "deepseek-coder-v2": {
                "deepseek-coder-v2-lite-q4km-tp1-rapid": (
                    [57.09651439511314],
                    [139.8265556199476],
                )
            },
            "glm-4-7": {
                "glm-4.7-flash-udq4-tp1-rapid": (
                    [40.7691297367011],
                    [206.20633498765528],
                )
            },
            "mistral-small-3-2": {
                "mistral-small-3.2-udq4-tp1-rapid": (
                    [27.29674347655439],
                    [1501.7739470349625],
                ),
                "mistral-small-3.2-udq8-tp1-rapid": (
                    [16.380395177161446],
                    [2686.1701778834686],
                ),
            },
            "nemotron-cascade-2": {
                "nemotron-cascade-2-q4km-tp1-rapid": (
                    [50.90422891211857],
                    [449.1593260318041],
                )
            },
            "phi-4": {
                "phi4-mini-q4km-tp1-rapid": (
                    [96.54834088986573],
                    [69.93722857441753],
                ),
                "phi4-mini-q8-tp1-rapid": (
                    [72.24629337909391],
                    [119.45722799282521],
                ),
            },
            "qwen-14b": {
                "qwen3-14b-instruct-q4km-tp1-rapid": (
                    [38.249019008891544],
                    [240.0411400012672],
                )
            },
            "qwen-30b-a3b": {
                "qwen3-30b-a3b-instruct-2507-udq4-tp1-rapid": (
                    [107.48388363267362],
                    [166.9534610118717],
                ),
                "qwen3-coder-30b-a3b-udq4-tp1-rapid": (
                    [108.1165394591524],
                    [164.12943904288113],
                ),
            },
        }
        for family_id, measurements in expected.items():
            family = json.loads(
                (MODULE.ROOT / f"families/{family_id}.json").read_text()
            )
            by_id = {item["id"]: item for item in family["run_measurements"]}
            for measurement_id, (decode, ttft) in measurements.items():
                with self.subTest(measurement_id=measurement_id):
                    self.assertEqual(
                        by_id[measurement_id]["metrics"]["decode_tok_s"], decode
                    )
                    self.assertEqual(by_id[measurement_id]["metrics"]["ttft_ms"], ttft)

        deepseek = json.loads((MODULE.ROOT / "families/deepseek-v4.json").read_text())
        deepseek_run = deepseek["run_measurements"][0]
        self.assertEqual(
            deepseek_run["metrics"]["decode_tok_s"],
            [80.82005189243556, 76.90017809136465, 78.28722593298039],
        )
        self.assertEqual(deepseek["packets"][0]["featured_metric"]["value"], 78.28722593298039)

        qwen35 = json.loads((MODULE.ROOT / "families/qwen-35b.json").read_text())
        qwen35_runs = {item["id"]: item for item in qwen35["run_measurements"]}
        self.assertEqual(
            qwen35_runs["qwen35-quark-tp4-strict-current"]["metrics"]["decode_tok_s"],
            [93.55054235558917],
        )
        self.assertEqual(
            qwen35_runs["qwen35-quark-tp4-legacy-approved"]["metrics"]["decode_tok_s"],
            [99.42835812273452],
        )
        self.assertEqual(qwen35_runs["qwen35-quark-tp2-screen"]["state"], "lab-screened")
        self.assertEqual(
            qwen35_runs["qwen35-autoround-tp1-users-r16"]["metrics"][
                "aggregate_tok_s"
            ],
            [1052.8704424119495],
        )
        self.assertEqual(
            qwen35_runs["qwen35-quark-tp4-mtp1-quarantined"]["state"],
            "quarantined",
        )
        self.assertEqual(
            [entry["value"] for entry in MODULE.featured_result_entries(qwen35)],
            [
                93.55054235558917,
                90.90948338800597,
                1052.8704424119495,
                85.86911405999231,
            ],
        )

        qwen30 = json.loads((MODULE.ROOT / "families/qwen-30b-a3b.json").read_text())
        variants = {item["id"]: item for item in qwen30["model_variants"]}
        self.assertEqual(set(variants), {
            "qwen3-30b-a3b-instruct-2507",
            "qwen3-coder-30b-a3b-instruct",
        })
        self.assertEqual(variants["qwen3-30b-a3b-instruct-2507"]["intermediate_size"], 6144)
        self.assertEqual(variants["qwen3-coder-30b-a3b-instruct"]["intermediate_size"], 5472)
        self.assertIn("partial transfer", qwen30["transfer_scope"]["status"])
        identity = json.loads(
            (
                MODULE.ROOT
                / "data/rapid-model-snapshots-b70/qwen3-30b-a3b-family-identity-20260824.json"
            ).read_text()
        )
        self.assertEqual(identity["shared_core_geometry"]["num_hidden_layers"], 48)
        self.assertEqual(identity["shared_core_geometry"]["num_experts"], 128)

        phi = json.loads((MODULE.ROOT / "families/phi-4.json").read_text())
        self.assertEqual([item["id"] for item in phi["weight_revisions"]], ["phi4-mini-instruct-7ff82c2"])

    def test_qwen35_quantizations_share_one_fail_closed_base_revision(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-35b.json").read_text())
        self.assertEqual(self._errors(family), [])
        self.assertEqual(
            [revision["id"] for revision in family["weight_revisions"]],
            ["qwen3.6-35b-a3b-base"],
        )
        self.assertEqual(family["model_variants"], [])
        revision = family["weight_revisions"][0]
        self.assertNotIn("repository", revision)
        self.assertNotIn("revision", revision)
        artifacts = {
            artifact["id"]: artifact
            for artifact in revision["quantized_artifacts"]
        }
        self.assertEqual(
            set(artifacts),
            {
                "qwen36-35b-quark-w8a8-cced565",
                "qwen36-35b-autoround-w4a16",
            },
        )
        self.assertNotIn("revision", artifacts["qwen36-35b-autoround-w4a16"])
        self.assertIn(
            "not captured",
            artifacts["qwen36-35b-autoround-w4a16"]["revision_status"],
        )
        expected_artifact = {
            "Quark W8A8 INT8": "qwen36-35b-quark-w8a8-cced565",
            "AutoRound W4A16 INT4": "qwen36-35b-autoround-w4a16",
        }
        for measurement in MODULE.records(family):
            self.assertEqual(measurement["revision"], "qwen3.6-35b-a3b-base")
            self.assertEqual(
                measurement["artifact_id"], expected_artifact[measurement["variant"]]
            )

        coverage = {view["id"]: view for view in family["coverage_views"]}
        quark_mtp = coverage["qwen35-current-mtp-by-tp"]
        self.assertEqual(quark_mtp["rows"], [0, 1, 2, 3, 4])
        self.assertEqual(quark_mtp["columns"], [1, 2, 4])
        self.assertEqual(len(quark_mtp["cells"]), 15)
        self.assertTrue(
            all(
                quark_mtp["cells"][f"{depth}:{tp}"]["state"] == "missing"
                for depth in (2, 3, 4)
                for tp in (1, 2, 4)
            )
        )
        quark_context = coverage["qwen35-quark-context-by-tp"]
        self.assertEqual(
            quark_context["rows"],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertEqual(quark_context["columns"], [1, 2, 4])
        self.assertEqual(len(quark_context["cells"]), 21)
        self.assertTrue(
            all(
                cell["state"] == "missing"
                for cell in quark_context["cells"].values()
            )
        )
        mtp = coverage["qwen35-autoround-mtp-by-tp"]
        self.assertEqual(mtp["rows"], [0, 1, 2, 3, 4])
        self.assertEqual(mtp["columns"], [1, 2, 4])
        self.assertEqual(len(mtp["cells"]), 15)
        self.assertEqual(mtp["cells"]["0:1"]["state"], "lab-screened")
        self.assertTrue(
            all(
                cell["state"] == "missing"
                for key, cell in mtp["cells"].items()
                if key != "0:1"
            )
        )
        context = coverage["qwen35-autoround-context-by-tp"]
        self.assertEqual(
            context["rows"], [0, 2048, 4096, 8192, 16384, 24576, 32768]
        )
        self.assertEqual(context["columns"], [1, 2, 4])
        self.assertEqual(len(context["cells"]), 21)
        self.assertTrue(
            all(cell["state"] == "missing" for cell in context["cells"].values())
        )

        packets = {packet["id"]: packet for packet in family["packets"]}
        research = packets["qwen36-35b-autoround-w4a16-research"]
        self.assertEqual(research["grades"]["evidence"]["grade"], "C")
        self.assertEqual(
            research["featured_metric"]["measurement_id"],
            "qwen35-autoround-tp1-single-r16",
        )
        self.assertEqual(
            family["family_closures"][0]["selectors"]["artifact_id"],
            "qwen36-35b-quark-w8a8-cced565",
        )
        rendered = MODULE.family_page(family)
        self.assertEqual(rendered.count('class="artifact-disclosure"'), 1)
        self.assertIn("2 exact artifacts · 2 quantizations", rendered)
        self.assertEqual(rendered.count("· quantized artifact</span>"), 0)

        origins = deepcopy(family)
        origins["weight_revisions"][0]["quantized_artifacts"][0][
            "quantization_origin"
        ] = "export"
        origins["weight_revisions"][0]["quantized_artifacts"][1][
            "quantization_origin"
        ] = "runtime"
        self.assertEqual(self._errors(origins), [])

        invalid_origin = deepcopy(origins)
        invalid_origin["weight_revisions"][0]["quantized_artifacts"][0][
            "quantization_origin"
        ] = "inherited"
        self._assert_error(
            self._errors(invalid_origin), "quantization_origin", "export or runtime"
        )

        missing_canonical_quantization = deepcopy(family)
        del missing_canonical_quantization["run_measurements"][0]["quantization"]
        self._assert_error(
            self._errors(missing_canonical_quantization),
            "canonical quantization",
            "artifact-bound revision",
        )

        mismatched = deepcopy(family)
        mismatched["run_measurements"][0]["artifact_id"] = (
            "qwen36-35b-autoround-w4a16"
        )
        self._assert_error(self._errors(mismatched), "artifact", "quantization")

        for collection, index in (
            ("run_measurements", 0),
            ("series_measurements", 0),
            ("packets", 0),
        ):
            with self.subTest(missing_artifact_binding=collection):
                missing = deepcopy(family)
                del missing[collection][index]["artifact_id"]
                self._assert_error(
                    self._errors(missing), "must name a quantized artifact"
                )

        missing_view_binding = deepcopy(family)
        del missing_view_binding["coverage_views"][0]["fixed_selectors"][
            "artifact_id"
        ]
        self._assert_error(
            self._errors(missing_view_binding), "must bind quantized artifact"
        )

        unknown_view_artifact = deepcopy(family)
        unknown_view_artifact["coverage_views"][1]["fixed_selectors"][
            "artifact_id"
        ] = "unknown-artifact"
        self._assert_error(
            self._errors(unknown_view_artifact),
            "coverage",
            "unknown quantized artifact",
        )

        missing_closure_binding = deepcopy(family)
        del missing_closure_binding["family_closures"][0]["selectors"][
            "artifact_id"
        ]
        self._assert_error(
            self._errors(missing_closure_binding), "must bind quantized artifact"
        )

        unknown_closure_artifact = deepcopy(family)
        unknown_closure_artifact["family_closures"][0]["selectors"][
            "artifact_id"
        ] = "unknown-artifact"
        self._assert_error(
            self._errors(unknown_closure_artifact),
            "family closure",
            "unknown quantized artifact",
        )

    def test_artifact_bound_cell_selectors_and_estimates_fail_closed(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-35b.json").read_text())
        view = family["coverage_views"][0]
        artifact_id = view["fixed_selectors"].pop("artifact_id")
        for cell in view["cells"].values():
            cell["selectors"] = {"artifact_id": artifact_id}

        self.assertEqual(self._errors(family), [])
        self.assertEqual(
            MODULE.effective_cell_selectors(view, 0, 1, view["cells"]["0:1"])[
                "artifact_id"
            ],
            artifact_id,
        )

        repeated = deepcopy(family)
        repeated["coverage_views"][0]["cells"]["0:1"]["selectors"][
            "revision"
        ] = "qwen3.6-35b-a3b-base"
        self._assert_error(
            self._errors(repeated), "cell 0:1.selectors", "repeat inherited keys"
        )

        unknown = deepcopy(family)
        unknown["coverage_views"][0]["cells"]["0:1"]["selectors"][
            "artifact_id"
        ] = "unknown-artifact"
        self._assert_error(
            self._errors(unknown), "cell 0:1", "unknown quantized artifact"
        )

        estimate_family = json.loads(
            (MODULE.ROOT / "families/qwen-35b.json").read_text()
        )
        measurement = estimate_family["run_measurements"][0]
        estimate = self._estimate()
        estimate["basis_measurement_ids"] = [measurement["id"]]
        estimate["selectors"] = {
            "revision": measurement["revision"],
            "artifact_id": measurement["artifact_id"],
            "quantization": measurement["quantization"],
        }
        estimate_family["estimates"] = [estimate]
        self.assertEqual(self._errors(estimate_family), [])

        missing_estimate_artifact = deepcopy(estimate_family)
        del missing_estimate_artifact["estimates"][0]["selectors"]["artifact_id"]
        self._assert_error(
            self._errors(missing_estimate_artifact),
            "estimate estimate-a",
            "must bind quantized artifact",
        )

        mismatched_estimate_quantization = deepcopy(estimate_family)
        mismatched_estimate_quantization["estimates"][0]["selectors"][
            "quantization"
        ] = "wrong-quantization"
        self._assert_error(
            self._errors(mismatched_estimate_quantization),
            "estimate estimate-a",
            "does not match artifact",
        )

    def test_dense_coverage_contract_expands_and_renders_a_scorecard(self) -> None:
        family = self._family()
        family["weight_revisions"][0]["quantized_artifacts"] = [
            {
                "id": "revision-a-quant-a",
                "label": "Quant A",
                "quantization": "quant-a",
                "repository": "example/quant-a",
                "revision": "a" * 40,
                "evidence": "https://example.test/quant-a.json",
            }
        ]
        measurement = family["run_measurements"][0]
        measurement.update(
            {
                "artifact_id": "revision-a-quant-a",
                "quantization": "quant-a",
            }
        )
        measurement["config"].update(
            {"active_context_tokens": 0, "kv": "f16"}
        )
        axes = [
            {"key": "revision", "label": "Revision", "values": ["revision-a"]},
            {
                "key": "artifact_id",
                "label": "Artifact",
                "values": ["revision-a-quant-a"],
            },
            {"key": "quantization", "label": "Quantization", "values": ["quant-a"]},
            {"key": "tp", "label": "TP", "prefix": "TP", "values": [1, 2, 4]},
            {"key": "mtp", "label": "MTP", "prefix": "MTP", "values": [0, 1]},
            {
                "key": "active_context_tokens",
                "label": "Active context",
                "values": [0, 32768],
                "value_labels": {"32768": "32K"},
            },
            {"key": "graph", "label": "Graph", "values": ["off", "on"]},
            {"key": "kv", "label": "KV", "values": ["f16"]},
        ]
        wildcard = {axis["key"]: "*" for axis in axes}
        measured_match = {
            "revision": "revision-a",
            "artifact_id": "revision-a-quant-a",
            "quantization": "quant-a",
            "tp": 1,
            "mtp": 0,
            "active_context_tokens": 0,
            "graph": "off",
            "kv": "f16",
        }
        contract = {
            "id": "dense-main-lane",
            "label": "Dense main lane",
            "description": "Every deployment permutation.",
            "axes": axes,
            "rules": [
                {
                    "id": "all-gaps",
                    "match": wildcard,
                    "state": "missing",
                    "label": "not measured",
                    "parent": "main-coverage-backlog",
                    "retry": {"status": "queued", "reason": "unmeasured"},
                },
                {
                    "id": "measured-control",
                    "match": measured_match,
                    "state": "lab-measured",
                    "label": "30.0–30.2 tok/s",
                    "evidence_id": "measured-a",
                    "retry": {"status": "complete"},
                },
            ],
        }
        family["coverage_contracts"] = [contract]

        cells, expansion_errors = MODULE.expand_coverage_contract(contract)
        self.assertEqual(expansion_errors, [])
        self.assertEqual(len(cells), 24)
        measured_cell = next(
            cell for cell in cells if cell["state"] == "lab-measured"
        )
        self.assertEqual(measured_cell["rule_ids"], ["all-gaps", "measured-control"])
        self.assertEqual(measured_cell["parent"], "main-coverage-backlog")
        self.assertEqual(measured_cell["retry"], {"status": "complete"})
        self.assertEqual(self._errors(family), [])

        rendered = MODULE.coverage_contract_scorecards(family)
        self.assertIn("1/24", rendered)
        self.assertIn("23</b> gaps", rendered)
        self.assertIn("Break down by axis", rendered)
        self.assertIn("TP4", rendered)
        self.assertIn("32K", rendered)
        self.assertNotIn('"active_context_tokens":32768', rendered)
        page = MODULE.family_page(family)
        self.assertIn('data-coverage-contract="dense-main-lane"', page)
        self.assertIn("Dense scorecards summarize every declared combination", page)

    def test_dense_coverage_contract_fails_on_gaps_and_ambiguous_rules(self) -> None:
        axes = [
            {"key": "tp", "label": "TP", "values": [1, 2]},
            {"key": "graph", "label": "Graph", "values": ["off", "on"]},
        ]
        exact = {
            "id": "tp1-off",
            "match": {"tp": 1, "graph": "off"},
            "state": "missing",
        }
        uncovered = {
            "id": "uncovered",
            "label": "Uncovered",
            "axes": axes,
            "rules": [exact],
        }
        _, uncovered_errors = MODULE.expand_coverage_contract(uncovered)
        self._assert_error(uncovered_errors, "leaves cell", "uncovered")

        ambiguous = {
            "id": "ambiguous",
            "label": "Ambiguous",
            "axes": axes,
            "rules": [
                {
                    "id": "fallback",
                    "match": {"tp": "*", "graph": "*"},
                    "state": "missing",
                },
                {
                    "id": "tp1",
                    "match": {"tp": 1, "graph": "*"},
                    "label": "TP1",
                },
                {
                    "id": "graph-off",
                    "match": {"tp": "*", "graph": "off"},
                    "label": "graph off",
                },
            ],
        }
        _, ambiguous_errors = MODULE.expand_coverage_contract(ambiguous)
        self._assert_error(ambiguous_errors, "ambiguous or misordered", "tp")

        incomplete_match = deepcopy(ambiguous)
        incomplete_match["rules"] = [deepcopy(ambiguous["rules"][0])]
        del incomplete_match["rules"][0]["match"]["graph"]
        _, incomplete_errors = MODULE.expand_coverage_contract(incomplete_match)
        self._assert_error(incomplete_errors, "match must name every axis")

    def test_dense_coverage_contract_fixed_selectors_are_exact_and_fail_closed(self) -> None:
        contract = {
            "id": "runtime-slice",
            "label": "Runtime slice",
            "fixed_selectors": {"runtime_family": "runtime-a"},
            "axes": [
                {"key": "tp", "label": "TP", "values": [1, 2]},
                {"key": "kv", "label": "KV", "values": ["f16"]},
            ],
            "rules": [
                {
                    "id": "all-gaps",
                    "match": {"tp": "*", "kv": "*"},
                    "state": "missing",
                }
            ],
        }
        cells, errors = MODULE.expand_coverage_contract(contract)
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 2)
        self.assertTrue(
            all(cell["selectors"]["runtime_family"] == "runtime-a" for cell in cells)
        )
        rendered = MODULE.coverage_contract_scorecards(
            {"coverage_contracts": [contract]}
        )
        self.assertIn("Fixed: runtime_family=runtime-a", rendered)
        self.assertNotIn("<strong>runtime_family</strong>", rendered)

        empty = deepcopy(contract)
        empty["fixed_selectors"] = {}
        self._assert_error(
            MODULE.expand_coverage_contract(empty)[1],
            "fixed_selectors must be a non-empty object",
        )

        wildcard = deepcopy(contract)
        wildcard["fixed_selectors"] = {"runtime_family": "*"}
        self._assert_error(
            MODULE.expand_coverage_contract(wildcard)[1],
            "scalar values excluding '*'",
        )

        repeated = deepcopy(contract)
        repeated["fixed_selectors"] = {"tp": 1}
        self._assert_error(
            MODULE.expand_coverage_contract(repeated)[1],
            "cannot repeat axis keys",
        )

    def test_legacy_mtp_tp_view_keeps_defaults(self) -> None:
        family = self._family()

        self.assertEqual(
            MODULE.coverage_axis(family["coverage_views"][0], "row"),
            {"key": "mtp", "label": "MTP", "prefix": "MTP", "values": [0]},
        )
        self.assertEqual(
            MODULE.coverage_axis(family["coverage_views"][0], "column"),
            {"key": "tp", "label": "TP", "prefix": "TP", "values": [1]},
        )
        self.assertEqual(self._errors(family), [])

        rendered = MODULE.coverage_tables(family)
        self.assertIn("1 card, no speculative decoding", rendered)
        self.assertIn("<code>TP1·MTP0</code>", rendered)
        self.assertIn("✓ Measured", rendered)

    def test_named_axes_fixed_selectors_and_exact_cartesian_cells(self) -> None:
        family = self._family()
        view = {
            "id": "context-by-quant",
            "label": "context × quant",
            "fixed": "Curated deployment slice.",
            "row_axis": {
                "key": "active_context_tokens",
                "label": "Active context",
                "value_labels": {"0": "0", "32768": "32K"},
            },
            "column_axis": {
                "key": "variant",
                "label": "Quantization",
                "prefix": "",
            },
            "fixed_selectors": {
                "revision": "revision-a",
                "runtime": "runtime-a",
                "graph": "off",
            },
            "rows": [0, 32768],
            "columns": ["Q4_K_M", "Q8_0"],
            "cells": {
                "0:Q4_K_M": {"state": "missing", "label": "gap"},
                "0:Q8_0": {"state": "missing", "label": "gap"},
                "32768:Q4_K_M": {"state": "missing", "label": "gap"},
                "32768:Q8_0": {"state": "missing", "label": "gap"},
            },
        }
        family["coverage_views"] = [view]

        self.assertEqual(self._errors(family), [])
        self.assertEqual(
            MODULE.effective_cell_selectors(view, 32768, "Q4_K_M"),
            {
                "revision": "revision-a",
                "runtime": "runtime-a",
                "graph": "off",
                "active_context_tokens": 32768,
                "variant": "Q4_K_M",
            },
        )
        rendered = MODULE.coverage_tables(family)
        self.assertIn("4 untested combinations", rendered)
        self.assertIn("Q4_K_M·0", rendered)
        self.assertIn("Q8_0·32K", rendered)
        self.assertIn("Full matrix and exact selectors", rendered)
        self.assertIn("Fixed: revision=revision-a", rendered)

        missing_cell = deepcopy(family)
        missing_cell["coverage_views"][0]["cells"].pop("32768:Q8_0")
        self.assertTrue(
            any("cells do not exactly match rows×columns" in error for error in self._errors(missing_cell))
        )

        extra_cell = deepcopy(family)
        extra_cell["coverage_views"][0]["cells"]["16384:Q8_0"] = {
            "state": "missing"
        }
        self.assertTrue(
            any("cells do not exactly match rows×columns" in error for error in self._errors(extra_cell))
        )

        no_fixed_selectors = deepcopy(family)
        del no_fixed_selectors["coverage_views"][0]["fixed_selectors"]
        self.assertTrue(
            any("named axes need fixed_selectors" in error for error in self._errors(no_fixed_selectors))
        )

    def test_estimates_are_separate_from_measurements_and_svg_curves(self) -> None:
        family = self._family()
        estimate = self._estimate()
        family["estimates"] = [estimate]
        family["coverage_views"] = [
            {
                "id": "estimated-gap",
                "label": "estimated gap",
                "row_axis": {"key": "mtp", "label": "MTP", "prefix": "MTP"},
                "column_axis": {"key": "tp", "label": "TP", "prefix": "TP"},
                "fixed_selectors": {
                    "revision": "revision-a",
                    "variant": "quant-a",
                    "runtime": "runtime-a",
                    "graph": "off",
                },
                "rows": [4],
                "columns": [1],
                "cells": {
                    "4:1": {
                        "state": "estimated",
                        "estimate_id": estimate["id"],
                    }
                },
            }
        ]
        family["views"] = [self._measured_view()]

        self.assertEqual(self._errors(family), [])
        rendered = MODULE.coverage_tables(family)
        self.assertIn("≈ Estimate", rendered)
        self.assertIn("≈ 42 tok/s (36–48)", rendered)
        self.assertIn("gap-engine 1.0.0", rendered)

        without_estimate = deepcopy(family)
        without_estimate["estimates"] = []
        svg_with_estimate, summary_with_estimate = MODULE.chart_svg(
            family, family["views"][0], "decode_tok_s", True
        )
        svg_without_estimate, summary_without_estimate = MODULE.chart_svg(
            without_estimate, without_estimate["views"][0], "decode_tok_s", True
        )
        self.assertEqual(svg_with_estimate, svg_without_estimate)
        self.assertEqual(summary_with_estimate, summary_without_estimate)
        self.assertNotIn('stroke-dasharray="7 5"', svg_with_estimate)

        estimate_as_measurement = deepcopy(family)
        estimate_as_measurement["run_measurements"].append(
            {
                "id": "illegal-estimate-measurement",
                "state": "estimated",
                "config": {"tp": 2},
                "metrics": {"decode_tok_s": [42.0]},
                "evidence": "https://example.test/illegal-estimate.json",
            }
        )
        self.assertTrue(
            any(
                "illegal-estimate-measurement must use an observed state" in error
                for error in self._errors(estimate_as_measurement)
            )
        )

        estimate_in_curve = deepcopy(family)
        estimate_in_curve["views"][0]["series"][0]["measurement_ids"] = [
            estimate["id"]
        ]
        self.assertTrue(
            any(
                f"references missing {estimate['id']}" in error
                for error in self._errors(estimate_in_curve)
            )
        )

        estimate_with_measurement_evidence = deepcopy(family)
        estimate_with_measurement_evidence["coverage_views"][0]["cells"]["4:1"][
            "evidence_id"
        ] = "measured-a"
        self.assertTrue(
            any(
                "cannot use evidence_id for an estimate" in error
                for error in self._errors(estimate_with_measurement_evidence)
            )
        )

    def test_measurement_selector_matching_fails_closed(self) -> None:
        family = self._family()
        family["coverage_views"][0].update(
            {
                "row_axis": {"key": "mtp", "label": "MTP", "prefix": "MTP"},
                "column_axis": {"key": "tp", "label": "TP", "prefix": "TP"},
                "fixed_selectors": {
                    "revision": "revision-a",
                    "variant": "quant-a",
                    "runtime": "runtime-a",
                    "graph": "off",
                },
            }
        )
        self.assertEqual(self._errors(family), [])

        mismatch = deepcopy(family)
        mismatch["coverage_views"][0]["fixed_selectors"]["runtime"] = "runtime-b"
        self.assertTrue(
            any(
                "selector runtime=runtime-b mismatches measured-a value runtime-a" in error
                for error in self._errors(mismatch)
            )
        )

        absent_from_measurement = deepcopy(family)
        absent_from_measurement["coverage_views"][0]["fixed_selectors"][
            "optimization_overlay_id"
        ] = "none"
        self.assertTrue(
            any(
                "selector optimization_overlay_id=none" in error
                and "measured-a" in error
                for error in self._errors(absent_from_measurement)
            ),
            "a fixed selector absent from the cited measurement must fail closed",
        )

    def test_curated_grade_validation(self) -> None:
        grade = {
            "grade": "A",
            "scope": "exact revision or packet",
            "basis": "curated rubric result",
            "evidence": ["https://example.test/grade.json"],
            "reviewed_at": "2026-08-23",
        }
        self.assertEqual(MODULE.validate_grade(grade, "grade"), [])

        family = self._family()
        family["weight_revisions"][0]["grades"] = {
            "capability": deepcopy(grade)
        }
        family["packets"] = [
            {
                "id": "packet-a",
                "revision": "revision-a",
                "manifest": "https://example.test/packet-a.json",
                "grades": {
                    "capability": deepcopy(grade),
                    "evidence": {**deepcopy(grade), "grade": "B"},
                },
            }
        ]
        family["primary_packet_id"] = "packet-a"
        self.assertEqual(self._errors(family), [])

        invalid = deepcopy(family)
        invalid["packets"][0]["grades"]["evidence"]["grade"] = "E"
        del invalid["packets"][0]["grades"]["evidence"]["evidence"]
        errors = self._errors(invalid)
        self.assertTrue(any("grade must be one of" in error for error in errors))
        self.assertTrue(any("evidence must be a non-empty list" in error for error in errors))

    def test_family_research_metric_needs_exact_projection_workload(self) -> None:
        family = self._family()
        family["run_measurements"][0]["metrics"]["decode_tok_s"] = [42.0]
        family["run_measurements"][0]["workload"] = "p66/o128 fixed rapid suite"
        family["run_measurements"][0]["evidence"] = (
            "https://example.test/research-a.json"
        )
        family["packets"] = [self._research_packet()]
        family["primary_packet_id"] = "research-a"
        self.assertEqual(self._errors(family), [])
        rendered = MODULE.packet_cards(family)
        self.assertIn("42 tok/s", rendered)
        self.assertIn("p66/o128 fixed rapid suite", rendered)
        self.assertNotIn("OPT", rendered)
        self.assertNotIn("projected headroom", rendered)
        self.assertNotIn("data-family-headroom", rendered)

        pinned = deepcopy(family)
        pinned["packets"][0]["projection"].update(
            {"prompt_tokens": 66, "output_tokens": 128}
        )
        self.assertEqual(self._errors(pinned), [])
        rendered = MODULE.packet_cards(pinned)
        self.assertIn("data-family-headroom", rendered)
        self.assertIn('data-ml-prompt="66"', rendered)
        self.assertIn('data-ml-output="128"', rendered)

        half_pinned = deepcopy(family)
        half_pinned["packets"][0]["projection"]["prompt_tokens"] = 66
        self.assertTrue(
            any(
                "must set prompt_tokens and output_tokens together" in error
                for error in self._errors(half_pinned)
            )
        )

    def test_observed_cell_cannot_upgrade_quarantined_evidence(self) -> None:
        family = self._family()
        family["run_measurements"][0]["state"] = "quarantined"

        errors = self._errors(family)
        self._assert_error(errors, "state", "measured-a")

    def test_featured_metric_is_bound_to_exact_measurement(self) -> None:
        family = self._family()
        family["run_measurements"][0]["metrics"]["decode_tok_s"] = [42.0]
        family["run_measurements"][0]["workload"] = "p66/o128 fixed rapid suite"
        family["run_measurements"][0]["evidence"] = (
            "https://example.test/research-a.json"
        )
        family["packets"] = [self._research_packet()]
        family["primary_packet_id"] = "research-a"
        self.assertEqual(self._errors(family), [])

        cases = {}
        missing_id = deepcopy(family)
        del missing_id["packets"][0]["featured_metric"]["measurement_id"]
        cases["measurement binding"] = (missing_id, ("measurement",))

        wrong_value = deepcopy(family)
        wrong_value["packets"][0]["featured_metric"]["value"] = 999.0
        cases["value binding"] = (wrong_value, ("value", "measured-a"))

        wrong_workload = deepcopy(family)
        wrong_workload["packets"][0]["featured_metric"]["workload"] = (
            "different workload"
        )
        cases["workload binding"] = (wrong_workload, ("workload", "measured-a"))

        wrong_evidence = deepcopy(family)
        wrong_evidence["packets"][0]["featured_metric"]["evidence"] = (
            "https://example.test/unrelated.json"
        )
        cases["evidence binding"] = (wrong_evidence, ("evidence", "measured-a"))

        quarantined = deepcopy(family)
        quarantined["run_measurements"][0]["state"] = "quarantined"
        cases["observed state"] = (quarantined, ("state", "measured-a"))

        for name, (candidate, needles) in cases.items():
            with self.subTest(name=name):
                self._assert_error(self._errors(candidate), *needles)

    def test_measured_curve_point_can_fill_a_context_cell(self) -> None:
        family = self._family()
        family["series_measurements"] = [
            {
                "id": "context-curve-a",
                "state": "lab-measured",
                "revision": "revision-a",
                "variant": "quant-a",
                "runtime": "runtime-a",
                "axis": "active_context_tokens",
                "config": {"tp": 1, "mtp": 0, "graph": "off", "kv": "f16"},
                "points": [
                    {"x": 2048, "decode_tok_s": 28.0},
                    {"x": 32768, "decode_tok_s": 21.0},
                ],
                "evidence": "https://example.test/context-a.json",
            }
        ]
        family["coverage_views"] = [
            {
                "id": "context-by-tp",
                "label": "context × TP",
                "row_axis": {
                    "key": "active_context_tokens",
                    "label": "Active context",
                    "value_labels": {"2048": "2K", "32768": "32K"},
                },
                "column_axis": {"key": "tp", "label": "TP", "prefix": "TP"},
                "fixed_selectors": {
                    "revision": "revision-a",
                    "variant": "quant-a",
                    "runtime": "runtime-a",
                    "mtp": 0,
                    "graph": "off",
                    "kv": "f16",
                },
                "rows": [2048, 32768],
                "columns": [1],
                "cells": {
                    "2048:1": {
                        "state": "lab-measured",
                        "label": "D28",
                        "evidence_id": "context-curve-a",
                        "point_x": 2048,
                    },
                    "32768:1": {
                        "state": "lab-measured",
                        "label": "D21",
                        "evidence_id": "context-curve-a",
                        "point_x": 32768,
                    },
                },
            }
        ]
        self.assertEqual(self._errors(family), [])

        absent = deepcopy(family)
        absent["coverage_views"][0]["cells"]["32768:1"]["point_x"] = 16384
        self.assertTrue(
            any("point_x is absent" in error for error in self._errors(absent))
        )

        cases = {}
        wrong_axis = deepcopy(family)
        wrong_axis["series_measurements"][0]["axis"] = "tp"
        cases["axis binding"] = (wrong_axis, ("axis", "context-curve-a"))

        misleading_value = deepcopy(family)
        misleading_value["coverage_views"][0]["cells"]["2048:1"]["label"] = (
            "D999"
        )
        cases["point value binding"] = (
            misleading_value,
            ("label", "context-curve-a"),
        )

        for name, (candidate, needles) in cases.items():
            with self.subTest(name=name):
                self._assert_error(self._errors(candidate), *needles)

    def test_malformed_containers_return_errors_instead_of_crashing(self) -> None:
        cases = []
        for field in (
            "weight_revisions",
            "packets",
            "run_measurements",
            "series_measurements",
            "views",
            "coverage_views",
            "family_closures",
        ):
            family = self._family()
            family[field] = [None]
            cases.append((f"{field} item", family))

        rows = self._family()
        rows["coverage_views"][0]["rows"] = True
        cases.append(("rows container", rows))

        columns = self._family()
        columns["coverage_views"][0]["columns"] = {"bad": 1}
        cases.append(("columns container", columns))

        cells = self._family()
        cells["coverage_views"][0]["cells"] = [{"not": "a mapping"}]
        cases.append(("cells container", cells))

        evidence = self._family()
        evidence["run_measurements"][0]["evidence"] = {"bad": "type"}
        cases.append(("evidence type", evidence))

        estimate_record = self._family()
        estimate_record["estimates"] = [self._estimate()]
        estimate_record["estimates"][0]["record"] = {"bad": "type"}
        cases.append(("estimate record type", estimate_record))

        for name, family in cases:
            with self.subTest(name=name):
                try:
                    errors = self._errors(family)
                except Exception as error:  # pragma: no cover - regression guard
                    self.fail(f"validator crashed for {name}: {type(error).__name__}: {error}")
                self.assertTrue(errors, f"malformed {name} must be rejected")

    def test_generate_does_not_render_a_family_after_validation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "families").mkdir()
            (root / "packages").mkdir()
            (root / "models").mkdir()
            (root / "repro").mkdir()
            (root / "results").mkdir()
            bad_manifest = {
                "format": "neural-download-model-family-v1",
                "name": "Missing id",
                "weight_revisions": [],
                "packets": [],
                "run_measurements": [],
                "series_measurements": [],
                "views": [],
                "coverage_views": [],
                "family_closures": [],
                "estimates": [],
            }
            (root / "families/bad.json").write_text(json.dumps(bad_manifest))
            (root / "families/catalog.json").write_text(
                json.dumps(
                    {
                        "format": "neural-download-model-family-catalog-v1",
                        "families": [
                            {"id": "bad", "manifest": "families/bad.json"}
                        ],
                    }
                )
            )
            (root / "packages/catalog.json").write_text(
                json.dumps({"packages": []})
            )
            (root / "repro/guide-catalog.json").write_text(
                json.dumps({"guides": []})
            )
            (root / "families/coverage-registry.json").write_text(
                json.dumps(
                    {
                        "format": "neural-download-coverage-registry-v1",
                        "planned_families": [],
                        "lanes": [],
                    }
                )
            )

            with (
                patch.object(MODULE, "ROOT", root),
                patch.object(MODULE, "CATALOG", root / "families/catalog.json"),
                patch.object(
                    MODULE,
                    "COVERAGE_REGISTRY",
                    root / "families/coverage-registry.json",
                ),
                patch.object(
                    MODULE, "PACKAGE_CATALOG", root / "packages/catalog.json"
                ),
                patch.object(
                    MODULE, "GUIDE_CATALOG", root / "repro/guide-catalog.json"
                ),
                patch.object(MODULE, "OUT_DIR", root / "models"),
            ):
                self.assertEqual(MODULE.generate(check=True), 1)

    def test_public_coverage_registry_is_complete_and_lane_based(self) -> None:
        registry = json.loads(MODULE.COVERAGE_REGISTRY.read_text())
        catalog = json.loads(MODULE.CATALOG.read_text())
        family_ids = {entry["id"] for entry in catalog["families"]}
        expected, inventory_errors = MODULE.public_evidence_inventory()
        self.assertEqual(inventory_errors, [])

        errors, summary = MODULE.validate_coverage_registry(
            registry, family_ids, expected
        )
        self.assertEqual(errors, [])
        self.assertEqual(summary["artifacts"], len(expected))
        self.assertLess(
            summary["lanes"],
            summary["artifacts"],
            "aliases across package/repro/result surfaces must count as one lane",
        )

        new_public_evidence = dict(expected)
        new_public_evidence["results/new-public-lane/README.md"] = "result"
        errors, _ = MODULE.validate_coverage_registry(
            registry, family_ids, new_public_evidence
        )
        self._assert_error(errors, "unmapped public evidence", "new-public-lane")

        duplicate = deepcopy(registry)
        duplicate["lanes"][1]["artifacts"].append(
            deepcopy(duplicate["lanes"][0]["artifacts"][0])
        )
        errors, _ = MODULE.validate_coverage_registry(
            duplicate, family_ids, expected
        )
        self._assert_error(errors, "assigned to both")

    def test_family_id_is_a_safe_slug_and_json_ld_cannot_break_out(self) -> None:
        unsafe_id = self._family()
        unsafe_id["id"] = '../../outside" onmouseover="alert(1)'
        self._assert_error(self._errors(unsafe_id), "id")

        script_payload = "x</script><script>alert(1)</script>"
        family = self._family()
        family["display_name"] = script_payload
        rendered = MODULE.family_page(family)
        self.assertNotIn(script_payload, rendered)
        self.assertNotIn("</script><script>alert(1)</script>", rendered)

    def test_featured_results_are_exact_and_never_infer_full_quality(self) -> None:
        family = self._family()
        family["featured_results"] = [
            {
                "role": "hero",
                "label": "Explicit strict selection",
                "measurement_id": "measured-a",
                "metric": "decode_tok_s",
                "sample_index": 0,
                "quality_label": "Bounded declared quality scope",
            }
        ]
        self.assertEqual(self._errors(family), [])
        rendered = MODULE.family_page(family)
        # The hero binding renders as the page headline (the one number a
        # visitor came for) and is not repeated in the strip; it carries the
        # declared quality scope verbatim, never an inferred gate.
        self.assertIn('<span class="big">30</span>', rendered)
        self.assertNotIn('<b>30</b>', rendered)
        self.assertNotIn('<b>30.2</b>', rendered)
        self.assertIn("hero-headline", rendered)
        self.assertIn("Bounded declared quality scope", rendered)
        self.assertNotIn("full quality gate", rendered.casefold())

        invalid = deepcopy(family)
        invalid["featured_results"][0]["sample_index"] = 9
        self._assert_error(self._errors(invalid), "featured_results", "select")

    def test_qwen27_curated_strip_keeps_graph_results_not_eager_insertion_order(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        entries = MODULE.featured_result_entries(family)
        self.assertEqual(
            [entry["value"] for entry in entries],
            [
                71.45427094575045,
                30.329809361830037,
                49.05894025767351,
                71.9001988117144,
            ],
        )
        rendered = MODULE.family_page(family)
        strip = re.search(
            r'<div class="result-strip".*?</div>', rendered, re.DOTALL
        )
        self.assertIsNotNone(strip)
        strip_html = strip.group(0)
        # The curated hero (71.45) is the page headline; the other curated
        # results stay in the strip, in curated order, never eager captures.
        self.assertIn("hero-headline", rendered)
        self.assertIn('<span class="big">71.45</span>', rendered)
        for protected in ("30.33", "49.06", "71.9"):
            self.assertIn(protected, strip_html)
        for eager in ("24.25", "16.77", "17.38", "71.72"):
            self.assertNotIn(eager, strip_html)
        measured_heading = rendered.index("<h2>Measured results</h2>")
        # Answer first: the results strip precedes packets, which precede the
        # measured-detail section.
        self.assertLess(rendered.index('class="result-strip"'), rendered.index("Packets and recipes"))
        self.assertLess(rendered.index("Packets and recipes"), measured_heading)
        self.assertLess(rendered.index("What has been classified"), measured_heading)

    def test_qwen27_dense_tp1_contracts_use_runtime_capability_vocabularies(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        expected_counts = {
            "qwen36-tp1-vllm-xpu-target-matrix": 189,
            "qwen36-tp1-vllm-xpu-autoround-mtp-matrix": 252,
            "qwen36-tp1-llamacpp-sycl-mtp-matrix": 448,
            "qwen36-tp1-llamacpp-sycl-target-matrix": 168,
            "qwen38-tp1-vllm-xpu-target-matrix": 126,
            "qwen38-tp1-vllm-xpu-autoround-mtp-matrix": 252,
            "qwen38-e9d1398-vllm-xpu-autoround-closure-matrix": 96,
            "qwen38-tp1-llamacpp-sycl-target-matrix": 112,
            "qwen38-tp1-llamacpp-sycl-mtp-package-matrix": 224,
            "qwen38-tp1-vllm-xpu-autoround-f01e-mtp4-eager-depth": 7,
            "qwen38-tp2-llamacpp-sycl-q4km-http-depth": 7,
            "qwen38-tp2-llamacpp-sycl-q8-http-depth": 7,
            "qwen38-tp2-vllm-xpu-fp8-http-depth": 7,
            "qwen38-tp4-vllm-xpu-fp8-http-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-http-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-http-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-eager-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-piecewise-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-mtp1-piecewise-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-mtp2-piecewise-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-mtp1-eager-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-mtp2-eager-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-mtp3-eager-depth": 7,
            "qwen38-tp2-vllm-xpu-autoround-f01e-mtp4-eager-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-f01e-eager-oracle-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-f01e-piecewise-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-f01e-mtp1-piecewise-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-f01e-mtp1-eager-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-f01e-mtp2-eager-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-f01e-mtp3-eager-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-f01e-mtp4-eager-depth": 7,
            "qwen38-tp4-vllm-xpu-autoround-strict-snapshot": 1,
        }
        self.assertEqual(set(contracts), set(expected_counts))
        self.assertEqual(self._errors(family), [])

        all_cells = []
        for contract_id, expected_count in expected_counts.items():
            cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
            self.assertEqual(errors, [], contract_id)
            self.assertEqual(len(cells), expected_count, contract_id)
            all_cells.extend(cells)
        self.assertEqual(len(all_cells), 2022)

        tp4_graph_mtp1_cells, errors = MODULE.expand_coverage_contract(
            contracts["qwen38-tp4-vllm-xpu-autoround-f01e-mtp1-piecewise-depth"]
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in tp4_graph_mtp1_cells if cell["state"] == "lab-measured"],
            [4096],
        )
        graph_mtp1_4k = next(cell for cell in tp4_graph_mtp1_cells if cell["state"] == "lab-measured")
        self.assertEqual(graph_mtp1_4k["evidence_id"], "q38-f01e-autoround-tp4-mtp1-piecewise-f16-exact-4k-r1-grade-c")
        self.assertEqual(graph_mtp1_4k["packet_id"], "qwen38-27b-autoround-int4-tp4-f01e-mtp1-piecewise-f16-4k-grade-c")
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in tp4_graph_mtp1_cells if cell["state"] == "missing"],
            [0, 2048, 8192, 16384, 24576, 32768],
        )

        fp8_tp1_cells, errors = MODULE.expand_coverage_contract(
            contracts["qwen38-tp1-vllm-xpu-target-matrix"]
        )
        self.assertEqual(errors, [])
        capacity_excluded = [
            cell
            for cell in fp8_tp1_cells
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-official-fp8-017b9c7"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
            and cell["state"] == "unsupported"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in capacity_excluded],
            [16384, 24576, 32768],
        )
        self.assertTrue(all("8,448-token profile" in cell["label"] for cell in capacity_excluded))
        official_fp8_x0 = next(
            cell
            for cell in fp8_tp1_cells
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-official-fp8-017b9c7"
            and cell["selectors"]["active_context_tokens"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        )
        self.assertEqual(official_fp8_x0["state"], "missing")

        e9d_contract = contracts[
            "qwen38-e9d1398-vllm-xpu-autoround-closure-matrix"
        ]
        self.assertEqual(
            e9d_contract["fixed_selectors"]["runtime"],
            "vLLM XPU nightly e9d1398d9",
        )
        self.assertNotEqual(
            e9d_contract["fixed_selectors"]["runtime"],
            "vLLM XPU 0.27.2rc1.dev77+gac7509e2b.xpu",
        )
        e9d_cells, errors = MODULE.expand_coverage_contract(e9d_contract)
        self.assertEqual(errors, [])
        self.assertEqual(
            Counter(cell["state"] for cell in e9d_cells),
            Counter(
                {
                    "unsupported": 48,
                    "quarantined": 33,
                    "lab-measured": 9,
                    "closed": 6,
                }
            ),
        )
        self.assertFalse(any(cell["state"] == "missing" for cell in e9d_cells))

        q38_llama_cells, errors = MODULE.expand_coverage_contract(
            contracts["qwen38-tp1-llamacpp-sycl-target-matrix"]
        )
        self.assertEqual(errors, [])
        self.assertFalse(any(cell["state"] == "estimated" for cell in q38_llama_cells))
        for artifact_id, evidence_id in (
            (
                "qwen38-27b-unsloth-ud-q4-k-xl-4ca7207",
                "q38-q4kxl-tp1-q8kv-target-http-context-r1-grade-c",
            ),
            (
                "qwen38-27b-ggmlorg-q8-0-0669b98",
                "q38-q8weights-tp1-q8kv-target-http-context-r1-grade-c",
            ),
        ):
            exact_replacements = [
                cell
                for cell in q38_llama_cells
                if cell["selectors"]["artifact_id"] == artifact_id
                and cell["selectors"]["graph_mode"] == "off"
                and cell["selectors"]["kv"] == "q8_0"
            ]
            self.assertEqual(len(exact_replacements), 7)
            self.assertTrue(
                all(
                    cell["state"] == "lab-measured"
                    and cell["evidence_id"] == evidence_id
                    and "estimate_id" not in cell
                    for cell in exact_replacements
                )
            )

        for contract_id, evidence_id in (
            ("qwen38-tp2-llamacpp-sycl-q4km-http-depth", "q38-q4km-tp2-f16kv-http-context-r1-grade-c"),
            ("qwen38-tp2-llamacpp-sycl-q8-http-depth", "q38-q8weights-tp2-f16kv-http-context-r3-grade-c"),
            ("qwen38-tp2-vllm-xpu-fp8-http-depth", "q38-official-fp8-tp2-f16kv-http-context-r1-grade-c"),
        ):
            cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
            self.assertEqual(errors, [], contract_id)
            self.assertEqual(len(cells), 7, contract_id)
            self.assertEqual(cells[0]["selectors"]["active_context_tokens"], 0)
            self.assertEqual(cells[0]["state"], "missing")
            self.assertEqual(
                [cell["selectors"]["active_context_tokens"] for cell in cells[1:]],
                [2048, 4096, 8192, 16384, 24576, 32768],
            )
            self.assertTrue(all(
                cell["state"] == "lab-measured"
                and cell["evidence_id"] == evidence_id
                and cell["selectors"]["tp"] == 2
                and cell["selectors"]["mtp"] == 0
                and cell["selectors"]["kv"] == "f16"
                for cell in cells[1:]
            ))

        q36_cells = [
            cell
            for contract_id, contract in contracts.items()
            if contract_id.startswith("qwen36-")
            for cell in MODULE.expand_coverage_contract(contract)[0]
        ]
        self.assertEqual(len(q36_cells), 1057)
        self.assertEqual(
            sum(cell["state"] == "quarantined" for cell in q36_cells), 63
        )
        self.assertEqual(sum(cell["state"] == "missing" for cell in q36_cells), 826)
        self.assertEqual(
            sum(cell["state"] == "lab-measured" for cell in q36_cells), 140
        )
        self.assertEqual(
            sum(cell["state"] == "lab-screened" for cell in q36_cells), 28
        )
        self.assertEqual(sum(cell["state"] == "estimated" for cell in q36_cells), 0)

        q36_mtp3_http_f16 = [
            cell
            for cell in q36_cells
            if cell.get("evidence_id")
            == "q36-mtpq8-tp1-mtp3-f16-http-context-r3"
        ]
        self.assertEqual(len(q36_mtp3_http_f16), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q36_mtp3_http_f16],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(
            all(
                cell["selectors"]["artifact_id"]
                == "qwen36-27b-unsloth-mtp-q8-0-5cb35eb"
                and cell["selectors"]["mtp"] == 3
                and cell["selectors"]["graph_mode"] == "off"
                and cell["selectors"]["kv"] == "f16"
                for cell in q36_mtp3_http_f16
            )
        )

        series = {item["id"]: item for item in family["series_measurements"]}
        mtp3 = series["q36-mtpq8-tp1-mtp3-f16-http-context-r3"]
        control = series["q36-mtpq8-tp1-mtp0-f16-http-context-r3"]
        self.assertEqual(
            [point["x"] for point in mtp3["points"]],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertEqual(mtp3["points"][0]["physical_prompt_tokens"], 1)
        self.assertIn("not a literal empty prompt", mtp3["caveat"])
        self.assertTrue(mtp3["comparison_to_control"]["all_seven_outputs_exact"])
        self.assertTrue(
            mtp3["comparison_to_control"][
                "all_seven_draft_counters_engaged_and_conserved"
            ]
        )
        self.assertEqual(len(control["points"]), 7)
        self.assertEqual(family["primary_packet_id"], "qwen38-27b-256k-vision-mtp-b70")

        result = json.loads(
            (
                MODULE.ROOT
                / "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r3-result.json"
            ).read_text()
        )
        self.assertEqual(result["raw_inventory_file_count"], 47)
        self.assertEqual(len(result["raw_artifacts"]), 47)
        self.assertEqual(
            len({item["path"] for item in result["raw_artifacts"]}), 47
        )
        self.assertEqual(result["scope"]["completion_tokens"], 128)
        self.assertEqual(result["scope"]["metric_intervals"], 99)
        self.assertEqual(result["correctness"]["needle"]["api_usage_prompt_tokens"], 27246)
        self.assertTrue(
            all(
                cell.get("control_stdout_mirror_sha256")
                == cell["control_receipt_sha256"]
                and cell.get("candidate_stdout_mirror_sha256")
                == cell["candidate_receipt_sha256"]
                and cell.get("draft_counters_sha256")
                for cell in result["cells"]
            )
        )

        mtp124_result = json.loads(
            (
                MODULE.ROOT
                / "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp124-exact-depth-quality-r1-result.json"
            ).read_text()
        )
        inventory = json.loads(
            (MODULE.ROOT / mtp124_result["raw_inventory"]["path"]).read_text()
        )
        self.assertEqual(inventory["file_count"], 105)
        self.assertEqual(len(inventory["files"]), 105)
        self.assertEqual(
            mtp124_result["raw_inventory"]["sha256"],
            "1d386022c1540827abcf1b9fa01fb8ccac9e922b69db1fbdad8c3a482d06d388",
        )
        self.assertEqual(
            [battery["quality_result_sha256"] for battery in mtp124_result["quality_batteries"]],
            [
                "03fee366374e7bae15d708a257570619afcc9b60f6d5b8e5c3bb166576bd811c",
                "96e7f69879db03ad262145632b2cf31754143b595e3597abbc0495cb2643f7c0",
                "2a1f59480702882f1d9a441c8548c31e41caefd69e4fa60eb943921bf05485a7",
            ],
        )
        self.assertTrue(
            all(
                battery["exact_canaries"] == 4
                and battery["stable_repeats"] == 2
                and battery["needle"]["api_usage_prompt_tokens"] == 27246
                and battery["needle"]["passed"]
                for battery in mtp124_result["quality_batteries"]
            )
        )
        candidate_cells = [
            cell
            for arm in mtp124_result["arms"]
            if arm["mtp"] in (1, 2, 4)
            for cell in arm["cells"]
        ]
        self.assertEqual(len(candidate_cells), 21)
        self.assertTrue(
            all(
                cell["target_output_parity"]
                and cell["draft_counters"]["passed"]
                for cell in candidate_cells
            )
        )
        for arm in ("candidate-mtp1", "candidate-mtp2", "candidate-mtp4"):
            argv = mtp124_result["runtime_identity"]["server_argv"][arm]
            self.assertEqual(argv[argv.index("--spec-draft-type-k") + 1], "f16")
            self.assertEqual(argv[argv.index("--spec-draft-type-v") + 1], "f16")
        mtp124_cells = [
            cell
            for cell in q36_cells
            if cell.get("evidence_id") in {
                "q36-mtpq8-tp1-mtp1-f16-http-context-r1",
                "q36-mtpq8-tp1-mtp2-f16-http-context-r1",
                "q36-mtpq8-tp1-mtp4-f16-http-context-r1",
            }
        ]
        self.assertEqual(len(mtp124_cells), 21)
        self.assertEqual(
            sorted({cell["selectors"]["mtp"] for cell in mtp124_cells}),
            [1, 2, 4],
        )
        self.assertTrue(
            all(
                cell["selectors"]["graph_mode"] == "off"
                and cell["selectors"]["kv"] == "f16"
                for cell in mtp124_cells
            )
        )

        q36_embedded_graph_f16 = [
            cell
            for cell in q36_cells
            if cell.get("evidence_id") == "q36-mtpq8-tp1-graph-f16-context"
        ]
        self.assertEqual(len(q36_embedded_graph_f16), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q36_embedded_graph_f16],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(
            all(
                cell["selectors"]["artifact_id"]
                == "qwen36-27b-unsloth-mtp-q8-0-5cb35eb"
                and cell["selectors"]["graph_mode"] == "SYCL"
                and cell["selectors"]["kv"] == "f16"
                and cell["selectors"]["mtp"] == 0
                for cell in q36_embedded_graph_f16
            )
        )

        q36_q4km_graph_f16 = [
            cell
            for cell in q36_cells
            if cell.get("evidence_id") == "q36-q4km-tp1-graph-f16-context"
        ]
        self.assertEqual(len(q36_q4km_graph_f16), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q36_q4km_graph_f16],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(
            all(
                cell["selectors"]["artifact_id"]
                == "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"
                and cell["selectors"]["graph_mode"] == "SYCL"
                and cell["selectors"]["kv"] == "f16"
                and cell["selectors"]["mtp"] == 0
                for cell in q36_q4km_graph_f16
            )
        )

        q36_q4km_graph_q8 = [
            cell
            for cell in q36_cells
            if cell.get("evidence_id") == "q36-q4km-tp1-graph-q8-context"
        ]
        self.assertEqual(len(q36_q4km_graph_q8), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q36_q4km_graph_q8],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(
            all(
                cell["selectors"]["artifact_id"]
                == "qwen36-27b-unsloth-mtp-q4-k-m-5cb35eb"
                and cell["selectors"]["graph_mode"] == "SYCL"
                and cell["selectors"]["kv"] == "q8_0"
                and cell["selectors"]["mtp"] == 0
                for cell in q36_q4km_graph_q8
            )
        )

        q36_embedded_graph_q8 = [
            cell
            for cell in q36_cells
            if cell.get("evidence_id") == "q36-mtpq8-tp1-graph-q8-context"
        ]
        self.assertEqual(len(q36_embedded_graph_q8), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q36_embedded_graph_q8],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(
            all(
                cell["selectors"]["artifact_id"]
                == "qwen36-27b-unsloth-mtp-q8-0-5cb35eb"
                and cell["selectors"]["graph_mode"] == "SYCL"
                and cell["selectors"]["kv"] == "q8_0"
                and cell["selectors"]["mtp"] == 0
                for cell in q36_embedded_graph_q8
            )
        )

        grade_c_packet_id = (
            "qwen36-27b-embedded-mtp-q8-q8kv-tp1-mtp1234-grade-c"
        )
        q36_q8kv_grade_c = [
            cell
            for cell in q36_cells
            if cell.get("packet_id") == grade_c_packet_id
        ]
        self.assertEqual(len(q36_q8kv_grade_c), 28)
        self.assertEqual(
            sorted({cell["selectors"]["mtp"] for cell in q36_q8kv_grade_c}),
            [1, 2, 3, 4],
        )
        self.assertTrue(
            all(
                cell["state"] == "lab-screened"
                and cell["selectors"]["artifact_id"]
                == "qwen36-27b-unsloth-mtp-q8-0-5cb35eb"
                and cell["selectors"]["graph_mode"] == "off"
                and cell["selectors"]["kv"] == "q8_0"
                and "Grade C" in cell["label"]
                for cell in q36_q8kv_grade_c
            )
        )
        for mtp in (1, 2, 3, 4):
            route = [
                cell
                for cell in q36_q8kv_grade_c
                if cell["selectors"]["mtp"] == mtp
            ]
            self.assertEqual(
                [cell["selectors"]["active_context_tokens"] for cell in route],
                [0, 2048, 4096, 8192, 16384, 24576, 32768],
            )
            divergent = [
                cell
                for cell in route
                if cell["selectors"]["active_context_tokens"] == 2048
            ]
            self.assertEqual(len(divergent), 1)
            self.assertIn("divergent", divergent[0]["label"])
            self.assertIn("deterministic output divergence", divergent[0]["reason"])

        grade_c_series = {
            mtp: series[
                f"q36-mtpq8-tp1-mtp{mtp}-q8kv-http-context-r1-grade-c"
            ]
            for mtp in (1, 2, 3, 4)
        }
        r1_path = (
            MODULE.ROOT
            / "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp1234-exact-depth-quality-r1-result.json"
        )
        r1_result = json.loads(r1_path.read_text())
        self.assertEqual(
            r1_result["classification"],
            "failed-global-cross-kv-seal-partial-quality-positive-no-publication",
        )
        self.assertTrue(all(arm["quality"]["passed"] for arm in r1_result["arms"][1:]))
        for mtp, measurement in grade_c_series.items():
            arm = next(arm for arm in r1_result["arms"] if arm["mtp"] == mtp)
            self.assertEqual(measurement["state"], "lab-screened")
            self.assertEqual(
                [point["decode_tok_s"] for point in measurement["points"]],
                [cell["serving_decode_tok_s_99_interval"] for cell in arm["cells"]],
            )
            self.assertEqual(
                [point["fresh_control_exact"] for point in measurement["points"]],
                [cell["matches_fresh_q8kv_control"] for cell in arm["cells"]],
            )
            self.assertIn("R1 remains failed", measurement["quality"])

        grade_c_packet = next(
            packet for packet in family["packets"] if packet["id"] == grade_c_packet_id
        )
        self.assertNotIn("featured_metric", grade_c_packet)
        self.assertIn("failed", grade_c_packet["status"])
        self.assertEqual(grade_c_packet["grades"]["evidence"]["grade"], "C")
        r3_path = (
            MODULE.ROOT
            / "experiments/qwen36-27b-mtp-gguf-q4-b70/data/2026-08-25-qwen36-mtpq8-q8kv-tp1-mtp01234-exact2k-classification-r3-result.json"
        )
        self.assertEqual(
            hashlib.sha256(r3_path.read_bytes()).hexdigest(),
            "3f63f3e7c1d28f2305ec561cb084b04ecba29187d238859d768fa6e72bc12661",
        )
        r3_result = json.loads(r3_path.read_text())
        self.assertEqual(r3_result["classification"], "grade-c-deterministic-route-divergence")
        self.assertEqual(r3_result["grade"]["packet_grade"], "C")
        self.assertFalse(r3_result["authority"]["direct_site_publication"])

        for contract_id, contract in contracts.items():
            if "-tp1-" not in contract_id or not contract_id.endswith("-matrix"):
                continue
            axes = {axis["key"]: axis["values"] for axis in contract["axes"]}
            if "target-matrix" in contract_id:
                self.assertEqual(axes["mtp"], [0])
            else:
                self.assertNotIn(0, axes["mtp"])
            if "vllm-xpu" in contract_id:
                self.assertEqual(
                    axes["graph_mode"],
                    ["off", "FULL_AND_PIECEWISE", "PIECEWISE"],
                )
                self.assertEqual(axes["kv"], ["f16", "fp8_e4m3", "fp8_e5m2"])
            else:
                self.assertEqual(axes["graph_mode"], ["off", "SYCL"])
                self.assertEqual(axes["kv"], ["f16", "q8_0"])

        q38_target, _ = MODULE.expand_coverage_contract(
            contracts["qwen38-tp1-llamacpp-sycl-target-matrix"]
        )
        self.assertEqual(
            sum(cell["state"] == "lab-measured" for cell in q38_target), 84
        )
        self.assertEqual(sum(cell["state"] == "estimated" for cell in q38_target), 0)
        self.assertTrue(all(cell["selectors"]["mtp"] == 0 for cell in q38_target))
        q38_q4kxl_graph = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-unsloth-ud-q4-k-xl-4ca7207"
            and cell["selectors"]["graph_mode"] == "SYCL"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q4kxl_graph), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q4kxl_graph],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q4kxl-tp1-f16kv-sycl-graph-cache64-http-context-r3-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q4kxl-f16kv-sycl-graph-cache64-depth-grade-c"
            for cell in q38_q4kxl_graph
        ))
        q38_q4kxl_graph_measurement = series[
            "q38-q4kxl-tp1-f16kv-sycl-graph-cache64-http-context-r3-grade-c"
        ]
        q38_q4kxl_graph_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4kxl-f16kv-tp1-sycl-graph-cache64-depth-quality-r3-result.json"
        ).read_text())
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q4kxl_graph_measurement["points"]],
            [cell["serving_decode_tok_s_99_interval"] for cell in q38_q4kxl_graph_result["serving_curve"]["cells"]],
        )
        self.assertTrue(q38_q4kxl_graph_result["quality"]["pass_all"])
        self.assertTrue(q38_q4kxl_graph_result["graph_mechanism"]["passed"])
        self.assertEqual(q38_q4kxl_graph_result["graph_mechanism"]["cache_limit"], 64)
        self.assertGreaterEqual(
            q38_q4kxl_graph_result["graph_mechanism"]["direct_replay"],
            q38_q4kxl_graph_result["graph_mechanism"]["minimum_direct_replays"],
        )
        self.assertEqual(
            q38_q4kxl_graph_result["validation_recovery"]["classification"],
            "offline-validator-recovery-no-gpu-rerun",
        )
        self.assertFalse(
            q38_q4kxl_graph_result["authority"]["protected_or_headline_replacement"]
        )
        q38_q5ks_graph = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-unsloth-ud-q5-k-s-4ca7207"
            and cell["selectors"]["graph_mode"] == "SYCL"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q5ks_graph), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q5ks_graph],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q5ks-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q5ks-f16kv-sycl-graph-cache64-depth-grade-c"
            for cell in q38_q5ks_graph
        ))
        q38_q5ks_graph_measurement = series[
            "q38-q5ks-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"
        ]
        q38_q5ks_graph_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q5ks-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(
            [point["x"] for point in q38_q5ks_graph_measurement["points"]],
            [cell["active_context_tokens"] for cell in q38_q5ks_graph_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q5ks_graph_measurement["points"]],
            [cell["serving_decode_tok_s_99_interval"] for cell in q38_q5ks_graph_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["output_token_ids_sha256"] for point in q38_q5ks_graph_measurement["points"]],
            [cell["output_token_ids_sha256"] for cell in q38_q5ks_graph_result["serving_curve"]["cells"]],
        )
        self.assertTrue(q38_q5ks_graph_result["quality"]["pass_all"])
        self.assertTrue(q38_q5ks_graph_result["graph_mechanism"]["passed"])
        self.assertEqual(q38_q5ks_graph_result["graph_mechanism"]["cache_limit"], 64)
        self.assertGreaterEqual(
            q38_q5ks_graph_result["graph_mechanism"]["direct_replay"],
            q38_q5ks_graph_result["graph_mechanism"]["minimum_direct_replays"],
        )
        self.assertEqual(
            q38_q5ks_graph_result["validation"]["terminal_checks_passed"], 19
        )
        self.assertFalse(q38_q5ks_graph_result["validation"]["offline_recovery"])
        self.assertFalse(
            q38_q5ks_graph_result["authority"]["protected_or_headline_replacement"]
        )
        q38_q5ks_graph_packet = next(
            packet for packet in family["packets"]
            if packet["id"]
            == "qwen38-27b-q5ks-f16kv-sycl-graph-cache64-depth-grade-c"
        )
        self.assertEqual(q38_q5ks_graph_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q5ks_graph_packet)

        q38_q4km_graph = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-ggmlorg-q4-k-m-0669b98"
            and cell["selectors"]["graph_mode"] == "SYCL"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q4km_graph), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q4km_graph],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q4km-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q4km-f16kv-sycl-graph-cache64-depth-grade-c"
            for cell in q38_q4km_graph
        ))
        q38_q4km_graph_measurement = series[
            "q38-q4km-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"
        ]
        q38_q4km_graph_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4km-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(
            [point["x"] for point in q38_q4km_graph_measurement["points"]],
            [cell["active_context_tokens"] for cell in q38_q4km_graph_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q4km_graph_measurement["points"]],
            [cell["serving_decode_tok_s_99_interval"] for cell in q38_q4km_graph_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["output_token_ids_sha256"] for point in q38_q4km_graph_measurement["points"]],
            [cell["output_token_ids_sha256"] for cell in q38_q4km_graph_result["serving_curve"]["cells"]],
        )
        self.assertTrue(q38_q4km_graph_result["quality"]["pass_all"])
        self.assertTrue(q38_q4km_graph_result["graph_mechanism"]["passed"])
        self.assertEqual(q38_q4km_graph_result["graph_mechanism"]["cache_limit"], 64)
        self.assertGreaterEqual(
            q38_q4km_graph_result["graph_mechanism"]["direct_replay"],
            q38_q4km_graph_result["graph_mechanism"]["minimum_direct_replays"],
        )
        self.assertEqual(q38_q4km_graph_result["validation"]["terminal_checks_passed"], 19)
        self.assertFalse(q38_q4km_graph_result["validation"]["offline_recovery"])
        self.assertFalse(
            q38_q4km_graph_result["authority"]["protected_or_headline_replacement"]
        )
        q38_q4km_graph_packet = next(
            packet for packet in family["packets"]
            if packet["id"]
            == "qwen38-27b-q4km-f16kv-sycl-graph-cache64-depth-grade-c"
        )
        self.assertEqual(q38_q4km_graph_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q4km_graph_packet)
        q38_tp2_depth, _ = MODULE.expand_coverage_contract(
            contracts["qwen38-tp2-vllm-xpu-autoround-http-depth"]
        )
        self.assertEqual(len(q38_tp2_depth), 7)
        self.assertEqual(q38_tp2_depth[0]["selectors"]["active_context_tokens"], 0)
        self.assertEqual(q38_tp2_depth[0]["state"], "missing")
        self.assertNotIn("point_x", q38_tp2_depth[0])
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_tp2_depth[1:]],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-autoround-tp2-f16kv-http-context-r1-grade-c"
            and cell["selectors"]["tp"] == 2
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "FULL_AND_PIECEWISE"
            and cell["selectors"]["kv"] == "f16"
            for cell in q38_tp2_depth[1:]
        ))
        tp2_depth_measurement = series[
            "q38-autoround-tp2-f16kv-http-context-r1-grade-c"
        ]
        tp2_depth_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-b2dd9ce73d-tp2-exact-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(
            [point["x"] for point in tp2_depth_measurement["points"]],
            [cell["active_context_tokens"] for cell in tp2_depth_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["decode_tok_s"] for point in tp2_depth_measurement["points"]],
            [cell["serving_decode_tok_s_99_interval"] for cell in tp2_depth_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["output_token_ids_sha256"] for point in tp2_depth_measurement["points"]],
            [cell["output_token_ids_sha256"] for cell in tp2_depth_result["serving_curve"]["cells"]],
        )
        self.assertNotIn(0, [point["x"] for point in tp2_depth_measurement["points"]])
        self.assertFalse(
            tp2_depth_result["authority"]["protected_or_headline_replacement"]
        )
        tp2_depth_packet = next(
            packet for packet in family["packets"]
            if packet["id"]
            == "qwen38-27b-autoround-int4-tp2-b2dd-http-depth-grade-c"
        )
        self.assertEqual(tp2_depth_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", tp2_depth_packet)
        q38_tp4_snapshot, _ = MODULE.expand_coverage_contract(
            contracts["qwen38-tp4-vllm-xpu-autoround-strict-snapshot"]
        )
        self.assertEqual(len(q38_tp4_snapshot), 1)
        tp4_cell = q38_tp4_snapshot[0]
        self.assertEqual(tp4_cell["state"], "lab-measured")
        self.assertEqual(
            tp4_cell["evidence_id"], "q38-b2dd-1e90-tp4-strict-pair"
        )
        self.assertNotIn("active_context_tokens", tp4_cell["selectors"])
        self.assertNotIn("point_x", tp4_cell)
        self.assertEqual(
            (
                tp4_cell["selectors"]["tp"],
                tp4_cell["selectors"]["mtp"],
                tp4_cell["selectors"]["graph_mode"],
                tp4_cell["selectors"]["kv"],
            ),
            (4, 0, "FULL_AND_PIECEWISE", "f16"),
        )
        tp4_measurement = next(
            measurement
            for measurement in family["run_measurements"]
            if measurement["id"] == "q38-b2dd-1e90-tp4-strict-pair"
        )
        self.assertEqual(
            tp4_measurement["metrics"]["decode_tok_s"],
            [71.77179128057259, 71.82969607434323],
        )
        self.assertIn("offline recovery", tp4_measurement["caveat"])
        self.assertIn("No historical high was lowered or replaced", tp4_measurement["caveat"])
        q38_tp4_depth, _ = MODULE.expand_coverage_contract(
            contracts["qwen38-tp4-vllm-xpu-autoround-http-depth"]
        )
        self.assertEqual(len(q38_tp4_depth), 7)
        self.assertEqual(q38_tp4_depth[0]["selectors"]["active_context_tokens"], 0)
        self.assertEqual(q38_tp4_depth[0]["state"], "missing")
        self.assertNotIn("point_x", q38_tp4_depth[0])
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_tp4_depth[1:]],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-autoround-tp4-f16kv-http-context-r1-grade-c"
            and cell["selectors"]["tp"] == 4
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "FULL_AND_PIECEWISE"
            and cell["selectors"]["kv"] == "f16"
            for cell in q38_tp4_depth[1:]
        ))
        tp4_depth_measurement = next(
            measurement
            for measurement in family["series_measurements"]
            if measurement["id"]
            == "q38-autoround-tp4-f16kv-http-context-r1-grade-c"
        )
        tp4_depth_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-b2dd9ce73d-tp4-exact-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(
            [point["x"] for point in tp4_depth_measurement["points"]],
            [cell["active_context_tokens"] for cell in tp4_depth_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["decode_tok_s"] for point in tp4_depth_measurement["points"]],
            [cell["serving_decode_tok_s_99_interval"] for cell in tp4_depth_result["serving_curve"]["cells"]],
        )
        self.assertEqual(
            [point["output_token_ids_sha256"] for point in tp4_depth_measurement["points"]],
            [cell["output_token_ids_sha256"] for cell in tp4_depth_result["serving_curve"]["cells"]],
        )
        self.assertNotIn(0, [point["x"] for point in tp4_depth_measurement["points"]])
        self.assertNotIn(
            71.77179128057259,
            [point["decode_tok_s"] for point in tp4_depth_measurement["points"]],
        )
        self.assertNotIn(
            71.82969607434323,
            [point["decode_tok_s"] for point in tp4_depth_measurement["points"]],
        )
        q38_q4km_f16 = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-ggmlorg-q4-k-m-0669b98"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q4km_f16), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q4km_f16],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertEqual(
            q38_q4km_f16[0]["evidence_id"],
            "q38-q4km-tp1-kv-f16-context",
        )
        self.assertIn("raw sweep", q38_q4km_f16[0]["label"])
        self.assertEqual(
            [point["x"] for point in series["q38-q4km-tp1-kv-f16-context"]["points"]],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["evidence_id"]
            == "q38-q4km-tp1-f16kv-http-context-r1-grade-c"
            and cell["packet_id"] == "qwen38-27b-q4km-tp1-b70"
            and "HTTP" in cell["label"]
            and "Grade C" in cell["label"]
            for cell in q38_q4km_f16[1:]
        ))
        q38_q4km_f16_series = series[
            "q38-q4km-tp1-f16kv-http-context-r1-grade-c"
        ]
        q38_q4km_http_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4km-tp1-http-depth-r1-result.json"
        ).read_text())
        self.assertEqual(q38_q4km_http_result["status"], "passed")
        self.assertEqual(
            q38_q4km_http_result["exact_depth_http"]["evidence_grade"],
            "C synthetic repeated-token fixture; exact context shape, not representative natural prose",
        )
        self.assertEqual(
            [point["x"] for point in q38_q4km_f16_series["points"]],
            [
                point["active_context_tokens"]
                for point in q38_q4km_http_result["exact_depth_http"]["points"]
            ],
        )
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q4km_f16_series["points"]],
            [
                point["decode_tok_s"]
                for point in q38_q4km_http_result["exact_depth_http"]["points"]
            ],
        )
        self.assertEqual(
            [point["ttft_ms"] for point in q38_q4km_f16_series["points"]],
            [
                point["ttft_ms"]
                for point in q38_q4km_http_result["exact_depth_http"]["points"]
            ],
        )
        self.assertEqual(
            q38_q4km_http_result["realistic_http"]["registered_output_hashes_exact"],
            12,
        )
        self.assertTrue(q38_q4km_http_result["realistic_http"]["cached_tokens_zero"])
        self.assertIn("Separately", q38_q4km_f16_series["quality"])
        self.assertIn("x=0 selector remains", q38_q4km_f16_series["caveat"])

        q38_q4km_q8 = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-ggmlorg-q4-k-m-0669b98"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "q8_0"
        ]
        self.assertEqual(len(q38_q4km_q8), 7)
        self.assertTrue(all(
            cell["evidence_id"] == "q38-q4km-tp1-kv-q8-context"
            and "raw sweep" in cell["label"]
            for cell in q38_q4km_q8
        ))

        q38_q4km_view = next(
            view for view in family["views"] if view["id"] == "context-kv"
        )
        self.assertEqual(q38_q4km_view["metrics"], ["decode_tok_s"])
        self.assertEqual(
            [item["measurement_ids"] for item in q38_q4km_view["series"]],
            [
                ["q38-q4km-tp1-f16kv-http-context-r1-grade-c"],
                ["q38-q4km-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"],
                ["q38-q4km-tp1-kv-q8-context"],
            ],
        )
        self.assertIn("graph-off F16 is Grade C", q38_q4km_view["subtitle"])
        self.assertIn("exact cache64 graph-patched F16 covers 0-32K", q38_q4km_view["subtitle"])
        self.assertIn("Q8_0 remains the preserved raw-engine graph-off curve", q38_q4km_view["subtitle"])

        q38_q8_f16 = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-ggmlorg-q8-0-0669b98"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q8_f16), 7)
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q8weights-tp1-f16kv-target-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q8weights-f16kv-target-http-depth-grade-c"
            and "HTTP" in cell["label"]
            and "Grade C" in cell["label"]
            for cell in q38_q8_f16
        ))
        q38_q8_f16_series = series[
            "q38-q8weights-tp1-f16kv-target-http-context-r1-grade-c"
        ]
        q38_q8_f16_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(q38_q8_f16_result["status"], "passed")
        self.assertEqual(q38_q8_f16_result["serving_curve"]["evidence_grade"], "C")
        self.assertEqual(
            [
                (point["x"], point["decode_tok_s"], point["cached_tokens"],
                 point["output_token_ids_sha256"])
                for point in q38_q8_f16_series["points"]
            ],
            [
                (cell["active_context_tokens"],
                 cell["serving_decode_tok_s_99_interval"],
                 cell["cached_tokens"], cell["output_token_ids_sha256"])
                for cell in q38_q8_f16_result["serving_curve"]["cells"]
            ],
        )
        self.assertTrue(q38_q8_f16_result["quality"]["pass_all"])
        self.assertEqual(
            q38_q8_f16_result["quality"]["cache_zero_requests"],
            {"passed": 10, "required": 10},
        )
        self.assertEqual(q38_q8_f16_series["config"]["mtp"], 0)
        self.assertEqual(q38_q8_f16_series["config"]["graph_mode"], "off")
        self.assertEqual(q38_q8_f16_series["config"]["fit"], "off")
        self.assertEqual(q38_q8_f16_series["config"]["kv"], "f16")
        self.assertTrue(
            q38_q8_f16_result["authority"][
                "site_target_only_q8weights_f16_curve_publication"
            ]
        )
        self.assertFalse(
            q38_q8_f16_result["authority"]["protected_or_headline_replacement"]
        )
        q38_q8_f16_packet = next(
            packet for packet in family["packets"]
            if packet["id"]
            == "qwen38-27b-q8weights-f16kv-target-http-depth-grade-c"
        )
        self.assertEqual(q38_q8_f16_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q8_f16_packet)

        q38_q8_f16_graph = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"] == "qwen38-27b-ggmlorg-q8-0-0669b98"
            and cell["selectors"]["graph_mode"] == "SYCL"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q8_f16_graph), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q8_f16_graph],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"] == "q38-q8weights-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"
            and cell["packet_id"] == "qwen38-27b-q8weights-f16kv-sycl-graph-cache64-depth-grade-c"
            for cell in q38_q8_f16_graph
        ))
        q38_q8_f16_graph_series = series[
            "q38-q8weights-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"
        ]
        q38_q8_f16_graph_result = json.loads((
            MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(
            [(point["x"], point["decode_tok_s"], point["output_token_ids_sha256"]) for point in q38_q8_f16_graph_series["points"]],
            [(cell["active_context_tokens"], cell["serving_decode_tok_s_99_interval"], cell["output_token_ids_sha256"]) for cell in q38_q8_f16_graph_result["serving_curve"]["cells"]],
        )
        self.assertTrue(q38_q8_f16_graph_result["quality"]["pass_all"])
        self.assertEqual(q38_q8_f16_graph_result["graph_mechanism"]["direct_replay"], 947)
        self.assertEqual(q38_q8_f16_graph_result["validation"]["terminal_checks_passed"], 19)
        self.assertFalse(q38_q8_f16_graph_result["authority"]["protected_or_headline_replacement"])
        self.assertIn("can be slower", q38_q8_f16_graph_result["comparison_disclosure"])
        q38_q8_f16_graph_packet = next(
            packet for packet in family["packets"]
            if packet["id"] == "qwen38-27b-q8weights-f16kv-sycl-graph-cache64-depth-grade-c"
        )
        self.assertEqual(q38_q8_f16_graph_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q8_f16_graph_packet)

        q38_q8_graph_q8kv = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-ggmlorg-q8-0-0669b98"
            and cell["selectors"]["graph_mode"] == "SYCL"
            and cell["selectors"]["kv"] == "q8_0"
        ]
        self.assertEqual(len(q38_q8_graph_q8kv), 7)
        closed_graph_q8kv = [
            cell for cell in q38_q8_graph_q8kv if cell["state"] == "closed"
        ]
        self.assertEqual(len(closed_graph_q8kv), 1)
        self.assertEqual(closed_graph_q8kv[0]["selectors"]["active_context_tokens"], 8192)
        self.assertEqual(
            closed_graph_q8kv[0]["packet_id"],
            "qwen38-27b-q8weights-q8kv-sycl-graph-cache64-8k-closed",
        )
        self.assertNotIn("evidence_id", closed_graph_q8kv[0])
        self.assertNotIn("point_x", closed_graph_q8kv[0])
        self.assertTrue(all(
            cell["state"] == "missing"
            for cell in q38_q8_graph_q8kv
            if cell["selectors"]["active_context_tokens"] != 8192
        ))
        q38_q8_graph_q8kv_packet = next(
            packet for packet in family["packets"]
            if packet["id"]
            == "qwen38-27b-q8weights-q8kv-sycl-graph-cache64-8k-closed"
        )
        self.assertEqual(
            q38_q8_graph_q8kv_packet["status"],
            "closed-bounded-negative-long-quality-crash",
        )
        self.assertNotIn("featured_metric", q38_q8_graph_q8kv_packet)
        self.assertIn("no measured speed", q38_q8_graph_q8kv_packet["coverage"])

        q38_q8_q8 = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-ggmlorg-q8-0-0669b98"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "q8_0"
        ]
        self.assertEqual(len(q38_q8_q8), 7)
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q8weights-tp1-q8kv-target-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q8weights-q8kv-target-http-depth-grade-c"
            and "HTTP" in cell["label"]
            and "Grade C" in cell["label"]
            for cell in q38_q8_q8
        ))
        q38_q8_q8_series = series[
            "q38-q8weights-tp1-q8kv-target-http-context-r1-grade-c"
        ]
        q38_q8_q8_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-q8kv-tp1-target-http-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(q38_q8_q8_result["status"], "passed")
        self.assertEqual(q38_q8_q8_result["serving_curve"]["evidence_grade"], "C")
        self.assertEqual(
            [
                (point["x"], point["decode_tok_s"], point["cached_tokens"],
                 point["output_token_ids_sha256"])
                for point in q38_q8_q8_series["points"]
            ],
            [
                (cell["active_context_tokens"],
                 cell["serving_decode_tok_s_99_interval"],
                 cell["cached_tokens"], cell["output_token_ids_sha256"])
                for cell in q38_q8_q8_result["serving_curve"]["cells"]
            ],
        )
        self.assertTrue(q38_q8_q8_result["quality"]["pass_all"])
        self.assertEqual(
            q38_q8_q8_result["quality"]["cache_zero_requests"],
            {"passed": 10, "required": 10},
        )
        self.assertEqual(q38_q8_q8_series["config"]["mtp"], 0)
        self.assertEqual(q38_q8_q8_series["config"]["graph_mode"], "off")
        self.assertEqual(q38_q8_q8_series["config"]["fit"], "off")
        self.assertEqual(q38_q8_q8_series["config"]["kv"], "q8_0")
        self.assertTrue(
            q38_q8_q8_result["authority"][
                "site_target_only_q8weights_q8kv_curve_publication"
            ]
        )
        self.assertFalse(
            q38_q8_q8_result["authority"]["protected_or_headline_replacement"]
        )
        q38_q8_q8_packet = next(
            packet for packet in family["packets"]
            if packet["id"]
            == "qwen38-27b-q8weights-q8kv-target-http-depth-grade-c"
        )
        self.assertEqual(q38_q8_q8_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q8_q8_packet)

        self.assertEqual(family["estimates"], [])
        q38_q8_calibration = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-q8kv-tp1-estimator-calibration-r1.json"
        ).read_text())
        self.assertEqual(q38_q8_calibration["summary"]["band_hits"], 0)
        self.assertEqual(q38_q8_calibration["summary"]["band_misses"], 7)
        self.assertTrue(q38_q8_calibration["summary"]["all_actuals_below_lower_band"])
        self.assertEqual(
            [point["actual"] for point in q38_q8_calibration["points"]],
            [point["decode_tok_s"] for point in q38_q8_q8_series["points"]],
        )
        q38_q8_view = next(
            view for view in family["views"]
            if view["id"] == "context-q8weights-http"
        )
        self.assertEqual(q38_q8_view["metrics"], ["decode_tok_s"])
        self.assertEqual(
            [item["measurement_ids"] for item in q38_q8_view["series"]],
            [
                ["q38-q8weights-tp1-f16kv-target-http-context-r1-grade-c"],
                ["q38-q8weights-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"],
                ["q38-q8weights-tp1-q8kv-target-http-context-r1-grade-c"],
            ],
        )
        self.assertIn("can be slower", q38_q8_view["subtitle"])
        self.assertIn("does not replace graph-off", q38_q8_view["subtitle"])

        q38_q5ks_q8_http = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-unsloth-ud-q5-k-s-4ca7207"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "q8_0"
        ]
        self.assertEqual(len(q38_q5ks_q8_http), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q5ks_q8_http],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q5ks-tp1-q8kv-target-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q5ks-q8kv-target-http-depth-grade-c"
            and "HTTP" in cell["label"]
            and "Grade C" in cell["label"]
            for cell in q38_q5ks_q8_http
        ))
        q38_q5ks_http_series = series[
            "q38-q5ks-tp1-q8kv-target-http-context-r1-grade-c"
        ]
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q5ks_http_series["points"]],
            [
                22.485360956826327,
                20.880043911731846,
                19.585282238140003,
                17.50471579785839,
                14.048644681829956,
                11.822951271745719,
                10.214448950905807,
            ],
        )
        self.assertTrue(all(
            point["cached_tokens"] == 0
            for point in q38_q5ks_http_series["points"]
        ))
        self.assertEqual(q38_q5ks_http_series["config"]["mtp"], 0)
        self.assertEqual(q38_q5ks_http_series["config"]["graph_mode"], "off")
        self.assertEqual(q38_q5ks_http_series["config"]["fit"], "off")
        self.assertEqual(q38_q5ks_http_series["config"]["kv"], "q8_0")
        self.assertIn("Full Qwen3.8 quality battery passed", q38_q5ks_http_series["quality"])
        q38_q5ks_http_packet = next(
            packet for packet in family["packets"]
            if packet["id"] == "qwen38-27b-q5ks-q8kv-target-http-depth-grade-c"
        )
        self.assertEqual(q38_q5ks_http_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q5ks_http_packet)
        q38_q5ks_http_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q5ks-q8kv-tp1-target-http-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(q38_q5ks_http_result["status"], "passed")
        self.assertEqual(q38_q5ks_http_result["serving_curve"]["evidence_grade"], "C")
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q5ks_http_series["points"]],
            [
                cell["serving_decode_tok_s_99_interval"]
                for cell in q38_q5ks_http_result["serving_curve"]["cells"]
            ],
        )
        self.assertTrue(q38_q5ks_http_result["quality"]["pass_all"])
        self.assertEqual(
            q38_q5ks_http_result["quality"]["cache_zero_requests"],
            {"passed": 10, "required": 10},
        )
        self.assertTrue(
            q38_q5ks_http_result["authority"]["site_target_only_curve_publication"]
        )
        self.assertEqual(
            q38_q5ks_http_result["authority"]["target_only_serving_curve_cells"], 7
        )
        for forbidden_authority in (
            "speculative_cells",
            "tp2_or_tp4_cells",
            "prefill_cells",
        ):
            self.assertEqual(q38_q5ks_http_result["authority"][forbidden_authority], 0)
        self.assertFalse(
            q38_q5ks_http_result["authority"]["protected_or_headline_replacement"]
        )
        self.assertFalse(q38_q5ks_http_result["authority"]["localmaxxing_submission"])

        q38_q5ks_f16_http = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-unsloth-ud-q5-k-s-4ca7207"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q5ks_f16_http), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q5ks_f16_http],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q5ks-tp1-f16kv-target-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q5ks-f16kv-target-http-depth-grade-c"
            and "HTTP" in cell["label"]
            and "Grade C" in cell["label"]
            for cell in q38_q5ks_f16_http
        ))
        q38_q5ks_f16_series = series[
            "q38-q5ks-tp1-f16kv-target-http-context-r1-grade-c"
        ]
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q5ks_f16_series["points"]],
            [
                22.617348746656774,
                22.072826293347987,
                21.51247483924336,
                20.699622782660835,
                19.116902989029395,
                17.847541304863622,
                16.72668172192112,
            ],
        )
        self.assertTrue(all(
            point["cached_tokens"] == 0
            for point in q38_q5ks_f16_series["points"]
        ))
        self.assertEqual(q38_q5ks_f16_series["config"]["mtp"], 0)
        self.assertEqual(q38_q5ks_f16_series["config"]["graph_mode"], "off")
        self.assertEqual(q38_q5ks_f16_series["config"]["fit"], "off")
        self.assertEqual(q38_q5ks_f16_series["config"]["kv"], "f16")
        self.assertIn("Full Qwen3.8 quality battery passed", q38_q5ks_f16_series["quality"])
        q38_q5ks_f16_packet = next(
            packet for packet in family["packets"]
            if packet["id"] == "qwen38-27b-q5ks-f16kv-target-http-depth-grade-c"
        )
        self.assertEqual(q38_q5ks_f16_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q5ks_f16_packet)
        q38_q5ks_f16_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q5ks-f16kv-tp1-target-http-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(q38_q5ks_f16_result["status"], "passed")
        self.assertEqual(q38_q5ks_f16_result["serving_curve"]["evidence_grade"], "C")
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q5ks_f16_series["points"]],
            [
                cell["serving_decode_tok_s_99_interval"]
                for cell in q38_q5ks_f16_result["serving_curve"]["cells"]
            ],
        )
        self.assertTrue(q38_q5ks_f16_result["quality"]["pass_all"])
        self.assertEqual(
            q38_q5ks_f16_result["quality"]["cache_zero_requests"],
            {"passed": 10, "required": 10},
        )
        self.assertTrue(
            q38_q5ks_f16_result["authority"]["site_target_only_f16_curve_publication"]
        )
        self.assertEqual(
            q38_q5ks_f16_result["authority"]["target_only_f16_serving_curve_cells"], 7
        )
        for forbidden_authority in (
            "q8_kv_cells",
            "speculative_cells",
            "tp2_or_tp4_cells",
            "graph_cells",
            "prefill_cells",
        ):
            self.assertEqual(q38_q5ks_f16_result["authority"][forbidden_authority], 0)
        self.assertFalse(
            q38_q5ks_f16_result["authority"]["protected_or_headline_replacement"]
        )
        self.assertFalse(q38_q5ks_f16_result["authority"]["localmaxxing_submission"])

        q38_q4kxl_f16_http = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-unsloth-ud-q4-k-xl-4ca7207"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q4kxl_f16_http), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q4kxl_f16_http],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q4kxl-tp1-f16kv-target-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q4kxl-f16kv-target-http-depth-grade-c"
            and "HTTP" in cell["label"]
            and "Grade C" in cell["label"]
            for cell in q38_q4kxl_f16_http
        ))
        q38_q4kxl_f16_series = series[
            "q38-q4kxl-tp1-f16kv-target-http-context-r1-grade-c"
        ]
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q4kxl_f16_series["points"]],
            [
                21.826326109162604,
                21.311674949425424,
                20.87064005039118,
                20.01988162715276,
                18.641111109262432,
                17.370272845612092,
                16.387443320790123,
            ],
        )
        self.assertTrue(all(
            point["cached_tokens"] == 0
            for point in q38_q4kxl_f16_series["points"]
        ))
        self.assertEqual(q38_q4kxl_f16_series["config"]["mtp"], 0)
        self.assertEqual(q38_q4kxl_f16_series["config"]["graph_mode"], "off")
        self.assertEqual(q38_q4kxl_f16_series["config"]["fit"], "off")
        self.assertEqual(q38_q4kxl_f16_series["config"]["kv"], "f16")
        self.assertIn(
            "Full Qwen3.8 quality battery passed",
            q38_q4kxl_f16_series["quality"],
        )
        q38_q4kxl_f16_packet = next(
            packet for packet in family["packets"]
            if packet["id"] == "qwen38-27b-q4kxl-f16kv-target-http-depth-grade-c"
        )
        self.assertEqual(q38_q4kxl_f16_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q4kxl_f16_packet)
        q38_q4kxl_f16_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4kxl-f16kv-tp1-target-http-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(q38_q4kxl_f16_result["status"], "passed")
        self.assertEqual(q38_q4kxl_f16_result["serving_curve"]["evidence_grade"], "C")
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q4kxl_f16_series["points"]],
            [
                cell["serving_decode_tok_s_99_interval"]
                for cell in q38_q4kxl_f16_result["serving_curve"]["cells"]
            ],
        )
        self.assertTrue(q38_q4kxl_f16_result["quality"]["pass_all"])
        self.assertEqual(
            q38_q4kxl_f16_result["quality"]["cache_zero_requests"],
            {"passed": 10, "required": 10},
        )
        self.assertTrue(
            q38_q4kxl_f16_result["authority"][
                "site_target_only_f16_curve_publication"
            ]
        )
        self.assertEqual(
            q38_q4kxl_f16_result["authority"][
                "target_only_f16_serving_curve_cells"
            ],
            7,
        )
        for forbidden_authority in (
            "q8_kv_cells",
            "speculative_cells",
            "tp2_or_tp4_cells",
            "graph_cells",
            "prefill_cells",
        ):
            self.assertEqual(
                q38_q4kxl_f16_result["authority"][forbidden_authority], 0
            )
        self.assertFalse(
            q38_q4kxl_f16_result["authority"]["protected_or_headline_replacement"]
        )
        self.assertFalse(
            q38_q4kxl_f16_result["authority"]["localmaxxing_submission"]
        )

        q38_q4kxl_raw_f16 = series["q38-q4kxl-tp1-kv-f16-context"]
        self.assertEqual(len(q38_q4kxl_raw_f16["points"]), 7)
        self.assertEqual(
            q38_q4kxl_raw_f16["evidence"],
            "experiments/qwen38-27b-b70/data/2026-08-22-qwen38-tp1-weight-ladder-sweep.json",
        )
        q38_q4kxl_raw_q8 = series["q38-q4kxl-tp1-kv-q8-context"]
        self.assertEqual(len(q38_q4kxl_raw_q8["points"]), 7)
        self.assertEqual(q38_q4kxl_raw_q8["config"]["kv"], "q8_0")
        self.assertEqual(
            q38_q4kxl_raw_q8["evidence"],
            "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q4kxl-q8-tp1-exact-depth-result.json",
        )

        q38_q4kxl_q8_http = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-unsloth-ud-q4-k-xl-4ca7207"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "q8_0"
        ]
        self.assertEqual(len(q38_q4kxl_q8_http), 7)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in q38_q4kxl_q8_http],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-q4kxl-tp1-q8kv-target-http-context-r1-grade-c"
            and cell["packet_id"]
            == "qwen38-27b-q4kxl-q8kv-target-http-depth-grade-c"
            and "HTTP" in cell["label"]
            and "Grade C" in cell["label"]
            for cell in q38_q4kxl_q8_http
        ))
        q38_q4kxl_q8_series = series[
            "q38-q4kxl-tp1-q8kv-target-http-context-r1-grade-c"
        ]
        q38_q4kxl_q8_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q4kxl-q8kv-tp1-target-http-depth-quality-r1-result.json"
        ).read_text())
        self.assertEqual(q38_q4kxl_q8_result["status"], "passed")
        self.assertEqual(q38_q4kxl_q8_result["serving_curve"]["evidence_grade"], "C")
        self.assertEqual(
            [point["decode_tok_s"] for point in q38_q4kxl_q8_series["points"]],
            [
                cell["serving_decode_tok_s_99_interval"]
                for cell in q38_q4kxl_q8_result["serving_curve"]["cells"]
            ],
        )
        self.assertTrue(all(
            point["cached_tokens"] == 0
            for point in q38_q4kxl_q8_series["points"]
        ))
        self.assertEqual(q38_q4kxl_q8_series["config"]["mtp"], 0)
        self.assertEqual(q38_q4kxl_q8_series["config"]["graph_mode"], "off")
        self.assertEqual(q38_q4kxl_q8_series["config"]["fit"], "off")
        self.assertEqual(q38_q4kxl_q8_series["config"]["kv"], "q8_0")
        self.assertTrue(q38_q4kxl_q8_result["quality"]["pass_all"])
        self.assertEqual(
            q38_q4kxl_q8_result["quality"]["cache_zero_requests"],
            {"passed": 10, "required": 10},
        )
        q38_q4kxl_q8_packet = next(
            packet for packet in family["packets"]
            if packet["id"] == "qwen38-27b-q4kxl-q8kv-target-http-depth-grade-c"
        )
        self.assertEqual(q38_q4kxl_q8_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_q4kxl_q8_packet)
        self.assertTrue(
            q38_q4kxl_q8_result["authority"][
                "site_target_only_q4kxl_q8kv_curve_publication"
            ]
        )
        self.assertEqual(
            q38_q4kxl_q8_result["authority"][
                "target_only_q4kxl_q8kv_serving_curve_cells"
            ],
            7,
        )
        for forbidden_authority in (
            "f16_kv_cells",
            "other_quantization_cells",
            "speculative_cells",
            "tp2_or_tp4_cells",
            "graph_cells",
            "prefill_cells",
        ):
            self.assertEqual(
                q38_q4kxl_q8_result["authority"][forbidden_authority], 0
            )
        self.assertFalse(
            q38_q4kxl_q8_result["authority"]["protected_or_headline_replacement"]
        )
        self.assertFalse(
            q38_q4kxl_q8_result["authority"]["localmaxxing_submission"]
        )

        q38_q4kxl_f16_view = next(
            view for view in family["views"]
            if view["id"] == "context-q4kxl-f16-http"
        )
        self.assertEqual(q38_q4kxl_f16_view["metrics"], ["decode_tok_s"])
        self.assertEqual(
            [item["measurement_ids"] for item in q38_q4kxl_f16_view["series"]],
            [
                ["q38-q4kxl-tp1-f16kv-target-http-context-r1-grade-c"],
                ["q38-q4kxl-tp1-f16kv-sycl-graph-cache64-http-context-r3-grade-c"],
                ["q38-q4kxl-tp1-q8kv-target-http-context-r1-grade-c"],
            ],
        )
        self.assertIn("all full quality batteries passed", q38_q4kxl_f16_view["subtitle"])

        q38_q5ks_view = next(
            view for view in family["views"]
            if view["id"] == "context-flagship-q8"
        )
        self.assertEqual(
            [item["measurement_ids"] for item in q38_q5ks_view["series"]],
            [
                ["q38-q5ks-tp1-f16kv-target-http-context-r1-grade-c"],
                ["q38-q5ks-tp1-f16kv-sycl-graph-cache64-http-context-r1-grade-c"],
                ["q38-q5ks-tp1-q8kv-target-http-context-r1-grade-c"],
            ],
        )
        self.assertEqual(q38_q5ks_view["metrics"], ["decode_tok_s"])
        self.assertIn("profiles remain separately labeled", q38_q5ks_view["subtitle"])

        q38_mtp_cells, _ = MODULE.expand_coverage_contract(
            contracts["qwen38-tp1-llamacpp-sycl-mtp-package-matrix"]
        )
        q38_q5ks_8k_screen = [
            cell for cell in q38_mtp_cells
            if cell["state"] == "lab-screened"
        ]
        self.assertEqual(len(q38_q5ks_8k_screen), 4)
        self.assertEqual(
            [cell["selectors"]["mtp"] for cell in q38_q5ks_8k_screen],
            [1, 2, 3, 4],
        )
        self.assertTrue(all(
            cell["selectors"]["artifact_id"]
            == "qwen38-27b-unsloth-ud-q5-k-s-4ca7207"
            and cell["selectors"]["active_context_tokens"] == 8192
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "q8_0"
            and "divergent" in cell["label"]
            for cell in q38_q5ks_8k_screen
        ))
        q38_screen_packet = next(
            packet for packet in family["packets"]
            if packet["id"] == "qwen38-27b-q5ks-q8kv-external-mtp-8k-grade-c"
        )
        self.assertEqual(q38_screen_packet["grades"]["evidence"]["grade"], "C")
        self.assertNotIn("featured_metric", q38_screen_packet)
        q38_screen_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q5ks-external-q4mtp-q8kv-tp1-route-8k-sentinel-r1-result.json"
        ).read_text())
        self.assertEqual(
            q38_screen_result["divergence"]["first_zero_based_token_index"], 6
        )
        self.assertFalse(q38_screen_result["authority"]["speed_claim"])

        q38_vllm_target, _ = MODULE.expand_coverage_contract(
            contracts["qwen38-tp1-vllm-xpu-target-matrix"]
        )
        official_fp8_eager = [
            cell for cell in q38_vllm_target
            if cell.get("evidence_id")
            == "q38-official-fp8-tp1-f16kv-eager-http-context-r2-grade-c"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in official_fp8_eager],
            [2048, 4096, 8192],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["selectors"]["artifact_id"]
            == "qwen38-27b-official-fp8-017b9c7"
            and cell["selectors"]["tp"] == 1
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
            and cell["packet_id"]
            == "qwen38-27b-official-fp8-tp1-eager-depth-grade-c"
            for cell in official_fp8_eager
        ))
        official_fp8_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-fp8-tp1-fit-depth-r2-result.json"
        ).read_text())
        official_fp8_measurement = series[
            "q38-official-fp8-tp1-f16kv-eager-http-context-r2-grade-c"
        ]
        self.assertEqual(
            [point["decode_tok_s"] for point in official_fp8_measurement["points"]],
            [cell["decode_tok_s"] for cell in official_fp8_result["cells"]],
        )
        self.assertFalse(
            official_fp8_result["authority"]["headline_or_protected_replacement"]
        )
        self.assertEqual(
            official_fp8_result["authority"]["protected_decode_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        official_fp8_tp4_cells, errors = MODULE.expand_coverage_contract(
            contracts["qwen38-tp4-vllm-xpu-fp8-http-depth"]
        )
        self.assertEqual(errors, [])
        self.assertEqual(official_fp8_tp4_cells[0]["state"], "missing")
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in official_fp8_tp4_cells[1:]],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["evidence_id"]
            == "q38-official-fp8-tp4-f16kv-http-context-r1-grade-c"
            and cell["selectors"]["tp"] == 4
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "PIECEWISE"
            and cell["selectors"]["kv"] == "f16"
            for cell in official_fp8_tp4_cells[1:]
        ))
        official_fp8_tp4_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-fp8-tp4-http-depth-r1-result.json"
        ).read_text())
        official_fp8_tp4_measurement = series[
            "q38-official-fp8-tp4-f16kv-http-context-r1-grade-c"
        ]
        self.assertEqual(
            [point["decode_tok_s"] for point in official_fp8_tp4_measurement["points"]],
            [point["decode_tok_s"] for point in official_fp8_tp4_result["points"]],
        )
        self.assertFalse(
            official_fp8_tp4_result["authority"]["headline_or_protected_replacement"]
        )

        rendered = MODULE.family_page(family)
        overview = re.search(
            r'<section class="contract-overview".*?</section>',
            rendered,
            re.DOTALL,
        )
        self.assertIsNotNone(overview)
        overview_html = overview.group(0)
        self.assertIn("Coverage · 32 matrices", overview_html)
        self.assertIn("597/2,022 classified", overview_html)
        for state, count, word in (
            ("lab-measured", "378", "measured"),
            ("lab-screened", "35", "screened"),
            ("quarantined", "117", "quarantined"),
            ("closed", "9", "closed"),
            ("unsupported", "58", "unsupported"),
            ("missing", "1,425", "missing"),
        ):
            self.assertIn(f'class="is-{state}"><b>{count}</b> {word}', overview_html)
        self.assertNotIn('class="is-estimated"', overview_html)

        self.assertEqual(
            family["initial_view_ids"],
            ["tp-phase", "mtp-nightly-tp1", "context-kv", "context-quant"],
        )
        initial_html, deferred_html = rendered.split(
            '<details class="more-views">', maxsplit=1
        )
        self.assertEqual(initial_html.count('data-family-view="'), 4)
        for view_id in family["initial_view_ids"]:
            self.assertIn(f'data-family-view="{view_id}"', initial_html)
            self.assertNotIn(f'data-family-view="{view_id}"', deferred_html)
        self.assertIn("33 more evidence views", deferred_html)
        self.assertEqual(deferred_html.count('data-family-view="'), 33)
        self.assertIn("Q4_K_M HTTP context × KV/graph", initial_html)
        self.assertIn("value=26.7217226139707 tok/s", initial_html)
        self.assertIn("value=23.221668353050664 tok/s", initial_html)
        self.assertIn("SYCL graph cache64", initial_html)
        self.assertIn(
            'data-family-view="context-q4kxl-f16-http"',
            deferred_html,
        )
        self.assertIn("value=23.20717810276497 tok/s", deferred_html)
        self.assertIn("value=20.3516257692428 tok/s", deferred_html)
        self.assertIn("SYCL graph cache64", deferred_html)
        self.assertIn("Q5_K_S HTTP context × KV/graph", deferred_html)
        self.assertIn("value=23.98574798250926 tok/s", deferred_html)
        self.assertIn("value=21.023067722865875 tok/s", deferred_html)
        self.assertIn("Q8_0-weight HTTP context × KV/graph", deferred_html)
        self.assertIn("value=19.167301559287175 tok/s", deferred_html)
        self.assertIn("value=17.521196458119796 tok/s", deferred_html)
        self.assertIn(
            'data-family-view="q38-q5ks-q8kv-mtp-8k-grade-c"',
            deferred_html,
        )
        self.assertIn(
            'data-family-view="context-q38-tp4-autoround-http"',
            deferred_html,
        )
        self.assertIn(
            'data-family-view="context-q38-tp1-autoround-graphmodes"',
            deferred_html,
        )
        self.assertIn("Qwen3.8 AutoRound TP1 graph modes", deferred_html)
        self.assertIn("value=11.919327130453762 tok/s", deferred_html)
        self.assertIn("value=30.075429359128265 tok/s", deferred_html)
        self.assertIn('data-family-view="context-q38-tp1-autoround-eager-kv"', deferred_html)
        self.assertIn("Qwen3.8 AutoRound TP1 current-image KV/graph", deferred_html)
        self.assertIn("value=12.106811568755516 tok/s", deferred_html)
        self.assertIn("value=12.157390534237836 tok/s", deferred_html)
        self.assertIn("value=29.763525310023436 tok/s", deferred_html)
        self.assertIn("value=26.782574825882012 tok/s", deferred_html)
        self.assertIn('data-family-view="context-q38-tp1-autoround-mtp4-screened"', deferred_html)
        self.assertIn("Qwen3.8 AutoRound TP1 eager MTP4 screened depth", deferred_html)
        self.assertIn("value=14.850597409841217 tok/s", deferred_html)
        self.assertIn("value=13.116686989341177 tok/s", deferred_html)
        self.assertIn('data-family-view="context-q38-tp1-autoround-mtp3-partial"', deferred_html)
        self.assertIn("Qwen3.8 AutoRound TP1 eager MTP3 partial depth", deferred_html)
        self.assertIn("value=13.250527400483348 tok/s", deferred_html)
        self.assertIn("value=11.165397459018312 tok/s", deferred_html)
        self.assertIn('data-family-view="context-q38-tp1-autoround-mtp2-partial"', deferred_html)
        self.assertIn("Qwen3.8 AutoRound TP1 MTP2 depth", deferred_html)
        self.assertIn("value=11.394116870048126 tok/s", deferred_html)
        self.assertIn("value=9.789228307267285 tok/s", deferred_html)
        self.assertIn('data-family-view="context-q38-tp1-autoround-mtp1-partial"', deferred_html)
        self.assertIn("Qwen3.8 AutoRound TP1 MTP1 depth", deferred_html)
        self.assertIn("value=8.309260103763794 tok/s", deferred_html)
        self.assertIn("value=7.72237631436256 tok/s", deferred_html)
        e4m3_curve = next(
            item for item in family["series_measurements"]
            if item["id"] == "q38-f01e-autoround-tp1-eager-e4m3kv-exact-context-r1"
        )
        self.assertEqual(e4m3_curve["config"]["kv"], "fp8_e4m3")
        self.assertEqual(
            [point["x"] for point in e4m3_curve["points"]],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertEqual(
            [point["decode_tok_s"] for point in e4m3_curve["points"]],
            [12.106811568755516, 11.986857838637341, 12.085894881224178,
             12.178365844454287, 12.15958526221534, 12.157390534237836],
        )
        e4m3_piecewise_curve = next(
            item for item in family["series_measurements"]
            if item["id"] == "q38-f01e-autoround-tp1-piecewise-e4m3kv-exact-context-r1"
        )
        self.assertEqual(e4m3_piecewise_curve["config"]["graph_mode"], "PIECEWISE")
        self.assertEqual(e4m3_piecewise_curve["config"]["kv"], "fp8_e4m3")
        self.assertEqual(
            [point["decode_tok_s"] for point in e4m3_piecewise_curve["points"]],
            [29.763525310023436, 28.9442310610282, 28.663718207928127,
             28.028757083522407, 27.319292359315934, 26.782574825882012],
        )
        q38_target_contract = next(
            item for item in family["coverage_contracts"]
            if item["id"] == "qwen38-tp1-vllm-xpu-target-matrix"
        )
        e4m3_rule = next(
            rule for rule in q38_target_contract["rules"]
            if rule["id"] == "measured-f01e-autoround-eager-e4m3kv-exact-8k"
        )
        self.assertEqual(e4m3_rule["label"], "D12.09 · E4M3 KV · Grade C")
        self.assertEqual(e4m3_rule["match"]["active_context_tokens"], 8192)
        e4m3_piecewise_cells = [
            cell for cell in q38_vllm_target
            if cell.get("evidence_id")
            == "q38-f01e-autoround-tp1-piecewise-e4m3kv-exact-context-r1"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in e4m3_piecewise_cells],
            [2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["selectors"]["tp"] == 1
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "PIECEWISE"
            and cell["selectors"]["kv"] == "fp8_e4m3"
            for cell in e4m3_piecewise_cells
        ))
        current_e5m2_evidence = (
            "experiments/qwen38-27b-b70/data/"
            "2026-08-26-qwen38-official-f01e-autoround-tp1-e5m2kv-init-canary-r1-result.json"
        )
        current_e5m2_cells = [
            cell for cell in q38_vllm_target
            if cell.get("evidence") == current_e5m2_evidence
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in current_e5m2_cells],
            [0, 2048, 4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "unsupported"
            and cell["selectors"]["artifact_id"]
            == "qwen38-27b-autoround-w4a16-bce40ca"
            and cell["selectors"]["tp"] == 1
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "fp8_e5m2"
            for cell in current_e5m2_cells
        ))
        e5m2_closures = [
            closure for closure in family["family_closures"]
            if closure["selectors"].get("artifact_id")
            == "qwen38-27b-autoround-w4a16-bce40ca"
            and closure["selectors"].get("kv") == "fp8_e5m2"
        ]
        self.assertEqual(
            {closure["selectors"]["runtime"] for closure in e5m2_closures},
            {
                "vLLM XPU nightly e9d1398d9",
                "vLLM XPU 0.27.2rc1.dev77+gac7509e2b",
            },
        )
        q38_mtp_cells, errors = MODULE.expand_coverage_contract(
            contracts["qwen38-tp1-vllm-xpu-autoround-mtp-matrix"]
        )
        self.assertEqual(errors, [])
        mtp3_measured = [
            cell for cell in q38_mtp_cells
            if cell.get("evidence_id")
            == "q38-f01e-autoround-tp1-mtp3-eager-f16-exact-context-r1-grade-d"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in mtp3_measured],
            [4096, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["selectors"]["mtp"] == 3
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
            for cell in mtp3_measured
        ))
        mtp3_2k = next(
            cell for cell in q38_mtp_cells
            if cell["selectors"]["mtp"] == 3
            and cell["selectors"]["active_context_tokens"] == 2048
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        )
        self.assertEqual(mtp3_2k["state"], "quarantined")
        self.assertIn("token-90 divergence", mtp3_2k["label"])
        mtp3_x0 = next(
            cell for cell in q38_mtp_cells
            if cell["selectors"]["mtp"] == 3
            and cell["selectors"]["active_context_tokens"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        )
        self.assertEqual(mtp3_x0["state"], "missing")
        mtp3_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp3-f16-eager-depth-expansion-r1-result.json"
        ).read_text())
        self.assertEqual(
            mtp3_result["metric_definition"]["published_decode_field"],
            "conventional_99_interval_tok_s",
        )
        self.assertTrue(
            mtp3_result["adjudication"]["whole_arm_fail_closed_receipt_preserved"]
        )
        self.assertFalse(
            mtp3_result["adjudication"]["automatic_publication_authority"]
        )
        self.assertEqual(
            mtp3_result["authority"]["protected_decode_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        mtp2_measured = [
            cell for cell in q38_mtp_cells
            if cell.get("evidence_id")
            == "q38-f01e-autoround-tp1-mtp2-eager-f16-exact-context-r1-grade-d"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in mtp2_measured],
            [4096, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["selectors"]["mtp"] == 2
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
            for cell in mtp2_measured
        ))
        mtp2_quarantined = [
            cell for cell in q38_mtp_cells
            if cell["selectors"]["mtp"] == 2
            and cell["selectors"]["active_context_tokens"] in (2048, 8192, 16384)
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in mtp2_quarantined],
            [2048, 8192, 16384],
        )
        self.assertTrue(all(cell["state"] == "quarantined" for cell in mtp2_quarantined))
        self.assertEqual(
            [cell["label"].split(" divergence", 1)[0] for cell in mtp2_quarantined],
            ["MTP2 token-90", "MTP2 token-99", "MTP2 token-32"],
        )
        mtp2_x0 = next(
            cell for cell in q38_mtp_cells
            if cell["selectors"]["mtp"] == 2
            and cell["selectors"]["active_context_tokens"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        )
        self.assertEqual(mtp2_x0["state"], "missing")
        mtp2_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp2-f16-eager-depth-expansion-r1-result.json"
        ).read_text())
        self.assertEqual(
            mtp2_result["adjudication"]["measured_depths"],
            [4096, 24576, 32768],
        )
        self.assertEqual(
            mtp2_result["adjudication"]["quarantined_depths"],
            [2048, 8192, 16384],
        )
        self.assertTrue(
            mtp2_result["adjudication"]["whole_arm_fail_closed_receipt_preserved"]
        )
        self.assertFalse(
            mtp2_result["adjudication"]["automatic_publication_authority"]
        )
        self.assertEqual(
            mtp2_result["authority"]["protected_decode_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        mtp1_measured = [
            cell for cell in q38_mtp_cells
            if cell.get("evidence_id")
            == "q38-f01e-autoround-tp1-mtp1-eager-f16-exact-context-r1-grade-d"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in mtp1_measured],
            [4096, 16384, 24576, 32768],
        )
        self.assertTrue(all(
            cell["state"] == "lab-measured"
            and cell["selectors"]["mtp"] == 1
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
            for cell in mtp1_measured
        ))
        mtp1_quarantined = [
            cell for cell in q38_mtp_cells
            if cell["selectors"]["mtp"] == 1
            and cell["selectors"]["active_context_tokens"] in (2048, 8192)
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in mtp1_quarantined],
            [2048, 8192],
        )
        self.assertTrue(all(cell["state"] == "quarantined" for cell in mtp1_quarantined))
        self.assertEqual(
            [cell["label"].split(" divergence", 1)[0] for cell in mtp1_quarantined],
            ["MTP1 token-90", "MTP1 token-99"],
        )
        mtp1_x0 = next(
            cell for cell in q38_mtp_cells
            if cell["selectors"]["mtp"] == 1
            and cell["selectors"]["active_context_tokens"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        )
        self.assertEqual(mtp1_x0["state"], "missing")
        mtp1_result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-eager-depth-expansion-r1-result.json"
        ).read_text())
        self.assertEqual(
            mtp1_result["adjudication"]["measured_depths"],
            [4096, 16384, 24576, 32768],
        )
        self.assertEqual(
            mtp1_result["adjudication"]["quarantined_depths"],
            [2048, 8192],
        )
        self.assertTrue(
            mtp1_result["adjudication"]["whole_arm_fail_closed_receipt_preserved"]
        )
        self.assertFalse(
            mtp1_result["adjudication"]["automatic_publication_authority"]
        )
        self.assertEqual(
            mtp1_result["authority"]["protected_decode_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        self.assertIn("Qwen3.8 AutoRound TP1/TP2/TP4 HTTP context", deferred_html)
        self.assertIn("value=48.15370845841339 tok/s", deferred_html)
        self.assertIn("value=42.33933781431878 tok/s", deferred_html)
        self.assertIn("value=71.16806401683698 tok/s", deferred_html)
        self.assertIn("value=66.64506545273888 tok/s", deferred_html)
        for speed in (
            "9.645823300859325",
            "10.041573627140547",
            "10.108015740743388",
            "10.12371796916948",
            "10.146000927730311",
            "10.201853504519782",
        ):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn(
            "2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-r1-result.json",
            deferred_html,
        )
        for speed in (
            "11.882449351158243",
            "14.954312648942505",
            "15.224524397869173",
            "13.775393901663984",
            "13.73875750222011",
            "13.917174301942318",
        ):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn(
            "2026-08-26-qwen38-official-f01e-autoround-tp2-mtp1-f16-eager-depth-expansion-r1-result.json",
            deferred_html,
        )
        for speed in (
            "20.36405574066059",
            "20.893715666020707",
            "18.289177744392617",
            "17.759261196319386",
            "17.695971649981892",
        ):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertNotIn("value=15.164533961949013 tok/s", deferred_html)
        self.assertIn(
            "2026-08-26-qwen38-official-f01e-autoround-tp2-mtp2-f16-eager-depth-expansion-r1-result.json",
            deferred_html,
        )
        for speed in (
            "19.08418591204264",
            "25.11756608538104",
            "20.279538044061752",
            "20.171481912081873",
            "20.15867375927568",
        ):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn(
            "2026-08-26-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1-result.json",
            deferred_html,
        )
        self.assertIn("value=9.647242826428695 tok/s", deferred_html)
        for speed in (
            "9.826154819323886",
            "10.052904972149483",
            "10.256704369059573",
            "10.167773834875007",
            "10.211861327963087",
        ):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn(
            "2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-depth-expansion-r1-result.json",
            deferred_html,
        )
        self.assertIn("value=13.709857016920843 tok/s", deferred_html)
        for speed in ("15.95655387676916", "15.123559550284519", "14.875095826227048", "14.76509277001119"):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn("2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-depth-expansion-r1-result.json", deferred_html)
        self.assertIn("value=18.078249787896656 tok/s", deferred_html)
        for speed in ("21.84394988019745", "19.742270729856283", "19.43634821450176", "19.395239463676972"):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn("2026-08-26-qwen38-official-f01e-autoround-tp4-mtp2-f16-eager-depth-expansion-r1-result.json", deferred_html)
        self.assertIn("value=21.07719065875979 tok/s", deferred_html)
        for speed in ("25.32029890389375", "21.94480318748083", "22.088928026399238", "22.54837762623632"):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn("2026-08-26-qwen38-official-f01e-autoround-tp4-mtp3-f16-eager-depth-expansion-r1-result.json", deferred_html)
        for speed in ("21.97463738631815", "23.789706915057792", "25.753606722449813"):
            self.assertIn(f"value={speed} tok/s", deferred_html)
        self.assertIn("2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1-result.json", deferred_html)
        tp_scale_view = next(
            view for view in family["views"]
            if view["id"] == "context-q38-tp4-autoround-http"
        )
        self.assertEqual(
            [item["measurement_ids"] for item in tp_scale_view["series"]],
            [
                ["q38-b2dd-tp1-graph-f16-exact-context"],
                ["q38-autoround-tp2-f16kv-http-context-r1-grade-c"],
                ["q38-f01e-autoround-tp2-eager-f16-exact-context-r1-grade-c"],
                ["q38-f01e-autoround-tp2-mtp1-eager-f16-exact-context-r1-grade-c"],
                ["q38-f01e-autoround-tp2-mtp2-eager-f16-exact-context-r1-grade-c"],
                ["q38-f01e-autoround-tp2-mtp3-eager-f16-exact-context-r1-grade-c"],
                ["q38-autoround-tp4-f16kv-http-context-r1-grade-c"],
                ["q38-f01e-autoround-tp4-eager-f16-exact-8k-r1-grade-c"],
                ["q38-f01e-autoround-tp4-eager-f16-exact-context-expansion-r1-grade-c"],
                ["q38-f01e-autoround-tp4-piecewise-f16-exact-context-r1-grade-c"],
                ["q38-f01e-autoround-tp4-mtp1-eager-f16-exact-8k-r1-grade-c"],
                ["q38-f01e-autoround-tp4-mtp1-eager-f16-exact-context-expansion-r1-grade-c"],
                ["q38-f01e-autoround-tp4-mtp2-eager-f16-exact-8k-r1-grade-c"],
                ["q38-f01e-autoround-tp4-mtp2-eager-f16-exact-context-expansion-r1-grade-c"],
                ["q38-f01e-autoround-tp4-mtp3-eager-f16-exact-8k-r1-grade-c"],
                ["q38-f01e-autoround-tp4-mtp3-eager-f16-exact-context-expansion-r1-grade-c"],
                ["q38-f01e-autoround-tp4-mtp4-eager-f16-quality-recovery-r1-grade-c"],
            ],
        )
        self.assertIn(
            'data-family-view="context-q36-mtpq8-q8kv-http-grade-c"',
            deferred_html,
        )
        self.assertIn("◇ screened, experimental", deferred_html)

        q36_context_view = next(
            view for view in family["views"]
            if view["id"] == "context-q36-quant-kv"
        )
        self.assertEqual(
            [series["measurement_ids"] for series in q36_context_view["series"]],
            [
                ["q36-q4km-tp1-kv-f16-context"],
                ["q36-q4km-tp1-kv-q8-context"],
                ["q36-q4kxl-tp1-kv-f16-context"],
                ["q36-q4kxl-tp1-kv-q8-context"],
                ["q36-q4-0-tp1-kv-f16-context"],
                ["q36-q4-0-tp1-kv-q8-context"],
                ["q36-mtpq8-tp1-kv-f16-context"],
                ["q36-mtpq8-tp1-kv-q8-context"],
                ["q36-unsloth-q8-tp1-kv-f16-context"],
                ["q36-unsloth-q8-tp1-kv-q8-context"],
            ],
        )
        self.assertIn('data-family-view="context-q36-quant-kv"', rendered)
        self.assertIn("Q4_K_M · f16 KV", rendered)
        self.assertIn("value=29.30276 tok/s", rendered)
        self.assertIn("value=655.10387 tok/s", rendered)
        self.assertIn("value=28.427444 tok/s", rendered)
        self.assertIn("value=648.263152 tok/s", rendered)
        self.assertIn("value=28.204518 tok/s", rendered)
        self.assertIn("value=654.617886 tok/s", rendered)
        self.assertIn("value=27.395786 tok/s", rendered)
        self.assertIn("value=645.980903 tok/s", rendered)
        self.assertIn("value=26.403242 tok/s", rendered)
        self.assertIn("value=144.909151 tok/s", rendered)
        self.assertIn("value=25.872387 tok/s", rendered)
        self.assertIn("value=144.957372 tok/s", rendered)
        self.assertIn("Q8_0 embedded-MTP artifact · f16 KV", rendered)
        self.assertIn("value=19.834912 tok/s", rendered)
        self.assertIn("value=658.014356 tok/s", rendered)
        self.assertIn("Q8_0 embedded-MTP artifact · q8_0 KV", rendered)
        self.assertIn("value=19.405539 tok/s", rendered)
        self.assertIn("value=653.030632 tok/s", rendered)
        self.assertIn("Q8_0 target-only Unsloth · f16 KV", rendered)
        self.assertIn("value=19.837968 tok/s", rendered)
        self.assertIn("value=660.84773 tok/s", rendered)
        self.assertIn("Q8_0 target-only Unsloth · q8_0 KV", rendered)
        self.assertIn("value=19.405005 tok/s", rendered)
        self.assertIn("value=653.732827 tok/s", rendered)

        unknown_speculator = deepcopy(family)
        next(
            contract
            for contract in unknown_speculator["coverage_contracts"]
            if contract["id"] == "qwen38-tp1-llamacpp-sycl-mtp-package-matrix"
        )["fixed_selectors"]["speculator_artifact_id"] = "unknown-speculator"
        self._assert_error(
            self._errors(unknown_speculator),
            "references unknown speculator artifact unknown-speculator",
        )

        target_as_speculator = deepcopy(family)
        next(
            contract
            for contract in target_as_speculator["coverage_contracts"]
            if contract["id"] == "qwen38-tp1-llamacpp-sycl-mtp-package-matrix"
        )["fixed_selectors"]["speculator_artifact_id"] = (
            "qwen38-27b-unsloth-ud-q4-k-xl-4ca7207"
        )
        self._assert_error(
            self._errors(target_as_speculator),
            "is not declared with role=speculator",
        )

        target_only_closure = next(
            closure
            for closure in family["family_closures"]
            if closure["selectors"].get("artifact_id")
            == "qwen36-27b-unsloth-q8-0-82d411a"
            and closure["selectors"].get("mtp") == [1, 2, 3, 4]
        )
        self.assertEqual(target_only_closure["state"], "unsupported")
        self.assertEqual(
            target_only_closure["evidence"],
            "experiments/qwen36-27b-q8-gguf-b70/model-manifest.json",
        )

    def test_packet_fallback_uses_the_highest_curated_packet_claim(self) -> None:
        family = self._family()
        measured_a = family["run_measurements"][0]
        measured_a["metrics"]["decode_tok_s"] = [42.0]
        measured_a["workload"] = "p66/o128 fixed rapid suite"
        measured_a["evidence"] = "https://example.test/research-a.json"
        measured_b = deepcopy(measured_a)
        measured_b["id"] = "measured-b"
        measured_b["metrics"]["decode_tok_s"] = [43.0]
        measured_b["evidence"] = "https://example.test/research-b.json"
        family["run_measurements"].append(measured_b)
        packet_a = self._research_packet()
        packet_b = deepcopy(packet_a)
        packet_b["id"] = "research-b"
        packet_b["label"] = "Research B"
        packet_b["manifest"] = "https://example.test/research-b.json"
        packet_b["featured_metric"].update(
            {
                "measurement_id": "measured-b",
                "value": 43.0,
                "evidence": "https://example.test/research-b.json",
            }
        )
        family["packets"] = [packet_a, packet_b]
        family["primary_packet_id"] = "research-b"

        self.assertEqual(self._errors(family), [])
        entries = MODULE.featured_result_entries(family)
        self.assertEqual([entry["value"] for entry in entries], [43.0, 42.0])
        self.assertEqual([entry["role"] for entry in entries], ["hero", "support"])

    def test_small_stat_views_render_every_metric_without_fake_supersession(self) -> None:
        family = self._family()
        family["run_measurements"][0]["metrics"].update(
            {
                "ttft_ms": [100.0],
                "wall_output_tok_s": [1.2462600034136797],
                "draft_acceptance_rate": [0.61],
                "effective_tokens_per_verification": [2.4],
            }
        )
        family["views"] = [
            {
                "id": "small-complete",
                "title": "Small complete view",
                "subtitle": "All metrics remain visible.",
                "x_label": "draft tokens",
                "discrete": True,
                "metrics": [
                    "decode_tok_s",
                    "wall_output_tok_s",
                    "ttft_ms",
                    "draft_acceptance_rate",
                    "effective_tokens_per_verification",
                ],
                "series": [
                    {
                        "label": "candidate",
                        "measurement_ids": ["measured-a"],
                        "x_from": "config.mtp",
                    }
                ],
            }
        ]
        rendered = MODULE.view_card(family, family["views"][0])
        for expected in ("30–30.2", "1.25", "100", "0.61", "2.4"):
            self.assertIn(expected, rendered)
        self.assertNotIn("superseded", rendered.casefold())
        self.assertNotIn("full quality gate", rendered.casefold())

    def test_svg_points_disclose_unrounded_escaped_values(self) -> None:
        family = self._family()
        family["run_measurements"][0]["metrics"]["decode_tok_s"] = [
            71.45427094575045
        ]
        view = self._measured_view()
        view["series"][0]["label"] = 'Q4 <fast> & "safe"'
        view["x_label"] = "cards <active>"

        svg, _summary = MODULE.chart_svg(
            family, view, "decode_tok_s", True
        )

        self.assertIn("<circle", svg)
        self.assertIn("<title>", svg)
        self.assertIn("Q4 &lt;fast&gt; &amp; &quot;safe&quot;", svg)
        self.assertIn("Decode (decode_tok_s)", svg)
        self.assertIn("cards &lt;active&gt;=1.0", svg)
        self.assertIn("value=71.45427094575045 tok/s", svg)
        self.assertNotIn("Q4 <fast>", svg)

    def test_multimetric_chart_has_complete_no_script_summary_table(self) -> None:
        family = self._family()
        family["series_measurements"] = [
            {
                "id": "measured-depth",
                "state": "lab-measured",
                "revision": "revision-a",
                "variant": "quant-a",
                "runtime": "runtime-a",
                "config": {"mtp": 0, "tp": 1, "graph": "off"},
                "workload": "fixed context sweep",
                "points": [
                    {
                        "x": 1024,
                        "decode_tok_s": 30.1,
                        "prefill_tok_s": 800.1,
                        "ttft_ms": 100.1,
                    },
                    {
                        "x": 2048,
                        "decode_tok_s": 29.2,
                        "prefill_tok_s": 780.2,
                        "ttft_ms": 120.2,
                    },
                    {
                        "x": 4096,
                        "decode_tok_s": 28.3,
                        "prefill_tok_s": 750.3,
                        "ttft_ms": 150.3,
                    },
                ],
                "evidence": "https://example.test/measured-depth.json",
            }
        ]
        view = {
            "id": "all-metrics",
            "title": "All metrics",
            "subtitle": "Static fallback stays complete.",
            "x_label": "context tokens",
            "metrics": ["decode_tok_s", "prefill_tok_s", "ttft_ms"],
            "series": [
                {
                    "label": "candidate",
                    "measurement_ids": ["measured-depth"],
                }
            ],
        }

        rendered = MODULE.view_card(family, view)
        fallback = rendered.split("<noscript>", 1)[1].split("</noscript>", 1)[0]

        self.assertIn('<table class="metric-fallback">', fallback)
        self.assertIn("All measured metric summaries", fallback)
        for label in ("Decode", "Prefill", "TTFT"):
            self.assertIn(f'<th scope="row">{label}</th>', fallback)
        for value in ("30.1", "800.1", "100.1"):
            self.assertIn(value, fallback)
        self.assertNotIn(" hidden", fallback)

    def test_compact_gaps_and_scoped_closures_remain_explicit(self) -> None:
        family = self._family()
        view = family["coverage_views"][0]
        view["rows"] = [0, 1]
        view["cells"]["1:1"] = {
            "state": "missing",
            "label": "not run",
        }
        family["family_closures"] = [
            {
                "selectors": {"revision": "revision-a", "mtp": 4},
                "state": "closed",
                "reason": "Stopped by the declared fit gate.",
                "evidence": "https://example.test/closure.json",
            }
        ]
        coverage = MODULE.coverage_tables(family)
        self.assertIn("1 untested combination", coverage)
        self.assertIn("TP1·MTP1", coverage)
        self.assertNotIn("Stopped by the declared fit gate", coverage)
        rendered = MODULE.family_page(family)
        self.assertIn("the lab has stopped pursuing", rendered)
        self.assertIn("Stopped by the declared fit gate", rendered)  # closure reason in words; selectors live in the family data
        self.assertIn("https://example.test/closure.json", rendered)

    def test_metric_code_legend_renders_for_compact_matrix_values(self) -> None:
        family = json.loads((MODULE.ROOT / "families/laguna-s.json").read_text())
        rendered = MODULE.coverage_tables(family)
        self.assertIn("Codes in the rows: D = decode tok/s", rendered)
        self.assertIn("AR = share of drafted tokens accepted", rendered)

    def test_packet_cta_labels_match_the_actual_target(self) -> None:
        package = {
            "id": "packet-a",
            "manifest": "packages/packet-a/package.json",
        }
        result = {
            "id": "result-a",
            "manifest": "results/result-a/README.md",
        }
        repro = {
            "id": "repro-a",
            "manifest": "repro/repro-a/README.md",
        }
        self.assertEqual(
            MODULE.packet_manifest_target(package),
            ("packet-a.html", "Open deployment packet"),
        )
        href, label = MODULE.packet_manifest_target(result)
        self.assertTrue(href.endswith("results/result-a/README.md"))
        self.assertEqual(label, "Read the lab report")
        self.assertEqual(MODULE.packet_link_kind({}, repro), "guide")
        href, label = MODULE.packet_manifest_target(repro)
        self.assertTrue(href.endswith("repro/repro-a/README.md"))
        self.assertEqual(label, "Open reproduction guide")

    def test_primary_packet_binding_controls_cta_without_speed_ranking(self) -> None:
        family = self._family()
        slower = self._research_packet()
        slower["id"] = "curated-slower"
        slower["featured_metric"]["value"] = 30.0
        faster = deepcopy(slower)
        faster["id"] = "uncurated-faster"
        faster["featured_metric"]["value"] = 300.0
        family["packets"] = [faster, slower]
        family["primary_packet_id"] = "curated-slower"

        self.assertIs(MODULE.preferred_packet(family), slower)

        missing = deepcopy(family)
        del missing["primary_packet_id"]
        self._assert_error(self._errors(missing), "primary_packet_id")

        unknown = deepcopy(family)
        unknown["primary_packet_id"] = "not-a-packet"
        self._assert_error(self._errors(unknown), "primary_packet_id", "missing")

    def test_repro_packet_keeps_reproduction_promise(self) -> None:
        family = self._family()
        measurement = family["run_measurements"][0]
        measurement["metrics"]["decode_tok_s"] = [42.0]
        measurement["workload"] = "p66/o128 fixed rapid suite"
        packet = self._research_packet()
        packet["manifest"] = "repro/repro-a/README.md"
        family["packets"] = [packet]

        rendered = MODULE.packet_cards(family)
        self.assertIn("Reproduce <b>42 tok/s</b>", rendered)
        self.assertNotIn("Measured evidence: <b>42 tok/s</b>", rendered)
        self.assertNotIn("not a step-by-step install guide", rendered)

    def test_report_packet_describes_measured_evidence_not_reproduction(self) -> None:
        family = self._family()
        measurement = family["run_measurements"][0]
        measurement["metrics"]["decode_tok_s"] = [42.0]
        measurement["workload"] = "p66/o128 fixed rapid suite"
        measurement["evidence"] = "https://example.test/research-a.json"
        family["packets"] = [self._research_packet()]

        rendered = MODULE.packet_cards(family)
        self.assertIn("Measured evidence: <b>42 tok/s</b>", rendered)
        self.assertNotIn("Reproduce <b>42 tok/s</b>", rendered)
        self.assertIn("not a step-by-step install guide", rendered)

    def test_local_evidence_cannot_escape_repository(self) -> None:
        for path in ("/etc/passwd", "../outside-evidence.json"):
            with self.subTest(path=path):
                family = self._family()
                family["run_measurements"][0]["evidence"] = path
                self._assert_error(self._errors(family), "evidence")

    def test_all_claim_numerics_are_finite_and_not_boolean(self) -> None:
        cases = []
        for value in (True, math.nan, math.inf, -math.inf):
            measurement = self._family()
            measurement["run_measurements"][0]["metrics"]["decode_tok_s"] = [
                value
            ]
            cases.append((f"measurement sample {value!r}", measurement))

        point_x = self._family()
        point_x["run_measurements"] = []
        point_x["series_measurements"] = [
            {
                "id": "bad-point",
                "state": "lab-measured",
                "revision": "revision-a",
                "variant": "quant-a",
                "runtime": "runtime-a",
                "axis": "active_context_tokens",
                "config": {"tp": 1, "mtp": 0, "graph": "off"},
                "points": [{"x": True, "decode_tok_s": math.inf}],
                "evidence": "https://example.test/bad-point.json",
            }
        ]
        point_x["coverage_views"] = []
        cases.append(("point x/value", point_x))

        estimate = self._family()
        estimate["estimates"] = [self._estimate()]
        estimate["estimates"][0]["value"] = math.nan
        estimate["estimates"][0]["interval"]["low"] = True
        cases.append(("estimate value/interval", estimate))

        featured = self._family()
        featured["run_measurements"][0]["metrics"]["decode_tok_s"] = [42.0]
        featured["run_measurements"][0]["workload"] = "p66/o128 fixed rapid suite"
        featured["run_measurements"][0]["evidence"] = (
            "https://example.test/research-a.json"
        )
        featured["packets"] = [self._research_packet()]
        featured["packets"][0]["featured_metric"]["value"] = True
        cases.append(("featured metric value", featured))

        for name, family in cases:
            with self.subTest(name=name):
                self.assertTrue(
                    self._errors(family), f"non-finite or boolean {name} must fail"
                )

    def test_metric_units_match_the_metric_definition(self) -> None:
        estimate = self._family()
        estimate["estimates"] = [self._estimate()]
        estimate["estimates"][0]["unit"] = "ms"
        self._assert_error(self._errors(estimate), "unit")

        featured = self._family()
        featured["run_measurements"][0]["metrics"]["decode_tok_s"] = [42.0]
        featured["run_measurements"][0]["workload"] = "p66/o128 fixed rapid suite"
        featured["run_measurements"][0]["evidence"] = (
            "https://example.test/research-a.json"
        )
        featured["packets"] = [self._research_packet()]
        featured["packets"][0]["featured_metric"]["unit"] = "ms"
        self._assert_error(self._errors(featured), "unit")

    def test_connected_curve_requires_homogeneous_identity(self) -> None:
        family = self._family()
        second = deepcopy(family["run_measurements"][0])
        second["id"] = "measured-b"
        second["runtime"] = "runtime-b"
        second["config"]["tp"] = 2
        family["run_measurements"].append(second)
        family["views"] = [
            {
                "id": "mixed-runtime",
                "title": "Mixed runtime",
                "metrics": ["decode_tok_s"],
                "series": [
                    {
                        "label": "must not connect",
                        "measurement_ids": ["measured-a", "measured-b"],
                        "x_from": "config.tp",
                    }
                ],
            }
        ]
        self._assert_error(self._errors(family), "runtime")

        discrete = deepcopy(family)
        discrete["views"][0]["discrete"] = True
        self.assertEqual(
            self._errors(discrete), [], "discrete historical points may differ"
        )

    def test_legacy_view_fixed_selectors_also_fail_closed(self) -> None:
        family = self._family()
        family["coverage_views"][0]["fixed_selectors"] = {
            "optimization_overlay_id": "none"
        }
        self._assert_error(
            self._errors(family), "optimization_overlay_id", "measured-a"
        )

    def test_axis_values_cannot_use_ambiguous_colon_encoding(self) -> None:
        family = self._family()
        family["coverage_views"] = [
            {
                "id": "ambiguous-axis",
                "label": "ambiguous",
                "row_axis": {"key": "variant", "label": "Variant"},
                "column_axis": {"key": "tp", "label": "TP", "prefix": "TP"},
                "fixed_selectors": {"revision": "revision-a"},
                "rows": ["quant:variant"],
                "columns": [1],
                "cells": {"quant:variant:1": {"state": "missing"}},
            }
        ]
        self._assert_error(self._errors(family), "axis")

    def test_view_ids_are_unique(self) -> None:
        ordinary = self._family()
        ordinary["coverage_views"] = []
        ordinary["views"] = [
            {"id": "duplicate", "metrics": [], "series": []},
            {"id": "duplicate", "metrics": [], "series": []},
        ]
        self._assert_error(self._errors(ordinary), "duplicate", "view")

        coverage = self._family()
        coverage["coverage_views"].append(deepcopy(coverage["coverage_views"][0]))
        self._assert_error(self._errors(coverage), "duplicate", "coverage")

    def test_initial_view_ids_are_valid_unique_view_references(self) -> None:
        family = self._family()
        family["views"] = [self._measured_view()]
        family["initial_view_ids"] = [family["views"][0]["id"]]
        self.assertEqual(self._errors(family), [])

        duplicate = deepcopy(family)
        duplicate["initial_view_ids"] *= 2
        self._assert_error(self._errors(duplicate), "initial_view_ids", "unique")

        unknown = deepcopy(family)
        unknown["initial_view_ids"] = ["not-a-view"]
        self._assert_error(self._errors(unknown), "initial_view_ids", "unknown")

        empty = deepcopy(family)
        empty["initial_view_ids"] = []
        self._assert_error(self._errors(empty), "initial_view_ids", "non-empty")

    def test_packet_revision_must_resolve_to_family_revision(self) -> None:
        family = self._family()
        family["packets"] = [
            {
                "id": "packet-a",
                "revision": "unknown-revision",
                "manifest": "https://example.test/packet-a.json",
            }
        ]
        self._assert_error(self._errors(family), "revision", "packet-a")

    @staticmethod
    def _research_packet() -> dict[str, object]:
        return {
            "id": "research-a",
            "label": "Research A",
            "revision": "revision-a",
            "cards": 1,
            "status": "research",
            "evidence_level": "bounded",
            "coverage": ["decode"],
            "manifest": "https://example.test/research-a.json",
            "featured_metric": {
                "measurement_id": "measured-a",
                "sample_index": 0,
                "metric": "decode_tok_s",
                "value": 42.0,
                "unit": "tok/s",
                "workload": "p66/o128 fixed rapid suite",
                "evidence": "https://example.test/research-a.json",
            },
            "projection": {
                "model": "research_a",
                "quant": "Q4_K_M",
                "runtime": "llama_cpp",
            },
        }

    def _assert_error(self, errors: list[str], *needles: str) -> None:
        self.assertTrue(errors, f"expected validation error containing {needles!r}")
        lowered = [error.casefold() for error in errors]
        self.assertTrue(
            any(
                all(needle.casefold() in error for needle in needles)
                for error in lowered
            ),
            f"no error contained all of {needles!r}: {errors}",
        )

    def test_q38_current_f01e_tp1_mtp4_is_screened_only_with_speedless_structural_cells(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp1-f01e-mtp4-eager-f16-screened-grade-d"
        measurement_id = "q38-f01e-autoround-tp1-mtp4-eager-f16-screened-context-r1-grade-d"
        contract_id = "qwen38-tp1-vllm-xpu-autoround-f01e-mtp4-eager-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "D")
        self.assertEqual(series[measurement_id]["state"], "lab-screened")
        self.assertEqual(
            [(point["x"], point["decode_tok_s"]) for point in series[measurement_id]["points"]],
            [(4096, 14.850597409841217), (16384, 12.361817762397319), (24576, 13.116686989341177)],
        )

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        self.assertEqual([cell for cell in cells if cell["state"] == "lab-measured"], [])
        screened = [cell for cell in cells if cell["state"] == "lab-screened"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in screened], [4096, 16384, 24576])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in screened))
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in quarantined], [2048, 8192])
        self.assertIn("token-90", quarantined[0]["label"])
        self.assertIn("cross-boot", quarantined[1]["label"])
        self.assertTrue(all("evidence_id" not in cell and "point_x" not in cell for cell in quarantined))
        closed = [cell for cell in cells if cell["state"] == "closed"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in closed], [32768])
        self.assertNotIn("evidence_id", closed[0])
        self.assertNotIn("point_x", closed[0])
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp4-f16-eager-depth-r1-human-adjudication-result.json").read_text())
        self.assertEqual(result["authority"]["lab_screened_speed_cells"], 3)
        self.assertEqual(result["authority"]["lab_measured_cells"], 0)
        self.assertFalse(result["authority"]["headline_or_protected_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])

        rendered = MODULE.family_page(family)
        for speed in ("14.850597409841217", "12.361817762397319", "13.116686989341177"):
            self.assertIn(f"value={speed} tok/s", rendered)
        for unselected_speed in ("12.005765140784916", "15.360198998480438", "15.694764790035633", "12.198861745354137"):
            self.assertNotIn(unselected_speed, rendered)
        view = next(item for item in family["views"] if item["id"] == "context-q38-tp1-autoround-mtp4-screened")
        self.assertEqual(view["series"][0]["measurement_ids"], [measurement_id])

    def test_q38_current_f01e_tp4_mtp4_recovery_adds_three_and_retains_structural_states(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp4-f01e-mtp4-eager-f16-recovery-grade-c"
        measurement_id = "q38-f01e-autoround-tp4-mtp4-eager-f16-quality-recovery-r1-grade-c"
        contract_id = "qwen38-tp4-vllm-xpu-autoround-f01e-mtp4-eager-depth"
        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        self.assertEqual(
            [(point["x"], point["decode_tok_s"]) for point in series[measurement_id]["points"]],
            [(4096, 21.97463738631815), (16384, 23.789706915057792), (24576, 25.753606722449813)],
        )
        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096, 16384, 24576])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in measured))
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in quarantined], [2048, 8192])
        self.assertIn("token-90", quarantined[0]["label"])
        self.assertIn("token-99", quarantined[1]["label"])
        self.assertTrue(all("evidence_id" not in cell and "point_x" not in cell for cell in quarantined))
        closed = [cell for cell in cells if cell["state"] == "closed"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in closed], [32768])
        self.assertNotIn("evidence_id", closed[0])
        self.assertNotIn("point_x", closed[0])
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])
        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1-result.json").read_text())
        self.assertEqual(result["authority"]["new_site_measured_cells"], 3)
        self.assertEqual(result["authority"]["diagnostic_speed_cells"], 0)
        self.assertFalse(result["authority"]["existing_8k_speed_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        rendered = MODULE.family_page(family)
        for speed in ("21.97463738631815", "23.789706915057792", "25.753606722449813"):
            self.assertIn(f"value={speed} tok/s", rendered)
        for diagnostic_speed in (
            "28.645144581715854",
            "18.854008775004846",
            "28.772138902083974",
            "29.914961654037754",
            "23.942660537746576",
            "25.730788439576674",
            "22.793348997720386",
            "22.446312547454145",
            "22.67304297722641",
        ):
            self.assertNotIn(diagnostic_speed, rendered)
        view = next(item for item in family["views"] if item["id"] == "context-q38-tp4-autoround-http")
        self.assertEqual(view["series"][-1]["measurement_ids"], [measurement_id])

    def test_q38_current_f01e_tp4_mtp3_adds_four_and_quarantines_2k(self) -> None:
        family=json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets={x["id"]:x for x in family["packets"]}; series={x["id"]:x for x in family["series_measurements"]}; contracts={x["id"]:x for x in family["coverage_contracts"]}
        packet_id="qwen38-27b-autoround-int4-tp4-f01e-mtp3-eager-f16-8k-grade-c"; measurement_id="q38-f01e-autoround-tp4-mtp3-eager-f16-exact-8k-r1-grade-c"
        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"],"C")
        point=series[measurement_id]["points"][0]; self.assertEqual((point["x"],point["decode_tok_s"],point["accepted_tokens"],point["drafted_tokens"]),(8192,21.07719065875979,89,114))
        cells,errors=MODULE.expand_coverage_contract(contracts["qwen38-tp4-vllm-xpu-autoround-f01e-mtp3-eager-depth"]); self.assertEqual(errors,[]); self.assertEqual(len(cells),7)
        measured=[x for x in cells if x["state"]=="lab-measured"]; self.assertEqual(len(measured),5)
        retained=next(x for x in measured if x["selectors"]["active_context_tokens"]==8192); self.assertEqual(retained["evidence_id"],measurement_id); self.assertEqual(retained["packet_id"],packet_id)
        expansion_id="q38-f01e-autoround-tp4-mtp3-eager-f16-exact-context-expansion-r1-grade-c"; self.assertEqual([x["x"] for x in series[expansion_id]["points"]],[4096,16384,24576,32768])
        self.assertEqual([x["selectors"]["active_context_tokens"] for x in measured if x["evidence_id"]==expansion_id],[4096,16384,24576,32768])
        quarantined=[x for x in cells if x["state"]=="quarantined"]; self.assertEqual(len(quarantined),1); self.assertEqual(quarantined[0]["selectors"]["active_context_tokens"],2048); self.assertNotIn("evidence_id",quarantined[0]); self.assertTrue(quarantined[0]["evidence"].endswith("tp4-mtp3-f16-eager-depth-expansion-r1-result.json"))
        self.assertEqual([x["selectors"]["active_context_tokens"] for x in cells if x["state"]=="missing"],[0])
        result=json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp3-f16-eager-8k-sentinel-r1-result.json").read_text())
        self.assertFalse(result["adjudication"]["raw_automatic_publication_authority"]); self.assertTrue(result["adjudication"]["explicit_human_per_cell_publication_authority"]); self.assertFalse(result["adjudication"]["descendant_expansion_authorized"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"],[71.45427094575045,30.329809361830037,49.05894025767351,71.9001988117144])

    def test_q38_current_f01e_tp4_mtp2_adds_four_and_quarantines_2k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp4-f01e-mtp2-eager-f16-8k-grade-c"
        measurement_id = "q38-f01e-autoround-tp4-mtp2-eager-f16-exact-8k-r1-grade-c"
        contract_id = "qwen38-tp4-vllm-xpu-autoround-f01e-mtp2-eager-depth"
        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["x"], 8192)
        self.assertEqual(points[0]["decode_tok_s"], 18.078249787896656)
        self.assertEqual(points[0]["historical_100_event_decode_tok_s"], 18.260858371612784)
        self.assertEqual((points[0]["accepted_tokens"], points[0]["drafted_tokens"]), (78, 98))
        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual(len(measured), 5)
        retained = next(cell for cell in measured if cell["selectors"]["active_context_tokens"] == 8192)
        self.assertEqual(retained["evidence_id"], measurement_id)
        self.assertEqual(retained["packet_id"], packet_id)
        expansion_id = "q38-f01e-autoround-tp4-mtp2-eager-f16-exact-context-expansion-r1-grade-c"
        expansion = series[expansion_id]
        self.assertEqual([point["x"] for point in expansion["points"]], [4096, 16384, 24576, 32768])
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in measured if cell["evidence_id"] == expansion_id],
            [4096, 16384, 24576, 32768],
        )
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["selectors"]["active_context_tokens"], 2048)
        self.assertNotIn("evidence_id", quarantined[0])
        self.assertTrue(quarantined[0]["evidence"].endswith("tp4-mtp2-f16-eager-depth-expansion-r1-result.json"))
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])
        self.assertTrue(all(cell["selectors"]["tp"] == 4 and cell["selectors"]["mtp"] == 2 and cell["selectors"]["graph_mode"] == "off" and cell["selectors"]["kv"] == "f16" for cell in cells))
        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp2-f16-eager-8k-sentinel-r1-result.json").read_text())
        self.assertFalse(result["adjudication"]["raw_automatic_publication_authority"])
        self.assertTrue(result["adjudication"]["explicit_human_per_cell_publication_authority"])
        self.assertEqual(result["adjudication"]["published_depths"], [8192])
        self.assertFalse(result["adjudication"]["descendant_expansion_authorized"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertEqual(series["q38-autoround-tp4-f16kv-http-context-r1-grade-c"]["points"][2]["decode_tok_s"], 69.8695629973191)

    def test_q38_current_f01e_tp4_mtp1_adds_four_and_quarantines_2k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}

        packet_id = "qwen38-27b-autoround-int4-tp4-f01e-mtp1-eager-f16-8k-grade-c"
        measurement_id = "q38-f01e-autoround-tp4-mtp1-eager-f16-exact-8k-r1-grade-c"
        contract_id = "qwen38-tp4-vllm-xpu-autoround-f01e-mtp1-eager-depth"
        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["x"], 8192)
        self.assertEqual(points[0]["decode_tok_s"], 13.709857016920843)
        self.assertEqual(points[0]["historical_100_event_decode_tok_s"], 13.848340421132164)
        self.assertEqual(points[0]["draft_acceptance_rate"], 0.9242424242424242)
        self.assertEqual((points[0]["accepted_tokens"], points[0]["drafted_tokens"]), (61, 66))

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual(len(measured), 5)
        retained = next(cell for cell in measured if cell["selectors"]["active_context_tokens"] == 8192)
        self.assertEqual(retained["evidence_id"], measurement_id)
        self.assertEqual(retained["packet_id"], packet_id)
        expansion_id = "q38-f01e-autoround-tp4-mtp1-eager-f16-exact-context-expansion-r1-grade-c"
        expansion = series[expansion_id]
        self.assertEqual([point["x"] for point in expansion["points"]], [4096, 16384, 24576, 32768])
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured if cell["evidence_id"] == expansion_id], [4096, 16384, 24576, 32768])
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["selectors"]["active_context_tokens"], 2048)
        self.assertNotIn("evidence_id", quarantined[0])
        self.assertTrue(quarantined[0]["evidence"].endswith("tp4-mtp1-f16-eager-depth-expansion-r1-result.json"))
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"],
            [0],
        )
        self.assertTrue(all(
            cell["selectors"]["tp"] == 4
            and cell["selectors"]["mtp"] == 1
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
            for cell in cells
        ))

        result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp1-f16-eager-8k-sentinel-r1-result.json"
        ).read_text())
        self.assertEqual(result["point"]["published_decode_field"], "conventional_99_interval_tok_s")
        self.assertEqual(result["authority"]["site_cells"], 1)
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])
        self.assertEqual(
            result["authority"]["protected_decode_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        graph_series = series["q38-autoround-tp4-f16kv-http-context-r1-grade-c"]
        self.assertEqual(graph_series["points"][2]["decode_tok_s"], 69.8695629973191)

    def test_q38_current_f01e_tp2_eager_adds_six_without_replacing_graph_profile(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp2-f01e-eager-f16-depth-grade-c"
        measurement_id = "q38-f01e-autoround-tp2-eager-f16-exact-context-r1-grade-c"
        contract_id = "qwen38-tp2-vllm-xpu-autoround-f01e-eager-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [2048, 4096, 8192, 16384, 24576, 32768])
        self.assertEqual(
            [point["decode_tok_s"] for point in points],
            [9.645823300859325, 10.041573627140547, 10.108015740743388, 10.12371796916948, 10.146000927730311, 10.201853504519782],
        )
        self.assertTrue(all(point["cached_tokens"] == 0 for point in points))

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [2048, 4096, 8192, 16384, 24576, 32768])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in measured))
        self.assertTrue(all(cell["selectors"]["tp"] == 2 and cell["selectors"]["mtp"] == 0 and cell["selectors"]["graph_mode"] == "off" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-eager-depth-expansion-r1-result.json").read_text())
        self.assertEqual(result["published_decode_field"], "conventional_99_interval_tok_s")
        self.assertEqual(result["quality"]["tp1_cross_topology_parity_depths"], [2048, 4096, 8192, 16384, 24576, 32768])
        self.assertTrue(result["quality"]["cache_zero_all_16_quality_requests"])
        self.assertEqual(result["authority"]["new_site_cells"], 6)
        self.assertFalse(result["authority"]["headline_or_protected_replacement"])
        self.assertFalse(result["authority"]["older_tp2_series_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertEqual(series["q38-autoround-tp2-f16kv-http-context-r1-grade-c"]["points"][0]["decode_tok_s"], 48.15370845841339)

    def test_q38_current_f01e_tp1_piecewise_adjudication_keeps_five_and_quarantines_8k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp1-f01e-graphmodes-depth-grade-c"
        measurement_id = "q38-f01e-autoround-tp1-piecewise-f16-exact-context-r3"
        adjudication_path = (
            "experiments/qwen38-27b-b70/data/"
            "2026-08-26-qwen38-official-f01e-autoround-tp1-mtp0-f16-piecewise-depth-r3-human-adjudication-result.json"
        )

        packet = packets[packet_id]
        self.assertEqual(packet["grades"]["evidence"]["grade"], "C")
        self.assertEqual(packet["manifest"], adjudication_path)
        self.assertIn(adjudication_path, packet["grades"]["evidence"]["evidence"])

        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [2048, 4096, 16384, 24576, 32768])
        self.assertEqual(
            [point["decode_tok_s"] for point in points],
            [30.075429359128265, 29.41347238250489, 28.192761390148664, 27.463520678399885, 26.759466347975422],
        )
        self.assertTrue(all(point["cached_tokens"] == 0 for point in points))
        self.assertEqual(series[measurement_id]["evidence"], adjudication_path)

        cells, errors = MODULE.expand_coverage_contract(contracts["qwen38-tp1-vllm-xpu-target-matrix"])
        self.assertEqual(errors, [])
        cells = [
            cell for cell in cells
            if cell["selectors"].get("revision") == "qwen3.8-27b"
            and cell["selectors"].get("artifact_id") == "qwen38-27b-autoround-w4a16-bce40ca"
            and cell["selectors"].get("tp") == 1
            and cell["selectors"].get("mtp") == 0
            and cell["selectors"].get("graph_mode") == "PIECEWISE"
            and cell["selectors"].get("kv") == "f16"
        ]
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [2048, 4096, 16384, 24576, 32768])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in measured))
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in quarantined], [8192])
        self.assertIn("token-99", quarantined[0]["label"])
        self.assertNotIn("evidence_id", quarantined[0])
        self.assertNotIn("point_x", quarantined[0])
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])

        adjudication = json.loads((MODULE.ROOT / adjudication_path).read_text())
        self.assertEqual(adjudication["coverage"]["lab_measured_depths"], [2048, 4096, 16384, 24576, 32768])
        self.assertEqual(adjudication["coverage"]["quarantined_depths"], [8192])
        self.assertFalse(adjudication["authority"]["quarantined_8k_speed_selection"])
        self.assertFalse(adjudication["authority"]["graph_mtp_descendant_authority"])
        self.assertEqual(adjudication["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])

        view = next(item for item in family["views"] if item["id"] == "context-q38-tp1-autoround-graphmodes")
        self.assertEqual(view["series"][1]["measurement_ids"], [measurement_id])
        self.assertIn("8K quarantined", view["subtitle"])
        rendered = MODULE.family_page(family)
        self.assertNotIn("29.01975248295894", rendered)
        self.assertNotIn("5060.748901989427", rendered)

    def test_q38_current_f01e_tp1_mtp1_piecewise_publishes_only_exact_4k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp1-f01e-mtp1-piecewise-f16-4k-grade-c"
        measurement_id = "q38-f01e-autoround-tp1-mtp1-piecewise-f16-exact-4k-r1-grade-c"
        contract_id = "qwen38-tp1-vllm-xpu-autoround-mtp-matrix"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        point = series[measurement_id]["points"]
        self.assertEqual([item["x"] for item in point], [4096])
        self.assertEqual(point[0]["decode_tok_s"], 8.685875123241662)
        self.assertEqual(point[0]["ttft_ms"], 2962.142157004564)
        self.assertEqual((point[0]["accepted_tokens"], point[0]["drafted_tokens"]), (56, 71))
        self.assertEqual(point[0]["output_token_ids_sha256"], "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0")

        self.assertEqual(
            series[measurement_id]["runtime_profile_id"],
            "qwen38-tp1-vllm-xpu-autoround-native-mtp-v1",
        )
        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 252)
        scoped = [
            cell for cell in cells
            if cell["selectors"]["mtp"] == 1
            and cell["selectors"]["graph_mode"] == "PIECEWISE"
            and cell["selectors"]["kv"] == "f16"
        ]
        measured = [cell for cell in scoped if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096])
        self.assertEqual(measured[0]["evidence_id"], measurement_id)
        self.assertEqual(measured[0]["packet_id"], packet_id)
        missing = [cell["selectors"]["active_context_tokens"] for cell in scoped if cell["state"] == "missing"]
        self.assertEqual(missing, [0, 2048, 8192, 16384, 24576, 32768])
        self.assertEqual(len(scoped), 7)

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-f16-piecewise-4k-sentinel-r1-result.json").read_text())
        self.assertEqual(result["human_adjudication"]["selected_depths"], [4096])
        self.assertEqual(result["human_adjudication"]["missing_depths"], [0, 2048, 8192, 16384, 24576, 32768])
        self.assertEqual(result["authority"]["site_cells"], 1)
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertEqual(result["historical_graph_corruption_caveat"]["first_divergence"]["one_based"], 99)

        view = next(item for item in family["views"] if item["id"] == "context-q38-tp1-autoround-mtp1-partial")
        self.assertEqual(view["series"][1]["measurement_ids"], [measurement_id])
        rendered = MODULE.family_page(family)
        self.assertIn("8.69", rendered)
        self.assertIn("PIECEWISE", rendered)

    def test_q38_current_f01e_tp1_mtp1_eager_e4m3_publishes_only_exact_4k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp1-f01e-mtp1-eager-e4m3kv-4k-grade-c"
        measurement_id = "q38-f01e-autoround-tp1-mtp1-eager-e4m3kv-exact-4k-r1-grade-c"
        contract_id = "qwen38-tp1-vllm-xpu-autoround-mtp-matrix"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        point = series[measurement_id]["points"]
        self.assertEqual([item["x"] for item in point], [4096])
        self.assertEqual(point[0]["decode_tok_s"], 8.378608393519674)
        self.assertEqual(point[0]["ttft_ms"], 3843.1851619970985)
        self.assertEqual((point[0]["accepted_tokens"], point[0]["drafted_tokens"]), (62, 66))
        self.assertEqual(point[0]["output_token_ids_sha256"], "a3d7ad63a22cfb897d9d7f69952e30e2036617776d18fb4c8a9be1513da522cd")

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        scoped = [
            cell for cell in cells
            if cell["selectors"]["mtp"] == 1
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "fp8_e4m3"
        ]
        measured = [cell for cell in scoped if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096])
        self.assertEqual(measured[0]["evidence_id"], measurement_id)
        self.assertEqual(measured[0]["packet_id"], packet_id)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in scoped if cell["state"] == "missing"],
            [0, 2048, 8192, 16384, 24576, 32768],
        )
        self.assertEqual(len(scoped), 7)

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp1-e4m3kv-eager-4k-sentinel-r1-result.json").read_text())
        self.assertEqual(result["publication_candidate"]["selected_depths"], [4096])
        self.assertEqual(result["publication_candidate"]["missing_depths"], [0, 2048, 8192, 16384, 24576, 32768])
        self.assertEqual(result["authority"]["measured_cells_pending_publication"], 1)
        self.assertEqual(result["authority"]["site_cells_published_by_this_packet"], 0)
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])

        rendered = MODULE.family_page(family)
        self.assertIn("MTP1 eager/E4M3 · exact 4K Grade C", rendered)
        self.assertIn("4K: 8.38", rendered)
        self.assertNotIn("8.463240801535022", rendered)

    def test_q38_current_f01e_tp1_mtp2_piecewise_publishes_only_exact_4k_with_cache_defect_disclosed(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp1-f01e-mtp2-piecewise-f16-4k-grade-c"
        measurement_id = "q38-f01e-autoround-tp1-mtp2-piecewise-f16-exact-4k-r1-grade-c"
        contract_id = "qwen38-tp1-vllm-xpu-autoround-mtp-matrix"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        self.assertIn("omitted its promised cache gate", packets[packet_id]["grades"]["evidence"]["basis"])
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [4096])
        self.assertEqual(points[0]["decode_tok_s"], 11.988874911178696)
        self.assertEqual(points[0]["ttft_ms"], 2941.726919991197)
        self.assertEqual((points[0]["accepted_tokens"], points[0]["drafted_tokens"]), (80, 94))

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        scoped = [cell for cell in cells if cell["selectors"]["mtp"] == 2 and cell["selectors"]["graph_mode"] == "PIECEWISE" and cell["selectors"]["kv"] == "f16"]
        measured = [cell for cell in scoped if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096])
        self.assertEqual(measured[0]["evidence_id"], measurement_id)
        self.assertEqual(measured[0]["packet_id"], packet_id)
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in scoped if cell["state"] == "missing"], [0, 2048, 8192, 16384, 24576, 32768])

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp1-mtp2-f16-piecewise-4k-sentinel-r1-result.json").read_text())
        self.assertFalse(result["cache_isolation"]["original_terminal_enforced_cache_gate"])
        self.assertTrue(result["cache_isolation"]["postrun_audit_passed"])
        self.assertEqual(result["cache_isolation"]["observed_rank_namespaces"], ["rank_0_0"])
        self.assertEqual(result["human_adjudication"]["selected_depths"], [4096])
        self.assertEqual(result["human_adjudication"]["excluded_depths"], [0, 2048, 8192, 16384, 24576, 32768])
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])

        rendered = MODULE.family_page(family)
        self.assertIn("MTP2 PIECEWISE · exact 4K Grade C · cache defect disclosed", rendered)
        self.assertIn("4K: 11.99", rendered)
        self.assertNotIn("12.10997465775626", rendered)

    def test_q38_current_f01e_tp2_mtp1_piecewise_publishes_only_exact_4k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp2-f01e-mtp1-piecewise-f16-4k-grade-c"
        measurement_id = "q38-f01e-autoround-tp2-mtp1-piecewise-f16-exact-4k-r1-grade-c"
        contract_id = "qwen38-tp2-vllm-xpu-autoround-f01e-mtp1-piecewise-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [4096])
        self.assertEqual(points[0]["decode_tok_s"], 13.743731651970505)
        self.assertEqual(points[0]["ttft_ms"], 2651.291036992916)
        self.assertEqual((points[0]["accepted_tokens"], points[0]["drafted_tokens"]), (56, 71))
        self.assertEqual(points[0]["output_token_ids_sha256"], "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0")

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096])
        self.assertEqual(measured[0]["evidence_id"], measurement_id)
        self.assertEqual(measured[0]["packet_id"], packet_id)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"],
            [0, 2048, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(cell["selectors"]["tp"] == 2 and cell["selectors"]["mtp"] == 1 and cell["selectors"]["graph_mode"] == "PIECEWISE" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp1-f16-piecewise-4k-sentinel-r1-result.json").read_text())
        self.assertEqual(result["publication_candidate"]["selected_depths"], [4096])
        self.assertEqual(result["publication_candidate"]["missing_depths"], [0, 2048, 8192, 16384, 24576, 32768])
        self.assertEqual(result["authority"]["measured_cells_pending_publication"], 1)
        self.assertEqual(result["authority"]["site_cells_published_by_this_packet"], 0)
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])

        view = next(item for item in family["views"] if item["id"] == "context-q38-tp2-autoround-graphmodes")
        self.assertEqual(view["series"][2]["measurement_ids"], [measurement_id])
        rendered = MODULE.family_page(family)
        self.assertIn("MTP1 PIECEWISE · exact 4K Grade C", rendered)
        self.assertIn("4K: 13.74", rendered)
        self.assertNotIn("13.882557224212631", rendered)

    def test_q38_current_f01e_tp2_mtp2_piecewise_publishes_only_exact_4k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp2-f01e-mtp2-piecewise-f16-4k-grade-c"
        measurement_id = "q38-f01e-autoround-tp2-mtp2-piecewise-f16-exact-4k-r1-grade-c"
        contract_id = "qwen38-tp2-vllm-xpu-autoround-f01e-mtp2-piecewise-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [4096])
        self.assertEqual(points[0]["decode_tok_s"], 18.40866489344403)
        self.assertEqual(points[0]["ttft_ms"], 3125.5207280046307)
        self.assertEqual((points[0]["accepted_tokens"], points[0]["drafted_tokens"]), (80, 94))
        self.assertEqual(points[0]["output_token_ids_sha256"], "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0")
        self.assertNotIn("historical_100_event_decode_tok_s", points[0])

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096])
        self.assertEqual(measured[0]["evidence_id"], measurement_id)
        self.assertEqual(measured[0]["packet_id"], packet_id)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"],
            [0, 2048, 8192, 16384, 24576, 32768],
        )
        self.assertTrue(all(cell["selectors"]["tp"] == 2 and cell["selectors"]["mtp"] == 2 and cell["selectors"]["graph_mode"] == "PIECEWISE" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp2-f16-piecewise-4k-sentinel-r1-result.json").read_text())
        self.assertEqual(result["publication_candidate"]["selected_depths"], [4096])
        self.assertEqual(result["publication_candidate"]["missing_depths"], [0, 2048, 8192, 16384, 24576, 32768])
        self.assertEqual(result["authority"]["measured_cells_pending_publication"], 1)
        self.assertEqual(result["authority"]["site_cells_published_by_this_packet"], 0)
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])

        view = next(item for item in family["views"] if item["id"] == "context-q38-tp2-autoround-graphmodes")
        self.assertEqual(view["series"][3]["measurement_ids"], [measurement_id])
        rendered = MODULE.family_page(family)
        self.assertIn("MTP2 PIECEWISE · exact 4K Grade C", rendered)
        self.assertIn("4K: 18.41", rendered)
        self.assertNotIn("18.59461100347882", rendered)

    def test_q38_current_f01e_tp2_piecewise_adds_four_and_quarantines_two_without_replacing_graph(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp2-f01e-piecewise-f16-depth-grade-c"
        measurement_id = "q38-f01e-autoround-tp2-piecewise-f16-exact-context-r1-grade-c"
        contract_id = "qwen38-tp2-vllm-xpu-autoround-f01e-piecewise-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [2048, 4096, 24576, 32768])
        self.assertEqual([point["decode_tok_s"] for point in points], [39.676315011384126, 46.64233045432341, 42.16719656056682, 41.13662863433114])
        self.assertTrue(all(point["cached_tokens"] == 0 for point in points))

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [2048, 4096, 24576, 32768])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in measured))
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in quarantined], [8192, 16384])
        self.assertIn("token-99", quarantined[0]["label"])
        self.assertIn("token-32", quarantined[1]["label"])
        self.assertTrue(all("evidence_id" not in cell and "point_x" not in cell for cell in quarantined))
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])
        self.assertTrue(all(cell["selectors"]["tp"] == 2 and cell["selectors"]["mtp"] == 0 and cell["selectors"]["graph_mode"] == "PIECEWISE" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp0-f16-piecewise-depth-r1-result.json").read_text())
        self.assertEqual(result["adjudication"]["valid_depths"], [2048, 4096, 24576, 32768])
        self.assertEqual(result["adjudication"]["quarantined_depths"], [8192, 16384])
        self.assertFalse(result["authority"]["dated_fully_certified_graph_profile_replacement"])
        self.assertFalse(result["authority"]["diagnostic_quarantine_speeds_exposed_on_site"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertEqual(series["q38-autoround-tp2-f16kv-http-context-r1-grade-c"]["points"][0]["decode_tok_s"], 48.15370845841339)
        view = next(item for item in family["views"] if item["id"] == "context-q38-tp2-autoround-graphmodes")
        self.assertEqual(view["series"][1]["measurement_ids"], [measurement_id])
        rendered = MODULE.family_page(family)
        self.assertNotIn("45.21462067141575", rendered)
        self.assertNotIn("43.99393016711806", rendered)

    def test_q38_current_f01e_tp4_piecewise_adds_five_and_quarantines_8k_without_replacing_graph(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp4-f01e-piecewise-f16-depth-grade-c"
        measurement_id = "q38-f01e-autoround-tp4-piecewise-f16-exact-context-r1-grade-c"
        contract_id = "qwen38-tp4-vllm-xpu-autoround-f01e-piecewise-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [2048, 4096, 16384, 24576, 32768])
        self.assertEqual([point["decode_tok_s"] for point in points], [51.06747790791104, 64.42037960929412, 62.78221708432737, 62.092862199068605, 60.50826347203049])
        self.assertTrue(all(point["cached_tokens"] == 0 for point in points))

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [2048, 4096, 16384, 24576, 32768])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in measured))
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in quarantined], [8192])
        self.assertIn("token-99", quarantined[0]["label"])
        self.assertNotIn("evidence_id", quarantined[0])
        self.assertNotIn("point_x", quarantined[0])
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])
        self.assertTrue(all(cell["selectors"]["tp"] == 4 and cell["selectors"]["mtp"] == 0 and cell["selectors"]["graph_mode"] == "PIECEWISE" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-piecewise-depth-r1-result.json").read_text())
        self.assertEqual(result["adjudication"]["valid_depths"], [2048, 4096, 16384, 24576, 32768])
        self.assertEqual(result["adjudication"]["quarantined_depths"], [8192])
        self.assertFalse(result["authority"]["dated_fully_certified_graph_profile_replacement"])
        self.assertFalse(result["authority"]["diagnostic_quarantine_speeds_exposed_on_site"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertEqual(series["q38-autoround-tp4-f16kv-http-context-r1-grade-c"]["points"][0]["decode_tok_s"], 71.16806401683698)
        view = next(item for item in family["views"] if item["id"] == "context-q38-tp4-autoround-graphmodes")
        self.assertEqual(view["series"][2]["measurement_ids"], [measurement_id])
        rendered = MODULE.family_page(family)
        self.assertNotIn("63.755137080322065", rendered)

    def test_q38_current_f01e_tp2_mtp2_adds_five_and_quarantines_2k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp2-f01e-mtp2-eager-f16-depth-grade-c"
        measurement_id = "q38-f01e-autoround-tp2-mtp2-eager-f16-exact-context-r1-grade-c"
        contract_id = "qwen38-tp2-vllm-xpu-autoround-f01e-mtp2-eager-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [4096, 8192, 16384, 24576, 32768])
        self.assertEqual(
            [point["decode_tok_s"] for point in points],
            [20.36405574066059, 20.893715666020707, 18.289177744392617, 17.759261196319386, 17.695971649981892],
        )
        self.assertTrue(all(point["cached_tokens"] == 0 for point in points))

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096, 8192, 16384, 24576, 32768])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in measured))
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["selectors"]["active_context_tokens"], 2048)
        self.assertNotIn("evidence_id", quarantined[0])
        self.assertIn("A72/110", quarantined[0]["label"])
        self.assertTrue(quarantined[0]["evidence"].endswith("tp2-mtp2-f16-eager-depth-expansion-r1-result.json"))
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])
        self.assertTrue(all(cell["selectors"]["tp"] == 2 and cell["selectors"]["mtp"] == 2 and cell["selectors"]["graph_mode"] == "off" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp2-f16-eager-depth-expansion-r1-result.json").read_text())
        self.assertEqual(result["adjudication"]["valid_depths"], [4096, 8192, 16384, 24576, 32768])
        self.assertEqual(result["adjudication"]["quarantined_depths"], [2048])
        self.assertTrue(result["quarantined_points"][0]["exact_depth_gate_passed"])
        self.assertEqual((result["quarantined_points"][0]["accepted_tokens"], result["quarantined_points"][0]["drafted_tokens"]), (72, 110))
        self.assertFalse(result["adjudication"]["automatic_publication_authority"])
        self.assertFalse(result["authority"]["headline_or_protected_replacement"])
        self.assertFalse(result["authority"]["mtp1_profile_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertEqual(series["q38-f01e-autoround-tp2-mtp1-eager-f16-exact-context-r1-grade-c"]["points"][0]["decode_tok_s"], 11.882449351158243)

    def test_q38_current_f01e_tp2_mtp3_adds_five_and_inherits_2k_quarantine_without_speed(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        packet_id = "qwen38-27b-autoround-int4-tp2-f01e-mtp3-eager-f16-depth-grade-c"
        measurement_id = "q38-f01e-autoround-tp2-mtp3-eager-f16-exact-context-r1-grade-c"
        contract_id = "qwen38-tp2-vllm-xpu-autoround-f01e-mtp3-eager-depth"

        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        points = series[measurement_id]["points"]
        self.assertEqual([point["x"] for point in points], [4096, 8192, 16384, 24576, 32768])
        self.assertEqual(
            [point["decode_tok_s"] for point in points],
            [19.08418591204264, 25.11756608538104, 20.279538044061752, 20.171481912081873, 20.15867375927568],
        )
        self.assertTrue(all(point["cached_tokens"] == 0 for point in points))

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in measured], [4096, 8192, 16384, 24576, 32768])
        self.assertTrue(all(cell["evidence_id"] == measurement_id and cell["packet_id"] == packet_id for cell in measured))
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["selectors"]["active_context_tokens"], 2048)
        self.assertNotIn("evidence_id", quarantined[0])
        self.assertIn("no MTP3 speed", quarantined[0]["label"])
        self.assertTrue(quarantined[0]["evidence"].endswith("tp2-mtp2-f16-eager-depth-expansion-r1-result.json"))
        self.assertEqual([cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"], [0])
        self.assertTrue(all(cell["selectors"]["tp"] == 2 and cell["selectors"]["mtp"] == 3 and cell["selectors"]["graph_mode"] == "off" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp3-f16-eager-depth-expansion-r1-result.json").read_text())
        self.assertEqual(result["adjudication"]["valid_depths"], [4096, 8192, 16384, 24576, 32768])
        self.assertEqual(result["adjudication"]["structurally_excluded_depths"], [2048])
        self.assertTrue(result["adjudication"]["excluded_depths_were_not_run"])
        self.assertFalse(result["structurally_excluded_points"][0]["speed_observed"])
        self.assertNotIn("decode_tok_s", result["structurally_excluded_points"][0])
        self.assertFalse(result["authority"]["headline_or_protected_replacement"])
        self.assertFalse(result["authority"]["mtp2_profile_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        self.assertEqual(series["q38-f01e-autoround-tp2-mtp2-eager-f16-exact-context-r1-grade-c"]["points"][0]["decode_tok_s"], 20.36405574066059)

    def test_q38_current_f01e_tp2_mtp4_measures_4k_16k_24k_and_retains_8k_quarantine(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}
        quarantine_packet_id = "qwen38-27b-autoround-int4-tp2-f01e-mtp4-eager-f16-8k-quarantine"
        measured_packet_id = "qwen38-27b-autoround-int4-tp2-f01e-mtp4-eager-f16-4k-grade-c"
        expansion_packet_id = "qwen38-27b-autoround-int4-tp2-f01e-mtp4-eager-f16-16k24k-grade-c"
        measurement_id = "q38-f01e-autoround-tp2-mtp4-eager-f16-exact-4k-r1-grade-c"
        expansion_measurement_id = "q38-f01e-autoround-tp2-mtp4-eager-f16-exact-16k24k-r1-grade-c"
        contract_id = "qwen38-tp2-vllm-xpu-autoround-f01e-mtp4-eager-depth"

        self.assertEqual(packets[quarantine_packet_id]["grades"]["evidence"]["grade"], "D")
        self.assertEqual(packets[measured_packet_id]["grades"]["evidence"]["grade"], "C")
        self.assertEqual(packets[expansion_packet_id]["grades"]["evidence"]["grade"], "C")
        self.assertEqual(
            series[measurement_id]["points"],
            [{"x": 4096, "decode_tok_s": 21.080466832575162, "ttft_ms": 4336.120582011063, "cached_tokens": 0, "drafted_tokens": 148, "accepted_tokens": 90, "draft_acceptance_rate": 0.6081081081081081, "output_token_ids_sha256": "3febb16ef2033c31e17817c6753ccdb95ad6e39db394ed4476ee12fb86af78b0"}],
        )
        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual(len(measured), 3)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in measured],
            [4096, 16384, 24576],
        )
        self.assertEqual(measured[0]["evidence_id"], measurement_id)
        self.assertEqual(measured[0]["packet_id"], measured_packet_id)
        self.assertTrue(all(
            cell["evidence_id"] == expansion_measurement_id
            and cell["packet_id"] == expansion_packet_id
            for cell in measured[1:]
        ))
        self.assertEqual(
            [point["decode_tok_s"] for point in series[expansion_measurement_id]["points"]],
            [18.455933818605118, 23.358856068128627],
        )
        quarantined = [cell for cell in cells if cell["state"] == "quarantined"]
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0]["selectors"]["active_context_tokens"], 8192)
        self.assertEqual(quarantined[0]["packet_id"], quarantine_packet_id)
        self.assertNotIn("evidence_id", quarantined[0])
        self.assertNotIn("point_x", quarantined[0])
        self.assertIn("token-99", quarantined[0]["label"])
        self.assertTrue(quarantined[0]["evidence"].endswith("tp2-mtp4-f16-eager-8k-sentinel-r1-result.json"))
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"],
            [0, 2048, 32768],
        )
        self.assertTrue(all(cell["selectors"]["tp"] == 2 and cell["selectors"]["mtp"] == 4 and cell["selectors"]["graph_mode"] == "off" and cell["selectors"]["kv"] == "f16" for cell in cells))

        result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-8k-sentinel-r1-result.json").read_text())
        self.assertEqual(result["authority"]["site_structural_quarantine_cells"], 1)
        self.assertEqual(result["authority"]["site_measured_speed_cells"], 0)
        self.assertFalse(result["diagnostic_point"]["site_speed_publication"])
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])
        self.assertEqual(result["authority"]["protected_decode_values_unchanged"], [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144])
        measured_result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-4k-sentinel-r1-result.json").read_text())
        self.assertEqual(measured_result["authority"]["site_cells"], 1)
        self.assertTrue(measured_result["authority"]["existing_8k_quarantine_unchanged"])
        self.assertTrue(measured_result["authority"]["x0_2k_16k_24k_32k_remain_missing"])
        expansion_result = json.loads((MODULE.ROOT / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp2-mtp4-f16-eager-16k24k-expansion-r1-result.json").read_text())
        self.assertEqual(expansion_result["authority"]["evidence_depths"], [16384, 24576])
        self.assertTrue(expansion_result["authority"]["existing_8k_quarantine_unchanged"])
        rendered = MODULE.family_page(family)
        self.assertNotIn("21.915468017099425", rendered)
        self.assertNotIn("22.13683638090851", rendered)

    def test_q38_current_f01e_tp4_eager_oracle_adds_five_without_replacing_8k(self) -> None:
        family = json.loads((MODULE.ROOT / "families/qwen-27b.json").read_text())
        packets = {item["id"]: item for item in family["packets"]}
        series = {item["id"]: item for item in family["series_measurements"]}
        contracts = {item["id"]: item for item in family["coverage_contracts"]}

        packet_id = "qwen38-27b-autoround-int4-tp4-f01e-eager-f16-oracle-8k-grade-c"
        measurement_id = "q38-f01e-autoround-tp4-eager-f16-exact-8k-r1-grade-c"
        contract_id = "qwen38-tp4-vllm-xpu-autoround-f01e-eager-oracle-depth"
        self.assertEqual(packets[packet_id]["grades"]["evidence"]["grade"], "C")
        point = series[measurement_id]["points"]
        self.assertEqual(len(point), 1)
        self.assertEqual(point[0]["x"], 8192)
        self.assertEqual(point[0]["decode_tok_s"], 9.647242826428695)
        self.assertEqual(point[0]["historical_100_event_decode_tok_s"], 9.74468972366535)
        self.assertEqual(point[0]["cached_tokens"], 0)

        cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
        self.assertEqual(errors, [])
        self.assertEqual(len(cells), 7)
        measured = [cell for cell in cells if cell["state"] == "lab-measured"]
        self.assertEqual(len(measured), 6)
        retained = next(cell for cell in measured if cell["selectors"]["active_context_tokens"] == 8192)
        self.assertEqual(retained["evidence_id"], measurement_id)
        self.assertEqual(retained["packet_id"], packet_id)
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in cells if cell["state"] == "missing"],
            [0],
        )
        expansion_id = "q38-f01e-autoround-tp4-eager-f16-exact-context-expansion-r1-grade-c"
        expansion_packet = "qwen38-27b-autoround-int4-tp4-f01e-eager-f16-depth-grade-c"
        expansion = series[expansion_id]
        self.assertEqual([point["x"] for point in expansion["points"]], [2048, 4096, 16384, 24576, 32768])
        self.assertEqual(
            [cell["selectors"]["active_context_tokens"] for cell in measured if cell["evidence_id"] == expansion_id],
            [2048, 4096, 16384, 24576, 32768],
        )
        self.assertTrue(all(cell["packet_id"] == expansion_packet for cell in measured if cell["evidence_id"] == expansion_id))
        self.assertTrue(all(
            cell["selectors"]["tp"] == 4
            and cell["selectors"]["mtp"] == 0
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
            for cell in cells
        ))

        result = json.loads((
            MODULE.ROOT
            / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-official-f01e-autoround-tp4-mtp0-f16-eager-8k-oracle-sentinel-r1-result.json"
        ).read_text())
        self.assertEqual(result["point"]["published_decode_field"], "conventional_99_interval_tok_s")
        self.assertEqual(result["authority"]["site_cells"], 1)
        self.assertFalse(result["authority"]["historical_or_protected_replacement"])
        self.assertEqual(
            result["authority"]["protected_decode_values_unchanged"],
            [71.45427094575045, 30.329809361830037, 49.05894025767351, 71.9001988117144],
        )
        graph_series = series["q38-autoround-tp4-f16kv-http-context-r1-grade-c"]
        self.assertEqual(graph_series["points"][2]["decode_tok_s"], 69.8695629973191)
        protected = next(
            item for item in family["run_measurements"]
            if item["id"] == "q38-a3561ef8-stock-tp4-graph-strict"
        )
        self.assertEqual(protected["metrics"]["decode_tok_s"][0], 71.9001988117144)

    def test_flash_next_practical_coverage_is_compact_exact_and_runtime_bound(self) -> None:
        family_path = MODULE.ROOT / "families/qwen-flash-next.json"
        family = json.loads(family_path.read_text())
        errors = MODULE.validate_family(family, family_path)
        self.assertEqual(errors, [])
        self.assertTrue(family["collapse_coverage_contracts"])
        self.assertEqual(family.get("estimates"), [])

        views = {view["id"]: view for view in family["coverage_views"]}
        self.assertEqual(
            list(views),
            [
                "qwen-flash-next-tp4-mtp-by-context",
                "qwen-flash-next-tp-fit",
                "qwen-flash-next-graph-by-modality",
            ],
        )
        practical = views["qwen-flash-next-tp4-mtp-by-context"]
        self.assertEqual(practical["rows"], [0, 1, 2, 3, 4])
        self.assertEqual(practical["columns"], [0, 1024, 2048, 4096, 8192])
        self.assertEqual(len(practical["cells"]), 25)
        practical_states = Counter(
            cell["state"] for cell in practical["cells"].values()
        )
        self.assertEqual(
            practical_states,
            Counter({"lab-screened": 12, "missing": 12, "quarantined": 1}),
        )
        self.assertFalse(
            any(
                cell.get("state") == "estimated" or "estimate_id" in cell
                for cell in practical["cells"].values()
            )
        )

        measurements = {
            measurement["id"]: measurement
            for measurement in MODULE.records(family)
        }
        runtime_by_mtp = {
            0: "vLLM XPU 658965050 + kernels 2f829747",
            1: "vLLM XPU 1372c62d + staged kernels 2f829747",
            2: "vLLM XPU 1372c62d + staged kernels 2f829747",
            3: "vLLM XPU 1372c62d + staged kernels 2f829747",
            4: "vLLM XPU 1372c62d + staged kernels 2f829747",
        }
        for mtp in practical["rows"]:
            for context in practical["columns"]:
                cell = practical["cells"][f"{mtp}:{context}"]
                selectors = MODULE.effective_cell_selectors(
                    practical, mtp, context, cell
                )
                self.assertEqual(selectors["runtime"], runtime_by_mtp[mtp])
                evidence_id = cell.get("evidence_id")
                if evidence_id:
                    measurement = measurements[evidence_id]
                    for key in (
                        "revision",
                        "artifact_id",
                        "runtime",
                        "runtime_family",
                        "tp",
                        "ep",
                        "parallel_profile",
                        "mtp",
                        "active_context_tokens",
                        "graph_mode",
                        "kv",
                        "modality",
                    ):
                        self.assertEqual(
                            MODULE.record_selector_value(measurement, key),
                            selectors[key],
                            f"{evidence_id} selector {key}",
                        )

        mtp3_4k = practical["cells"]["3:4096"]
        self.assertEqual(mtp3_4k["state"], "lab-screened")
        self.assertEqual(
            mtp3_4k["evidence_id"],
            "qwen38-flash-next-fp8-tp4-mtp3-context4k-a1",
        )
        serialized = json.dumps(family, sort_keys=True)
        self.assertNotIn("mtp3-official-quality-prereg", serialized)
        self.assertIn(
            "20260827-tp4-mtp3-official-quality-attempt2-result.json",
            serialized,
        )
        mtp3_measurement = measurements[
            "qwen38-flash-next-fp8-tp4-mtp3-context4k-a1"
        ]
        self.assertEqual(mtp3_measurement["state"], "lab-screened")
        self.assertEqual(
            mtp3_measurement["metrics"]["decode_tok_s"],
            [15.50156510641242],
        )
        self.assertIn("MTP thinking parity", family["summary"])
        self.assertIn("unqualified", family["summary"])

        fit = views["qwen-flash-next-tp-fit"]
        self.assertEqual(len(fit["cells"]), 3)
        self.assertEqual(
            Counter(cell["state"] for cell in fit["cells"].values()),
            Counter({"missing": 2, "lab-screened": 1}),
        )
        self.assertTrue(
            all(
                cell["state"] != "unsupported"
                for cell in fit["cells"].values()
            )
        )

        graph_modality = views["qwen-flash-next-graph-by-modality"]
        self.assertEqual(len(graph_modality["cells"]), 4)
        self.assertEqual(
            Counter(cell["state"] for cell in graph_modality["cells"].values()),
            Counter({"missing": 3, "lab-screened": 1}),
        )
        self.assertEqual(
            graph_modality["cells"]["off:text"]["evidence_id"],
            "qwen38-flash-next-fp8-tp4-attempt19",
        )
        self.assertTrue(
            all(
                cell["state"] != "unsupported"
                for cell in graph_modality["cells"].values()
            )
        )

        contract_cells, contract_errors = MODULE.expand_coverage_contract(
            family["coverage_contracts"][0]
        )
        self.assertEqual(contract_errors, [])
        self.assertEqual(len(contract_cells), 480)
        self.assertEqual(
            Counter(cell["state"] for cell in contract_cells),
            Counter({"missing": 467, "lab-screened": 12, "quarantined": 1}),
        )

        rendered = MODULE.family_page(family)
        practical_heading = rendered.index("Practical TP4 eager text coverage")
        fit_heading = rendered.index("Card-fit summary")
        graph_heading = rendered.index("Graph and modality summary")
        contract_disclosure = rendered.index(
            '<details class="full-coverage-contracts">'
        )
        self.assertLess(practical_heading, fit_heading)
        self.assertLess(fit_heading, graph_heading)
        self.assertLess(graph_heading, contract_disclosure)
        self.assertIn(
            "Full 480-cell coverage contract · 13 classified", rendered
        )
        contract_end = rendered.index("</details>", contract_disclosure)
        self.assertIn("13/480", rendered[contract_disclosure:contract_end])
        self.assertIn("19 of 25 required rows", rendered)
        self.assertIn("inconclusive and unqualified", rendered)

    def test_collapsed_coverage_contract_flag_must_be_boolean(self) -> None:
        family = self._family()
        family["collapse_coverage_contracts"] = "yes"
        self.assertIn(
            "families/test-family.json: collapse_coverage_contracts must be boolean",
            self._errors(family),
        )

    @staticmethod
    def _family() -> dict[str, object]:
        return {
            "format": "neural-download-model-family-v1",
            "id": "test-family",
            "name": "Test family",
            "weight_revisions": [{"id": "revision-a", "label": "Revision A"}],
            "packets": [],
            "run_measurements": [
                {
                    "id": "measured-a",
                    "state": "lab-measured",
                    "revision": "revision-a",
                    "variant": "quant-a",
                    "runtime": "runtime-a",
                    "config": {"mtp": 0, "tp": 1, "graph": "off"},
                    "workload": "fixed test workload",
                    "metrics": {"decode_tok_s": [30.0, 30.2]},
                    "evidence": "https://example.test/measured-a.json",
                }
            ],
            "series_measurements": [],
            "views": [],
            "coverage_views": [
                {
                    "id": "legacy-mtp-tp",
                    "label": "legacy",
                    "fixed": "Legacy MTP by TP slice.",
                    "rows": [0],
                    "columns": [1],
                    "cells": {
                        "0:1": {
                            "state": "lab-measured",
                            "label": "30.0–30.2",
                            "evidence_id": "measured-a",
                        }
                    },
                }
            ],
            "family_closures": [],
            "estimates": [],
        }

    @staticmethod
    def _estimate() -> dict[str, object]:
        return {
            "id": "estimate-a",
            "state": "estimated",
            "selectors": {
                "revision": "revision-a",
                "variant": "quant-a",
                "runtime": "runtime-a",
                "graph": "off",
                "mtp": 4,
                "tp": 1,
            },
            "metric": "decode_tok_s",
            "unit": "tok/s",
            "value": 42.0,
            "interval": {"low": 36.0, "high": 48.0},
            "engine": {
                "name": "gap-engine",
                "version": "1.0.0",
                "snapshot_sha256": "sha256:" + "1" * 64,
            },
            "generated_at": "2026-08-23T12:00:00Z",
            "basis_measurement_ids": ["measured-a"],
            "record": "https://example.test/estimate-a.json",
            "not_for_promotion": True,
            "limitations": "Projection only; never packet performance evidence.",
        }

    @staticmethod
    def _measured_view() -> dict[str, object]:
        return {
            "id": "measured-curve",
            "title": "Measured curve",
            "subtitle": "Observed values only.",
            "x_label": "TP",
            "metrics": ["decode_tok_s"],
            "series": [
                {
                    "label": "measured",
                    "measurement_ids": ["measured-a"],
                    "x_from": "config.tp",
                }
            ],
        }

    @staticmethod
    def _errors(family: dict[str, object]) -> list[str]:
        source = MODULE.ROOT / "families" / "test-family.json"
        return MODULE.validate_family(family, source)


if __name__ == "__main__":
    unittest.main()
