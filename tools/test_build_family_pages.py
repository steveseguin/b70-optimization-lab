#!/usr/bin/env python3
"""Focused tests for the model-family coverage validator and renderer."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("build-family-pages.py")
SPEC = importlib.util.spec_from_file_location("build_family_pages", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FamilyCoverageTest(unittest.TestCase):
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
        self.assertIn("<th>MTP / TP</th>", rendered)
        self.assertIn('<th scope="col">TP1</th>', rendered)
        self.assertIn('<tr><th scope="row">MTP0</th>', rendered)

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
        self.assertIn("<th>Active context / Quantization</th>", rendered)
        self.assertIn('<th scope="col">Q4_K_M</th>', rendered)
        self.assertIn('<tr><th scope="row">32K</th>', rendered)
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
        self.assertIn("≈ estimate", rendered)
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
        self.assertIn("OPT —", rendered)
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

            with (
                patch.object(MODULE, "ROOT", root),
                patch.object(MODULE, "CATALOG", root / "families/catalog.json"),
                patch.object(
                    MODULE, "PACKAGE_CATALOG", root / "packages/catalog.json"
                ),
                patch.object(MODULE, "OUT_DIR", root / "models"),
            ):
                self.assertEqual(MODULE.generate(check=True), 1)

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
