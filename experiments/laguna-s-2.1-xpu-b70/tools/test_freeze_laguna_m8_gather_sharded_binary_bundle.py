#!/usr/bin/env python3
"""CPU-only tests for the sharded-gather native-bundle freezer."""

from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import freeze_laguna_m8_gather_sharded_binary_bundle as freezer


class BinaryBundleTests(unittest.TestCase):
    def _sources(
        self, parent: Path
    ) -> tuple[dict[str, dict[str, str]], dict[str, bytes]]:
        payloads = {
            "shared-_C.abi3.so": b"shared-c",
            "shared-_xpu_C.abi3.so": b"shared-xpu-c",
            "candidate-_moe_C.abi3.so": b"candidate-moe-c",
            "libgdn_attn_kernels_xe_2.so": b"gdn",
            "libgrouped_gemm_xe_2.so": b"grouped-two",
            "libgrouped_gemm_xe_default.so": b"grouped-default",
            "libmhc_kernels_xe_2.so": b"mhc",
            "libmqa_logits_kernels_xe_2.so": b"mqa",
        }
        sources = parent / "sources"
        sources.mkdir()
        entries: dict[str, dict[str, str]] = {}
        for name, payload in payloads.items():
            path = sources / name
            path.write_bytes(payload)
            entries[name] = {
                "role": f"test-{name}",
                "source": str(path),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        return entries, payloads

    def _freeze(
        self, temporary: Path
    ) -> tuple[Path, dict[str, bytes], dict[str, object]]:
        binary_parent = temporary / "binaries"
        binary_parent.mkdir()
        entries, payloads = self._sources(temporary)
        destination = binary_parent / "bundle"
        with mock.patch.object(freezer, "BINARY_PARENT", binary_parent):
            summary = freezer.freeze(
                destination,
                entries,
                storage_attestor=lambda _path: {
                    "filesystem": "ext4",
                    "source": "/dev/nvme-test",
                    "major_minor": "1:2",
                    "mount_point": str(temporary),
                    "sysfs_device": "/sys/devices/test/nvme0",
                },
            )
        return destination, payloads, summary

    def test_freezes_exact_read_only_libraries_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination, payloads, summary = self._freeze(Path(directory))
            self.assertEqual(summary["status"], "frozen_host_only_not_imported")
            for name, payload in payloads.items():
                path = destination / name
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(path.stat().st_mode & 0o777, 0o444)
            raw = (destination / "manifest.json").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), summary["manifest_sha256"])
            manifest = json.loads(raw)
            self.assertEqual(manifest["actions_not_performed"][0], "Torch import")
            self.assertEqual(destination.stat().st_mode & 0o777, 0o555)

    def test_rejects_source_digest_drift_and_preserves_partial_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            binary_parent = temporary / "binaries"
            binary_parent.mkdir()
            entries, _payloads = self._sources(temporary)
            entries["candidate-_moe_C.abi3.so"]["sha256"] = "0" * 64
            destination = binary_parent / "bundle"
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                self.assertRaisesRegex(RuntimeError, "digest drift"),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: {},
                )
            self.assertTrue(destination.is_dir())
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                self.assertRaisesRegex(RuntimeError, "bundle exists"),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: {},
                )

    def test_rejects_alias_or_wrong_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            binary_parent = temporary / "binaries"
            binary_parent.mkdir()
            entries, _payloads = self._sources(temporary)
            destination = binary_parent / "bundle"
            destination.symlink_to(binary_parent)
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                self.assertRaises(RuntimeError),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: {},
                )
            destination.unlink()
            entries.pop("shared-_C.abi3.so")
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                self.assertRaisesRegex(RuntimeError, "inventory drift"),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: {},
                )

    def test_module_has_no_accelerator_import(self) -> None:
        tree = ast.parse(Path(freezer.__file__).read_text())
        names = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        names.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
            for alias in node.names
        )
        self.assertFalse(
            any(
                name.split(".")[0]
                in {"torch", "vllm", "vllm_xpu_kernels", "intel_extension_for_pytorch"}
                for name in names
            )
        )


if __name__ == "__main__":
    unittest.main()
