#!/usr/bin/env python3
"""CPU-only contracts for the A2 BF16 singleton diagnostic."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


TOOL = Path(__file__).with_name("diagnose-q38-bf16-singleton-a2.py")
SPEC = importlib.util.spec_from_file_location("q38_bf16_singleton_a2", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class A2Contracts(unittest.TestCase):
    def _summarize_identity_pair(
        self,
        *,
        left_input: str = "input-a",
        right_input: str = "input-a",
        left_weight: str = "weight-a",
        right_weight: str = "weight-a",
    ) -> dict:
        def record(input_sha256: str, weight_sha256: str) -> dict:
            return {
                "identity": {
                    "input_sha256": input_sha256,
                    "weight_sha256": weight_sha256,
                },
                "cold_a1_style_pair": {"arm": "cold"},
                "immediate_row_snapshot": {"arm": "immediate"},
                "warmed_a1_style_deferred_cat": {"arm": "deferred"},
                "fixed_row_repeats": {"arm": "focus"},
            }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "replica1.json").write_text(
                MODULE.json.dumps(record(left_input, left_weight)),
                encoding="utf-8",
            )
            (root / "replica2.json").write_text(
                MODULE.json.dumps(record(right_input, right_weight)),
                encoding="utf-8",
            )
            with mock.patch.object(
                MODULE,
                "infer_conclusion",
                side_effect=AssertionError("cross-identity records must not infer"),
            ) as inference:
                summary = MODULE.summarize(root)
            inference.assert_not_called()
            return summary

    def test_frozen_first_a1_cell_identity(self) -> None:
        self.assertEqual(MODULE.FAMILY, "hc_down_inject")
        self.assertEqual(MODULE.SENTINEL, "layer00-attn-r0")
        self.assertEqual(MODULE.SEED, 2026090201)
        self.assertEqual(MODULE.REPLICAS, (1, 2))
        self.assertEqual(MODULE.sha256(MODULE.A1_TOOL), MODULE.A1_TOOL_SHA256)
        self.assertEqual(
            MODULE.sha256(MODULE.SHARD_CONTRACT), MODULE.SHARD_CONTRACT_FILE_SHA256
        )
        contract = MODULE.json.loads(MODULE.SHARD_CONTRACT.read_text())
        self.assertEqual(
            MODULE.load_a1().canonical_sha256(contract), MODULE.SHARD_CONTRACT_SHA256
        )

    def test_environment_is_exact_and_rejects_extra_gemm_selector(self) -> None:
        self.assertEqual(
            MODULE.verify_environment(dict(MODULE.A2_ENVIRONMENT)),
            MODULE.A2_ENVIRONMENT,
        )
        with self.assertRaisesRegex(RuntimeError, "environment drift"):
            MODULE.verify_environment({**MODULE.A2_ENVIRONMENT, "DNNL_VERBOSE": "1"})

    def test_bf16_comparison_localizes_rows_elements_and_bits(self) -> None:
        reference = bytes.fromhex("0000000000000000")
        candidate = bytes.fromhex("000000000000803f")
        result = MODULE.compare_bf16(reference, candidate, rows=2, cols=2)
        self.assertFalse(result["exact"])
        self.assertEqual(result["differing_elements"], 1)
        self.assertEqual(result["differing_rows"], [1])
        self.assertEqual(result["first_differences"][0]["col"], 1)
        self.assertEqual(
            result["regions"]["active_columns_0_324"]["differing_elements"], 1
        )
        self.assertEqual(
            result["regions"]["active_columns_0_324"]["per_row_differences"]["1"][
                "differing_elements"
            ],
            1,
        )
        with self.assertRaisesRegex(ValueError, "length"):
            MODULE.compare_bf16(b"", b"", rows=1, cols=1)

    def test_protocol_records_every_invocation_and_row(self) -> None:
        values = [bytes.fromhex("00000000"), bytes.fromhex("0000803f")]
        result = MODULE.classify_protocol(values, rows=1, cols=2)
        self.assertEqual(len(result["invocations"]), 2)
        self.assertEqual(len(result["invocations"][0]["row_sha256"]), 1)
        self.assertEqual(
            result["comparisons_to_invocation0"][0]["differing_elements"], 1
        )
        self.assertEqual(len(result["unique_invocation_sha256"]), 2)

    def test_active_and_synthetic_padding_regions_are_separate(self) -> None:
        reference = bytes(MODULE.COLS * 2)
        tail = bytearray(reference)
        tail[MODULE.ACTIVE_COLS * 2 : MODULE.ACTIVE_COLS * 2 + 2] = bytes.fromhex(
            "803f"
        )
        result = MODULE.compare_bf16(reference, bytes(tail), rows=1, cols=MODULE.COLS)
        self.assertTrue(result["regions"]["active_columns_0_324"]["exact"])
        padding = result["regions"]["synthetic_padding_columns_324_336"]
        self.assertFalse(padding["exact"])
        self.assertEqual(padding["differing_cols"], [324])
        record = MODULE.snapshot_record(bytes(tail), rows=1, cols=MODULE.COLS)
        self.assertIn("active_columns_0_324_sha256", record)
        self.assertIn("synthetic_padding_columns_324_336_sha256", record)
        self.assertIn("row_active_columns_0_324_sha256", record)
        self.assertIn("row_synthetic_padding_columns_324_336_sha256", record)
        self.assertFalse(record["synthetic_padding_all_numeric_zero"])
        self.assertEqual(record["synthetic_padding_first_nonzero"][0]["col"], 324)

    def test_nonfinite_snapshot_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "non-finite"):
            MODULE.validate_snapshot(bytes.fromhex("807f"), rows=1, cols=1)

    def test_atomic_evidence_is_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            MODULE.atomic_write(path, {"value": 1})
            with self.assertRaisesRegex(FileExistsError, "refusing overwrite"):
                MODULE.atomic_write(path, {"value": 2})

    def test_conclusion_separates_arithmetic_from_deferred_lifetime(self) -> None:
        base = bytes(MODULE.COLS * 2)

        def changed(col: int) -> bytes:
            value = bytearray(base)
            value[col * 2 : col * 2 + 2] = bytes.fromhex("803f")
            return bytes(value)

        def protocol(candidate: bytes):
            return MODULE.classify_protocol([base, candidate], rows=1, cols=MODULE.COLS)

        def record(*, cold=base, immediate=base, deferred=base, focus=base):
            return {
                "cold_a1_style_pair": protocol(cold),
                "immediate_row_snapshot": protocol(immediate),
                "warmed_a1_style_deferred_cat": protocol(deferred),
                "fixed_row_repeats": {"0": protocol(focus)},
            }

        self.assertEqual(
            MODULE.infer_conclusion([record(immediate=changed(0))]),
            "genuine_warmed_m1_flinear_active_output_repeatability_failure",
        )
        self.assertEqual(
            MODULE.infer_conclusion([record(deferred=changed(0))]),
            "warmed_deferred_queue_or_buffer_lifetime_active_output_failure",
        )
        self.assertEqual(
            MODULE.infer_conclusion([record(cold=changed(0))]),
            "cold_start_active_output_instability_not_reproduced_when_warm",
        )
        self.assertEqual(
            MODULE.infer_conclusion([record(cold=changed(324))]),
            "synthetic_padding_tail_only_instability_not_production_output_nondeterminism",
        )
        self.assertEqual(
            MODULE.infer_conclusion([record()]),
            "a1_mismatch_not_reproduced_in_bounded_a2",
        )

    def test_worker_error_still_writes_envelope_and_child_postflight(self) -> None:
        fake_a1 = SimpleNamespace(validate_admission=lambda: {"status": "pass"})
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(MODULE, "A2_ROOT", Path(temporary)),
            mock.patch.object(
                MODULE, "run_cell", side_effect=RuntimeError("diagnostic failure")
            ),
            mock.patch.object(MODULE, "load_a1", return_value=fake_a1),
        ):
            with self.assertRaisesRegex(RuntimeError, "preserving"):
                MODULE.run_cell_enveloped(1)
            value = MODULE.json.loads((Path(temporary) / "replica1.json").read_text())
            self.assertEqual(value["status"], "diagnostic_error")
            self.assertEqual(value["child_postflight"]["status"], "pass")

    def test_parent_postflight_runs_even_when_child_fails(self) -> None:
        fake_a1 = SimpleNamespace(
            validate_admission=lambda: {"aer_event_count": 0},
            verify_static_identity=lambda: None,
            refuse_active_accelerator_owner=lambda: None,
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(MODULE, "A2_ROOT", Path(temporary) / "a2"),
            mock.patch.object(MODULE, "load_a1", return_value=fake_a1),
            mock.patch.object(
                MODULE.subprocess, "run", side_effect=RuntimeError("child failed")
            ),
            mock.patch.dict(MODULE.os.environ, {MODULE.AUTHORITY_ENV: "YES"}),
        ):
            with self.assertRaisesRegex(RuntimeError, "parent postflight preserved"):
                MODULE.run_plan()
            receipt = MODULE.A2_ROOT / "parent-postflight-replica1.json"
            self.assertTrue(receipt.is_file())

    def test_cross_process_input_drift_blocks_interpretation(self) -> None:
        summary = self._summarize_identity_pair(right_input="input-b")
        self.assertEqual(summary["status"], "diagnostic_error")
        self.assertFalse(summary["identity_exact_across_processes"])
        self.assertFalse(summary["identity_comparisons"]["input_sha256"])
        self.assertTrue(summary["identity_comparisons"]["weight_sha256"])
        self.assertEqual(
            summary["diagnostic_conclusion"],
            "identity_drift_no_interpretation",
        )

    def test_cross_process_weight_drift_blocks_interpretation(self) -> None:
        summary = self._summarize_identity_pair(right_weight="weight-b")
        self.assertEqual(summary["status"], "diagnostic_error")
        self.assertFalse(summary["identity_exact_across_processes"])
        self.assertTrue(summary["identity_comparisons"]["input_sha256"])
        self.assertFalse(summary["identity_comparisons"]["weight_sha256"])
        self.assertEqual(
            summary["diagnostic_conclusion"],
            "identity_drift_no_interpretation",
        )

    def test_plan_is_inert_and_execution_is_bounded(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn("signal.alarm(CELL_TIMEOUT_SECONDS)", source)
        self.assertIn("timeout=min(", source)
        self.assertEqual(MODULE.CELL_TIMEOUT_SECONDS, 600)
        self.assertEqual(MODULE.PLAN_TIMEOUT_SECONDS, 1500)
        parsed = MODULE.argparse.ArgumentParser()
        self.assertIsNotNone(parsed)

    def test_cold_pair_precedes_all_warmed_gemm_arms_and_runtime_checks_exist(
        self,
    ) -> None:
        source = TOOL.read_text(encoding="utf-8")
        cold = source.index("cold_a1_pair = []")
        immediate = source.index("immediate = []")
        deferred = source.index("deferred_warm = []")
        focus = source.index("focus = {}")
        self.assertGreater(source.index("F.linear", cold), cold)
        self.assertEqual(source.index("F.linear"), source.index("F.linear", cold))
        self.assertLess(cold, immediate)
        self.assertLess(cold, deferred)
        self.assertLess(cold, focus)
        self.assertIn("torch.__version__ != a1.TORCH_VERSION", source)
        self.assertIn("TORCH_BUILD_CONFIG_SHA256", source)
        self.assertIn("safetensors.__version__", source)
        self.assertIn("native_pre_gemm = native_map_snapshot()", source)
        self.assertIn('"contract": a1.loaded_native_library_contract()', source)
        self.assertIn("shape/dtype drift", source)
        self.assertIn("non-finite BF16", source)


if __name__ == "__main__":
    unittest.main()
