#!/usr/bin/env python3
"""Focused tests for the model-family coverage validator and renderer."""

from __future__ import annotations

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
            "Target-only &middot; MTP0",
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
            "packages/qwen38-27b-q4km-tp2-asrock-b70/package.json": ("http-decode-vs-active-context", 44.43728051677345),
            "packages/qwen38-27b-q8-tp2-b70/package.json": ("http-decode-vs-active-context", 33.848820185540816),
            "packages/qwen38-27b-fp8-tp2-b70/package.json": ("http-decode-vs-active-context", 20.38985363507897),
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
        self.assertIn(">470.2&dagger;</a>", index_html)
        self.assertNotIn("raw&dagger;", index_html)
        self.assertNotIn("HTTP&dagger;", index_html)
        fp8_row = re.search(
            r"official FP8.*?</tr>", index_html, flags=re.DOTALL
        )
        self.assertIsNotNone(fp8_row)
        self.assertIn(">20.39&dagger;</a>", fp8_row.group(0))
        self.assertIn(">470.2&dagger;</a>", fp8_row.group(0))
        self.assertIn("32 active users", fp8_row.group(0))
        self.assertIn("c64 reaches 474.54 tok/s but queues", fp8_row.group(0))
        laguna_row = re.search(
            r"Laguna-S-2\.1.*?</tr>", index_html, flags=re.DOTALL
        )
        self.assertIsNotNone(laguna_row)
        self.assertNotIn(">20.39&dagger;</a>", laguna_row.group(0))
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
                / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-fp8-tp2-http-p32-confirmation-r3-result.json"
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
        self.assertTrue(result["points"][-1]["queued_profile"])
        self.assertTrue(all(not point["queued_profile"] for point in result["points"][:-1]))

    def test_promoted_ornith_packet_and_family_stay_in_parity(self) -> None:
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
        self.assertAlmostEqual(
            package["library"]["featured_metric"]["value"],
            sum(current) / len(current),
            places=6,
        )
        index_html = (MODULE.ROOT / "index.html").read_text()
        public_headline = f"{package['library']['featured_metric']['value']:.2f}"
        self.assertGreaterEqual(index_html.count(f">{public_headline}</td>"), 1)
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
        self.assertIn((float(public_headline), 100.0), ratebars)
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

        # Keep the old measurement IDs bound to their original eleven-feature
        # evidence while moving the public headline to a new twelve-feature ID.
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
        self.assertEqual(len(family_ids), 17)
        self.assertLessEqual(expected | {"qwen-35b"}, family_ids)
        model_index = (MODULE.ROOT / "models/index.html").read_text()
        for family_id in expected | {"qwen-35b"}:
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
            "qwen38-tp1-llamacpp-sycl-target-matrix": 112,
            "qwen38-tp1-llamacpp-sycl-mtp-package-matrix": 224,
            "qwen38-tp2-llamacpp-sycl-q4km-http-depth": 7,
            "qwen38-tp2-llamacpp-sycl-q8-http-depth": 7,
            "qwen38-tp2-vllm-xpu-fp8-http-depth": 7,
        }
        self.assertEqual(set(contracts), set(expected_counts))
        self.assertEqual(self._errors(family), [])

        all_cells = []
        for contract_id, expected_count in expected_counts.items():
            cells, errors = MODULE.expand_coverage_contract(contracts[contract_id])
            self.assertEqual(errors, [], contract_id)
            self.assertEqual(len(cells), expected_count, contract_id)
            all_cells.extend(cells)
        self.assertEqual(len(all_cells), 1792)

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
            if "-tp2-" in contract_id:
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
            sum(cell["state"] == "lab-measured" for cell in q38_target), 49
        )
        self.assertEqual(sum(cell["state"] == "estimated" for cell in q38_target), 0)
        self.assertTrue(all(cell["selectors"]["mtp"] == 0 for cell in q38_target))
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
                ["q38-q4km-tp1-kv-q8-context"],
            ],
        )
        self.assertIn("F16 x=0 remains raw", q38_q4km_view["subtitle"])
        self.assertIn("Q8_0 is the preserved raw-engine curve", q38_q4km_view["subtitle"])

        q38_q8_f16 = [
            cell for cell in q38_target
            if cell["selectors"]["artifact_id"]
            == "qwen38-27b-ggmlorg-q8-0-0669b98"
            and cell["selectors"]["graph_mode"] == "off"
            and cell["selectors"]["kv"] == "f16"
        ]
        self.assertEqual(len(q38_q8_f16), 7)
        self.assertTrue(all(cell["state"] == "lab-measured" for cell in q38_q8_f16))
        self.assertEqual(
            [cell["evidence_id"] for cell in q38_q8_f16],
            ["q38-q8weights-tp1-kv-f16-context"] * 7,
        )

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
                ["q38-q4kxl-tp1-q8kv-target-http-context-r1-grade-c"],
            ],
        )
        self.assertIn("both full quality batteries passed", q38_q4kxl_f16_view["subtitle"])

        q38_q5ks_view = next(
            view for view in family["views"]
            if view["id"] == "context-flagship-q8"
        )
        self.assertEqual(
            [item["measurement_ids"] for item in q38_q5ks_view["series"]],
            [
                ["q38-q5ks-tp1-f16kv-target-http-context-r1-grade-c"],
                ["q38-q5ks-tp1-q8kv-target-http-context-r1-grade-c"],
            ],
        )
        self.assertEqual(q38_q5ks_view["metrics"], ["decode_tok_s"])

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

        rendered = MODULE.family_page(family)
        overview = re.search(
            r'<section class="contract-overview".*?</section>',
            rendered,
            re.DOTALL,
        )
        self.assertIsNotNone(overview)
        overview_html = overview.group(0)
        self.assertIn("Coverage · 11 matrices", overview_html)
        self.assertIn("308/1,792 classified", overview_html)
        for state, count, word in (
            ("lab-measured", "213", "measured"),
            ("lab-screened", "32", "screened"),
            ("quarantined", "63", "quarantined"),
            ("missing", "1,484", "missing"),
        ):
            self.assertIn(f'class="is-{state}"><b>{count}</b> {word}', overview_html)
        self.assertNotIn('class="is-estimated"', overview_html)
        self.assertNotIn("7 estimates", rendered)

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
        self.assertIn("22 more evidence views", deferred_html)
        self.assertEqual(deferred_html.count('data-family-view="'), 22)
        self.assertIn(
            'data-family-view="context-q4kxl-f16-http"',
            deferred_html,
        )
        self.assertIn(
            'data-family-view="q38-q5ks-q8kv-mtp-8k-grade-c"',
            deferred_html,
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
        for expected in ("30–30.2", "100", "0.61", "2.4"):
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
