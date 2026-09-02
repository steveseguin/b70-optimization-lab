#!/usr/bin/env python3
"""CPU-only contract tests for the Flash-Next BF16 dense census."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


TOOL = Path(__file__).with_name("census-q38-bf16-dense-invariance.py")
SPEC = importlib.util.spec_from_file_location("q38_bf16_dense_census", TOOL)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {TOOL}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CensusContractTests(unittest.TestCase):
    @staticmethod
    def record(cell, *, exact=True, suffix=""):
        return {
            "identity": {
                "family": cell["family"],
                "sentinel": {"id": cell["sentinel"]},
                "seed": cell["seed"],
                "replica": cell["replica"],
                "weight_sha256": "w" * 64,
                "input_sha256": "i" * 64,
                "singleton_authority_sha256": "s" * 64,
            },
            "results": [{"m": 1, "output_sha256": "o" * 64 + suffix}],
            "all_cells_exact": exact,
        }

    def test_a28_catalogue_is_complete(self) -> None:
        MODULE.validate_catalog()
        summary = MODULE.catalog_summary()
        self.assertEqual(summary["family_count"], 14)
        self.assertEqual(summary["calls_per_token"], 532)
        self.assertEqual(
            {row["family"] for row in summary["families"]},
            set(MODULE.FAMILIES),
        )

    def test_exact_a28_multiplicities_are_frozen(self) -> None:
        expected = {
            "hc_down_inject": 96,
            "final_hc_down": 1,
            "hc_up": 97,
            "gdn_qkvz": 36,
            "full_qkv": 12,
            "shared_gate_up": 48,
            "router": 48,
            "qsa_indexer": 12,
            "gdn_ba": 36,
            "shared_gate": 48,
            "shared_down": 48,
            "attn_out": 48,
            "ple_key": 1,
            "ple_value": 1,
        }
        self.assertEqual(
            {name: row["calls"] for name, row in MODULE.FAMILIES.items()}, expected
        )
        self.assertEqual(sum(expected.values()), 532)

    def test_phase1_plan_has_two_fresh_processes_per_seed_and_sentinel(self) -> None:
        plan = MODULE.phase1_plan()
        self.assertEqual(len(plan), 14 * 2 * 3 * 2)
        identities = {
            (row["family"], row["sentinel"], row["seed"], row["replica"])
            for row in plan
        }
        self.assertEqual(len(identities), len(plan))
        self.assertTrue(all(row["m_values"] == list(MODULE.M_VALUES) for row in plan))
        filenames = {MODULE.cell_filename(row) for row in plan}
        self.assertEqual(len(filenames), len(plan))

    def test_m_above_active_scheduler_limit_is_diagnostic_only(self) -> None:
        self.assertEqual(MODULE.PRODUCTION_M_VALUES, (1, 2, 4, 8, 16, 32, 48, 64))
        self.assertEqual(MODULE.DIAGNOSTIC_M_VALUES, (128, 192, 256))
        self.assertTrue(all(m <= 64 for m in MODULE.PRODUCTION_M_VALUES))
        self.assertTrue(all(m > 64 for m in MODULE.DIAGNOSTIC_M_VALUES))

    def test_inverse_permutation_restores_source_order(self) -> None:
        permutation = [2, 0, 3, 1]
        inverse = MODULE.inverse_permutation(permutation)
        permuted = ["a", "b", "c", "d"]
        permuted = [permuted[index] for index in permutation]
        self.assertEqual([permuted[index] for index in inverse], ["a", "b", "c", "d"])
        with self.assertRaisesRegex(ValueError, "not a permutation"):
            MODULE.inverse_permutation([0, 0])

    def test_unknown_or_cross_family_sentinel_fails_closed(self) -> None:
        sentinel = MODULE.resolve_sentinel("gdn_qkvz", "layer00-r0")
        self.assertEqual(sentinel["layer"], 0)
        with self.assertRaisesRegex(ValueError, "unknown family"):
            MODULE.resolve_sentinel("missing", "layer00-r0")
        with self.assertRaisesRegex(ValueError, "unknown sentinel"):
            MODULE.resolve_sentinel("gdn_qkvz", "layer03-r0")

    def test_catalogue_drift_fails_closed(self) -> None:
        drifted = {name: dict(row) for name, row in MODULE.FAMILIES.items()}
        drifted["ple_value"]["calls"] = 2
        with mock.patch.object(MODULE, "FAMILIES", drifted):
            with self.assertRaisesRegex(ValueError, "not 532"):
                MODULE.validate_catalog()

    def test_atomic_evidence_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "result.json"
            MODULE.atomic_write_json(path, {"value": 1})
            self.assertEqual(json.loads(path.read_text()), {"value": 1})
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                MODULE.atomic_write_json(path, {"value": 2})

    def test_plan_emission_is_launch_inert(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn("Q38_BF16_DENSE_CENSUS_EXECUTE", source)
        self.assertIn('if args.command in (None, "plan"):', source)
        self.assertNotIn("docker", source.lower())
        parser = MODULE.build_parser()
        parsed = parser.parse_args(["plan"])
        self.assertEqual(parsed.command, "plan")

    def test_external_checkpoint_mount_is_exact(self) -> None:
        payload = json.dumps(
            {
                "filesystems": [
                    {
                        "source": "/dev/sda2",
                        "fstype": "fuseblk",
                        "target": "/mnt/usb-models",
                    }
                ]
            }
        )
        self.assertEqual(MODULE.parse_findmnt(payload)["source"], "/dev/sda2")
        wrong = payload.replace("/dev/sda2", "/dev/nvme0n1p2")
        with self.assertRaisesRegex(RuntimeError, "mount drift"):
            MODULE.parse_findmnt(wrong)
        self.assertTrue(str(MODULE.MODEL).startswith("/mnt/usb-models/"))

    def test_memory_swap_and_aer_parsers_fail_closed(self) -> None:
        values = MODULE.read_meminfo(
            "MemAvailable: 20000000 kB\nSwapFree: 7000000 kB\n"
        )
        self.assertEqual(values["SwapFree"], 7000000)
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            MODULE.read_meminfo("MemAvailable: 20000000 kB\n")
        self.assertEqual(
            MODULE.count_aer_events(
                "AER: Corrected error\nok\nPCIe Bus Error: severity=Corrected"
            ),
            2,
        )

    def test_admission_precedes_any_evidence_path_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "must-not-exist"
            with (
                mock.patch.object(MODULE, "EVIDENCE_ROOT", root),
                mock.patch.object(
                    MODULE,
                    "validate_admission",
                    side_effect=RuntimeError("no clearance"),
                ),
                mock.patch.dict("os.environ", {"Q38_BF16_DENSE_CENSUS_EXECUTE": "YES"}),
            ):
                with self.assertRaisesRegex(RuntimeError, "no clearance"):
                    MODULE.run_plan()
            self.assertFalse(root.exists())

    def test_runtime_contract_binds_clearance_a28_timeout_and_clean_sources(
        self,
    ) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertIn(MODULE.A28_SUMMARY_SHA256, source)
        self.assertIn("_git_relevant_status", source)
        self.assertIn('"--untracked-files=no"', source)
        self.assertIn("actual mapped runtime libraries", source)
        self.assertIn("timeout=min(CELL_TIMEOUT_SECONDS", source)
        self.assertIn("signal.alarm(CELL_TIMEOUT_SECONDS)", source)
        self.assertEqual(MODULE.CELL_TIMEOUT_SECONDS, 600)
        self.assertEqual(MODULE.PLAN_TIMEOUT_SECONDS, 21600)
        self.assertEqual(
            MODULE.CLEARANCE_VALIDATOR_SHA256, MODULE.sha256(MODULE.CLEARANCE_VALIDATOR)
        )
        self.assertEqual(
            MODULE.sha256(MODULE.MODEL_RECEIPT), MODULE.MODEL_RECEIPT_SHA256
        )
        receipt = json.loads(MODULE.MODEL_RECEIPT.read_text())
        self.assertEqual(
            receipt["contract"]["tree_metadata_sha256"],
            MODULE.MODEL_TREE_METADATA_SHA256,
        )

    def test_source_tensor_catalog_and_shard_contract_fail_closed(self) -> None:
        names = MODULE.source_tensor_names(
            "full_qkv", MODULE.resolve_sentinel("full_qkv", "layer03-r0")
        )
        self.assertEqual(len(names), 3)
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary)
            shard = model / "shard.safetensors"
            shard.write_bytes(b"bound")
            stat = shard.stat()
            contract = {
                "model_index_sha256": MODULE.MODEL_INDEX_SHA256,
                "model_receipt_sha256": "r" * 64,
                "tree_metadata_sha256": MODULE.MODEL_TREE_METADATA_SHA256,
                "shards": {
                    shard.name: {
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "sha256": MODULE.sha256(shard),
                    }
                },
            }
            receipt = model / "receipt.json"
            receipt.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": shard.name,
                                "size": stat.st_size,
                                "digest_kind": "lfs_sha256",
                                "digest": MODULE.sha256(shard),
                            }
                        ]
                    }
                )
            )
            receipt_sha = MODULE.sha256(receipt)
            contract["model_receipt_sha256"] = receipt_sha
            with (
                mock.patch.object(MODULE, "MODEL", model),
                mock.patch.object(MODULE, "MODEL_RECEIPT", receipt),
                mock.patch.object(MODULE, "MODEL_RECEIPT_SHA256", receipt_sha),
            ):
                self.assertEqual(len(MODULE.validate_shard_contract(contract)), 64)
                shard.write_bytes(b"drift")
                with self.assertRaisesRegex(RuntimeError, "stat drift"):
                    MODULE.validate_shard_contract(contract)

    def test_environment_is_allowlisted_and_native_mappings_are_unambiguous(
        self,
    ) -> None:
        clean = MODULE.sanitized_subprocess_environment()
        self.assertEqual(MODULE.verify_worker_environment(clean), clean)
        with self.assertRaisesRegex(RuntimeError, "not sanitized"):
            MODULE.verify_worker_environment({**clean, "DNNL_VERBOSE": "1"})
        with self.assertRaisesRegex(RuntimeError, "ambiguous or absent"):
            MODULE.loaded_native_library_contract(
                "00400000-00401000 r-xp 0 0:0 0 /tmp/none\n"
            )

    def test_expanded_a28_catalog_is_bound_to_all_four_traces(self) -> None:
        MODULE.validate_catalog()
        value = json.loads(MODULE.A28_CATALOG.read_text())
        self.assertEqual(value["family_count"], 14)
        self.assertEqual(sum(row["calls_per_token"] for row in value["families"]), 532)
        self.assertEqual(
            set(value["derivation"]["trace_sha256"]),
            {"rank0", "rank1", "rank2", "rank3"},
        )
        summarizer = (
            MODULE.A28_CATALOG.parent.parent
            / "tools/summarize-tp4-target-decode-kineto.py"
        )
        self.assertEqual(
            MODULE.sha256(summarizer), value["derivation"]["summarizer_sha256"]
        )
        self.assertEqual(
            MODULE.sha256(MODULE.A28_SUMMARY), value["source_summary"]["sha256"]
        )
        self.assertEqual(MODULE.sha256(MODULE.A28_CATALOG), MODULE.A28_CATALOG_SHA256)

    def test_summary_requires_every_planned_cell_and_preserves_negatives(self) -> None:
        plan = MODULE.phase1_plan()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cells = root / "cells"
            cells.mkdir()
            with self.assertRaisesRegex(RuntimeError, "evidence is missing"):
                MODULE.summarize_evidence(root)
            for index, cell in enumerate(plan):
                record = self.record(cell, exact=index != 0)
                (cells / MODULE.cell_filename(cell)).write_text(
                    json.dumps(record), encoding="utf-8"
                )
            summary = MODULE.summarize_evidence(root)
            self.assertEqual(summary["completed_processes"], len(plan))
            self.assertEqual(summary["exact_processes"], len(plan) - 1)
            self.assertFalse(summary["all_phase1_cells_exact"])
            self.assertEqual(len(summary["noninvariant_processes"]), 1)

    def test_summary_rejects_cross_process_and_weight_drift(self) -> None:
        plan = MODULE.phase1_plan()
        with tempfile.TemporaryDirectory() as temporary:
            cells = Path(temporary) / "cells"
            cells.mkdir()
            for cell in plan:
                record = self.record(cell)
                if cell == plan[1]:
                    record["identity"]["singleton_authority_sha256"] = "x" * 64
                    record["identity"]["weight_sha256"] = "y" * 64
                (cells / MODULE.cell_filename(cell)).write_text(json.dumps(record))
            summary = MODULE.summarize_evidence(Path(temporary))
            self.assertFalse(summary["all_phase1_cells_exact"])
            self.assertEqual(len(summary["cross_process_failures"]), 1)
            self.assertEqual(len(summary["reconstructed_weight_failures"]), 1)


if __name__ == "__main__":
    unittest.main()
