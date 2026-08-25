#!/usr/bin/env python3
"""Focused tests for the model-family coverage validator and renderer."""

from __future__ import annotations

from copy import deepcopy
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
        self.assertIn('<span class="big">30</span>', rendered)
        self.assertNotIn('<span class="big">30.2</span>', rendered)
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
        hero = re.search(
            r'<a class="hero-headline".*?</a>', rendered, re.DOTALL
        )
        self.assertIsNotNone(hero)
        self.assertIn("71.45", hero.group(0))
        for protected in ("30.33", "49.06", "71.9"):
            self.assertIn(protected, strip_html)
        for eager in ("24.25", "16.77", "17.38", "71.72"):
            self.assertNotIn(eager, strip_html)

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
        self.assertIn("Scoped closures", rendered)
        self.assertIn("revision=revision-a", rendered)
        self.assertIn("https://example.test/closure.json", rendered)

    def test_packet_cta_labels_match_the_actual_target(self) -> None:
        package = {
            "id": "packet-a",
            "manifest": "packages/packet-a/package.json",
        }
        result = {
            "id": "result-a",
            "manifest": "results/result-a/README.md",
        }
        self.assertEqual(
            MODULE.packet_manifest_target(package),
            ("packet-a.html", "Open deployment packet"),
        )
        href, label = MODULE.packet_manifest_target(result)
        self.assertTrue(href.endswith("results/result-a/README.md"))
        self.assertEqual(label, "Read the lab report")

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
