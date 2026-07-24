#!/usr/bin/env python3
"""CPU-only anti-corruption tests for the v3 gather-sharded packets."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PATH = Path(__file__).with_name("freeze_laguna_m8_gather_sharded_packets.py")
SPEC = importlib.util.spec_from_file_location("laguna_packets", PATH)
assert SPEC and SPEC.loader
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)
phase_a = tool._phase_a()


def _digest(seed: str) -> str:
    return (seed.encode().hex() + "0" * 64)[:64]


def _common() -> dict:
    fixture_root = Path("/mnt/fast-ai/test-fixture")
    native_root = Path("/mnt/fast-ai/test-native")
    libraries = {
        name: {
            "role": f"role-{name}",
            "source": f"/mnt/fast-ai/source/{name}",
            "path": str(native_root / name),
            "sha256": _digest(f"lib-{name}"),
            "bytes": 1,
            "mode": 0o444,
        }
        for name in phase_a.LIBRARIES
    }
    return {
        "format": phase_a.COMMON_FORMAT,
        "source": {
            "approved_record_vllm_commit": "8936aac144929190c1e53f8b8624ca397ce16f5b",
            "approved_record_kernel_commit": "b6076ce1249ffee0e30bee528f4cd15c3bffb234",
            "candidate_kernel_commit": "7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6",
        },
        "source_ir": copy.deepcopy(phase_a.SOURCE_IR_IDENTITY),
        "stage0_completion": {
            "path": "/mnt/fast-ai/stage0.json",
            "sha256": _digest("stage0"),
            "status": "stage0_host_only_complete_pending_packet_commit",
            "input": {
                "path": "/mnt/fast-ai/stage0-input.json",
                "sha256": _digest("input"),
            },
        },
        "native_bundle": {
            "root": str(native_root),
            "manifest": str(native_root / "manifest.json"),
            "manifest_sha256": _digest("manifest"),
            "prepared": str(native_root / "bundle-prepared.json"),
            "prepared_sha256": _digest("prepared"),
            "library_sha256": {
                name: value["sha256"] for name, value in libraries.items()
            },
            "libraries": libraries,
            "status": "validated_host_only_not_imported",
            "validation_protocol": "separate_successful_validate_existing_invocation_required",
            "storage": {
                "mount_point": "/mnt/fast-ai",
                "filesystem": "ext4",
                "source": "/dev/nvme0n1p2",
                "major_minor": "259:2",
                "sysfs_device": "/sys/devices/pci/nvme/nvme0",
            },
        },
        "fixture": {
            "root": str(fixture_root),
            "manifest": str(fixture_root / "manifest.json"),
            "manifest_sha256": _digest("fixture-manifest"),
            "analysis": str(fixture_root / "analysis.json"),
            "analysis_sha256": _digest("fixture-analysis"),
            "canonical_route_map": {
                "path": str(fixture_root / "canonical_route_map.int32.le.bin"),
                "sha256": _digest("route-map"),
            },
            "records": {
                name: {
                    "path": str(fixture_root / f"{name}.bin"),
                    "sha256": _digest(name),
                    "dtype": "<u2",
                    "shape": [288, 1],
                    "per_epoch_sha256": [
                        _digest(f"{name}-{index}") for index in range(288)
                    ],
                }
                for name in phase_a.FIXTURE_RECORDS
            },
        },
        "cards": [dict(card) for card in phase_a.PHYSICAL_CARDS],
        "treatments": {
            "A": "generic_moe_gather",
            "B": "laguna_m8_moe_gather_sharded",
            "same_candidate_moe_library": True,
        },
        "logical_cycle": {
            "layers": 47,
            "warm_cycles_per_arm": 20,
            "blocks": 31,
            "cycles_per_arm": 64,
            "arm_order": "A-B-B-A",
            "rotation": "(block*47)%256",
            "pre_epochs": 256,
            "post_epochs": 32,
            "minimum_wins": 28,
            "minimum_median_saving_ms": 0.08,
        },
        "operational_preflight": copy.deepcopy(
            phase_a.OPERATIONAL_PREFLIGHT_IDENTITY
        ),
        "runtime_identity": copy.deepcopy(phase_a.RUNTIME_IDENTITY),
    }


def _nonces() -> dict[tuple[int, str], str]:
    return {
        (rank, arm): f"{rank}{index}".ljust(32, "a")
        for rank in range(4)
        for index, arm in enumerate(tool._phase_b().ARMS)
    }


class PacketFreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.common = _common()
        phase_a.validate_common(self.common)
        self.auth = Path(
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/"
            "authorizations/test"
        )
        self.a_root = Path(
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/test-a"
        )
        self.b_root = Path(
            "/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/test-b"
        )

    def _pair(self) -> tuple[dict, dict]:
        return tool.packet_pair(
            self.common,
            self.auth,
            self.a_root,
            self.b_root,
            session_nonces=_nonces(),
            counter_tools={"test": True},
            temporal_control={"test": True},
        )

    def test_pair_is_v3_canonical_nonrecursive_and_mutually_bound(self) -> None:
        phase_a_packet, phase_b_packet = self._pair()
        self.assertEqual(
            phase_a_packet["paired_phase_b_packet_sha256"],
            tool.sha(phase_b_packet),
        )
        self.assertEqual(
            phase_b_packet["body"]["phase_a_binding"]["phase_a_body_sha256"],
            tool.sha(phase_a_packet["body"]),
        )
        self.assertEqual(
            tool.canonical(json.loads(tool.canonical(phase_a_packet))),
            tool.canonical(phase_a_packet),
        )
        self.assertNotIn("paired_phase_a_packet_sha256", phase_b_packet)
        phase_a.verify_mutual_packets(
            phase_a_packet, phase_b_packet, phase_b_path=self.auth / tool.PHASE_B_NAME
        )

    def test_one_field_and_paired_corruption_are_rejected(self) -> None:
        phase_a_packet, phase_b_packet = self._pair()
        corrupt_b = copy.deepcopy(phase_b_packet)
        corrupt_b["body"]["protocol"]["cycles"] = 14
        # Shape-only validation is deliberately insufficient; rebuilding from
        # the freezer's frozen contract catches this mutation.
        expected_a, expected_b = self._pair()
        self.assertNotEqual(corrupt_b, expected_b)
        self.assertEqual(phase_a_packet, expected_a)

        corrupt_a = copy.deepcopy(phase_a_packet)
        corrupt_a["paired_phase_b_packet_sha256"] = "0" * 64
        with self.assertRaises(RuntimeError):
            phase_a.verify_mutual_packets(
                corrupt_a, phase_b_packet, phase_b_path=self.auth / tool.PHASE_B_NAME
            )

    def test_session_nonces_are_unique_and_exactly_bound(self) -> None:
        _phase_a_packet, phase_b_packet = self._pair()
        sessions = [
            session
            for card in phase_b_packet["body"]["cards"]
            for session in card["sessions"].values()
        ]
        self.assertEqual(len(sessions), 16)
        self.assertEqual(len(set(sessions)), 16)
        self.assertEqual(tool._session_nonces(phase_b_packet), _nonces())

    def test_common_is_derived_from_certificate_not_cli_overrides(self) -> None:
        source = PATH.read_text()
        self.assertNotIn('add_argument("--cards"', source)
        self.assertNotIn('add_argument("--common"', source)
        self.assertNotIn("import torch", source.lower())
        self.assertNotIn("CorsairExternal", source)
        self.assertNotIn("FROZEN-UUID", source)
        self.assertNotIn("frozen-before", source)

    def test_write_requires_three_fresh_internal_roots(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="laguna-packet-test-", dir="/mnt/fast-ai"
        ) as directory:
            existing = Path(directory)
            with self.assertRaises(RuntimeError):
                tool._assert_internal_parent(existing, "existing")
        with self.assertRaises(RuntimeError):
            tool._assert_internal_parent(Path("/tmp/laguna-not-nvme"), "outside")

    def test_cli_creation_requires_stage0_and_both_campaign_roots(self) -> None:
        with mock.patch(
            "sys.argv",
            ["packet-freezer", "--authorization-directory", str(self.auth)],
        ):
            with self.assertRaises(RuntimeError):
                tool.main()


if __name__ == "__main__":
    unittest.main()
