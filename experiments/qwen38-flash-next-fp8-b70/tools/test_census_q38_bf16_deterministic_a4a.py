#!/usr/bin/env python3
"""CPU-only contracts for the Flash-Next BF16 A4a census."""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


TOOL = Path(__file__).with_name("census-q38-bf16-deterministic-a4a.py")
SPEC = importlib.util.spec_from_file_location("q38_bf16_a4a", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def hashes(value: str) -> list[str]:
    return [f"{value}-row-{row}" for row in range(MODULE.ROWS)]


def snapshot(value: str, *, tail: str = "tail") -> dict:
    return {
        "full_sha256": f"full-{value}",
        "active_sha256": f"active-{value}",
        "tail_sha256": tail,
        "row_full_sha256": hashes(value),
        "row_active_sha256": hashes(value),
        "row_tail_sha256": [],
        "tail_all_numeric_zero": True,
    }


def fake_record(
    cell: dict,
    *,
    arm: str,
    replica: int,
    position: int,
    values: list[str] | None = None,
    per_call_us: float = 10.0,
) -> dict:
    values = values or ["authority"] * MODULE.SWEEPS
    items = [snapshot(value) for value in values]
    requested = arm == "mkldnn-deterministic"
    return {
        "status": "classified",
        "identity": {
            "model_revision": "revision",
            "a1_tool_sha256": MODULE.A1_TOOL_SHA256,
            "a3_tool_sha256": MODULE.A3_TOOL_SHA256,
            "a3_result_sha256": MODULE.A3_RESULT_SHA256,
            "provider_library_sha256": "provider",
            "input_sha256": f"input-{cell['family']}",
            "weight_sha256": f"weight-{cell['family']}-{cell['sentinel']}",
            "shard_contract_sha256": "contract",
            "family": cell["family"],
            "sentinel": {"id": cell["sentinel"]},
            "cell_index": cell["cell_index"],
            "counterbalance_pattern": cell["counterbalance_pattern"],
            "counterbalance_position": position,
            "arm": arm,
            "replica": replica,
        },
        "shape": {"calls_per_target_token": cell["calls_per_token"]},
        "arm_report": {
            "setting": {
                "before": False,
                "requested": requested,
                "after_set": requested,
                "restored": False,
            },
            "snapshots": items,
            "unique_active_sha256": sorted({item["active_sha256"] for item in items}),
            "unique_tail_sha256": ["tail"],
            "all_tail_numeric_zero": True,
            "latency": {"median": per_call_us * MODULE.ROWS},
        },
        "child_postflight": {"status": "pass"},
    }


class A4aContracts(unittest.TestCase):
    def test_frozen_dependencies_and_catalog(self) -> None:
        self.assertEqual(MODULE.sha256(MODULE.A1_TOOL), MODULE.A1_TOOL_SHA256)
        self.assertEqual(MODULE.sha256(MODULE.A3_TOOL), MODULE.A3_TOOL_SHA256)
        self.assertEqual(MODULE.sha256(MODULE.A3_RESULT), MODULE.A3_RESULT_SHA256)
        MODULE.validate_catalog()
        self.assertEqual(len(MODULE.load_a1().FAMILIES), 14)
        self.assertEqual(
            sum(spec["calls"] for spec in MODULE.load_a1().FAMILIES.values()),
            532,
        )

    def test_only_hc_down_inject_has_a_synthetic_tail(self) -> None:
        for family, spec in MODULE.load_a1().FAMILIES.items():
            expected = 324 if family == "hc_down_inject" else spec["n"]
            self.assertEqual(MODULE.active_columns(family), expected)

    def test_counterbalance_is_exact_and_balanced(self) -> None:
        self.assertEqual(
            [(x["arm"], x["replica"]) for x in MODULE.arm_schedule(0)],
            [
                ("native", 1),
                ("mkldnn-deterministic", 1),
                ("mkldnn-deterministic", 2),
                ("native", 2),
            ],
        )
        self.assertEqual(
            [(x["arm"], x["replica"]) for x in MODULE.arm_schedule(1)],
            [
                ("mkldnn-deterministic", 1),
                ("native", 1),
                ("native", 2),
                ("mkldnn-deterministic", 2),
            ],
        )
        plan = MODULE.process_plan()
        self.assertEqual(len(plan), 112)
        for arm in MODULE.ARMS:
            for position in range(1, 5):
                self.assertEqual(
                    sum(
                        item["arm"] == arm and item["position"] == position
                        for item in plan
                    ),
                    14,
                )

    def test_environment_is_exact(self) -> None:
        self.assertEqual(
            MODULE.verify_environment(dict(MODULE.A4A_ENVIRONMENT)),
            MODULE.A4A_ENVIRONMENT,
        )
        with self.assertRaisesRegex(RuntimeError, "environment drift"):
            MODULE.verify_environment({**MODULE.A4A_ENVIRONMENT, "ONEDNN_VERBOSE": "1"})

    def test_snapshot_preserves_full_active_tail_and_per_row_hashes(self) -> None:
        n = 4
        active_n = 3
        payload = bytearray(MODULE.ROWS * n * 2)
        record = MODULE.snapshot(bytes(payload), n=n, active_n=active_n)
        self.assertEqual(len(record["row_full_sha256"]), MODULE.ROWS)
        self.assertEqual(len(record["row_active_sha256"]), MODULE.ROWS)
        self.assertEqual(len(record["row_tail_sha256"]), MODULE.ROWS)
        self.assertTrue(record["tail_all_numeric_zero"])
        payload[active_n * 2 : active_n * 2 + 2] = bytes.fromhex("803f")
        changed = MODULE.snapshot(bytes(payload), n=n, active_n=active_n)
        self.assertEqual(changed["active_sha256"], record["active_sha256"])
        self.assertNotEqual(changed["full_sha256"], record["full_sha256"])
        self.assertFalse(changed["tail_all_numeric_zero"])

    def test_scientific_variation_does_not_make_a_record_invalid(self) -> None:
        cell = MODULE.canonical_cells()[0]
        schedule = MODULE.arm_schedule(0)
        with mock.patch.object(MODULE, "SWEEPS", 2):
            records = [
                fake_record(
                    cell,
                    arm=item["arm"],
                    replica=item["replica"],
                    position=item["position"],
                    values=(
                        ["authority", "alternate"]
                        if item["arm"] == "native"
                        else ["authority", "authority"]
                    ),
                )
                for item in schedule
            ]
            result = MODULE.summarize_cell(records, cell)
        self.assertTrue(result["native_varies"])
        self.assertTrue(result["candidate_exact_across_processes"])
        self.assertTrue(result["candidate_whole_row_hashes_in_native_support"])
        self.assertTrue(result["exactness_pass"])

    def test_missing_native_row_support_fails_parity(self) -> None:
        cell = MODULE.canonical_cells()[0]
        schedule = MODULE.arm_schedule(0)
        with mock.patch.object(MODULE, "SWEEPS", 1):
            records = [
                fake_record(
                    cell,
                    arm=item["arm"],
                    replica=item["replica"],
                    position=item["position"],
                    values=[
                        "candidate"
                        if item["arm"] == "mkldnn-deterministic"
                        else "native"
                    ],
                )
                for item in schedule
            ]
            result = MODULE.summarize_cell(records, cell)
        self.assertFalse(result["candidate_whole_row_hashes_in_native_support"])
        self.assertEqual(len(result["missing_native_support_rows"]), MODULE.ROWS)
        self.assertFalse(result["exactness_pass"])

    def test_family_cluster_bootstrap_is_deterministic(self) -> None:
        families = [
            {
                "calls_per_token": index + 1,
                "native_median_us": 10.0,
                "candidate_median_us": 9.9,
            }
            for index in range(14)
        ]
        left = MODULE.family_cluster_bootstrap(families, replicates=100)
        right = MODULE.family_cluster_bootstrap(families, replicates=100)
        self.assertEqual(left, right)
        self.assertAlmostEqual(left["one_sided_upper_95_ratio"], 0.99)

    def test_full_summary_weights_exactly_532_calls(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(MODULE, "SWEEPS", 1),
            mock.patch.object(MODULE, "BOOTSTRAP_REPLICATES", 100),
        ):
            root = Path(temporary)
            for planned in MODULE.process_plan():
                directory = MODULE.cell_directory(planned, root=root)
                directory.mkdir(parents=True, exist_ok=True)
                record = fake_record(
                    planned,
                    arm=planned["arm"],
                    replica=planned["replica"],
                    position=planned["position"],
                    per_call_us=(
                        9.9 if planned["arm"] == "mkldnn-deterministic" else 10.0
                    ),
                )
                (
                    directory / MODULE.arm_filename(planned["arm"], planned["replica"])
                ).write_text(json.dumps(record), encoding="utf-8")
            result = MODULE.summarize(root)
        self.assertEqual(result["multiplicity_sum"], 532)
        self.assertAlmostEqual(
            result["weighted_cost_us_per_target_token"]["candidate_native_ratio"],
            0.99,
        )
        self.assertTrue(result["cost_gate"]["passed"])
        self.assertTrue(result["component_candidate_advances"])

    def test_cost_gate_constants_are_exactly_preregistered(self) -> None:
        self.assertEqual(MODULE.CENTRAL_RATIO_MAX, 1.000)
        self.assertEqual(MODULE.BOOTSTRAP_UPPER_95_MAX, 1.010)
        self.assertEqual(MODULE.COUNTERBALANCE_HALF_RATIO_MAX, 1.020)
        self.assertEqual(MODULE.HOT_FAMILY_CALL_THRESHOLD, 12)
        self.assertEqual(MODULE.HOT_FAMILY_POINT_RATIO_MAX, 1.020)
        self.assertEqual(MODULE.BOOTSTRAP_REPLICATES, 10_000)

    def test_setting_scope_precedes_first_gemm(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        start = source.index("def execute_arm")
        scope = source.index("with a3.scoped_mkldnn_deterministic", start)
        first = source.index("a3.timed_ordinal_sweep", scope)
        self.assertLess(scope, first)
        self.assertNotIn("functional.linear", source[start:scope])

    def test_default_plan_is_inert_and_has_no_lifecycle_action(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn('"device_execution": False', source)
        self.assertEqual(MODULE.ROWS, 256)
        self.assertEqual(MODULE.SWEEPS, 100)
        for forbidden in ("vllm serve", "docker", "podman", "reboot", "shutdown"):
            self.assertNotIn(forbidden, source)

    def test_plan_has_one_intentional_pre_cell_admission_receipt(self) -> None:
        source = inspect.getsource(MODULE.run_plan)
        self.assertEqual(source.count("before = a1.validate_admission()"), 1)
        self.assertEqual(source.count("after = a1.validate_admission()"), 1)
        self.assertIn('final_health = {"status": "pass"', source)

    def test_late_pre_cell_health_failure_preserves_plan_status_and_final_health(
        self,
    ) -> None:
        planned = MODULE.process_plan()[:2]
        calls = {"admission": 0}

        def validate_admission():
            calls["admission"] += 1
            if calls["admission"] == 4:
                raise RuntimeError("late pre-cell health failure")
            return {"aer_event_count": 0, "receipt": calls["admission"]}

        def atomic_write(path: Path, value: object) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                raise FileExistsError(path)
            path.write_text(json.dumps(value), encoding="utf-8")

        fake_a1 = type(
            "FakeA1",
            (),
            {
                "validate_admission": staticmethod(validate_admission),
                "verify_static_identity": staticmethod(lambda: {}),
                "refuse_active_accelerator_owner": staticmethod(lambda: None),
            },
        )()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "a4a"
            with (
                mock.patch.object(MODULE, "A4A_ROOT", root),
                mock.patch.object(MODULE, "load_a1", return_value=fake_a1),
                mock.patch.object(MODULE, "validate_catalog", return_value=None),
                mock.patch.object(MODULE, "process_plan", return_value=planned),
                mock.patch.object(
                    MODULE, "sha256", return_value=MODULE.A3_RESULT_SHA256
                ),
                mock.patch.object(MODULE, "atomic_write", side_effect=atomic_write),
                mock.patch.object(MODULE.subprocess, "run", return_value=None),
                mock.patch.dict(
                    MODULE.os.environ, {MODULE.AUTHORITY_ENV: "YES"}, clear=False
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "preserving plan status"):
                    MODULE.run_plan()
            status = json.loads((root / "plan-status.json").read_text())
        self.assertEqual(status["failure_location"]["stage"], "pre_cell_health")
        self.assertEqual(status["failure_location"]["current_process"], planned[1])
        self.assertEqual(status["completed_process_count"], 1)
        self.assertEqual(status["completed_processes"], [planned[0]])
        self.assertEqual(status["final_health"]["status"], "pass")
        self.assertEqual(calls["admission"], 5)


if __name__ == "__main__":
    unittest.main()
