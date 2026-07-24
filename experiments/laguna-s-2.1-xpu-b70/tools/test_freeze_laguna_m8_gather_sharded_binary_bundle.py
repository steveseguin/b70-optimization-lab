#!/usr/bin/env python3
"""CPU-only tests for the sharded-gather native-bundle freezer."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import freeze_laguna_m8_gather_sharded_binary_bundle as freezer


class BinaryBundleTests(unittest.TestCase):
    STORAGE = {
        "filesystem": "ext4",
        "source": "/dev/nvme0n1p2",
        "major_minor": "259:2",
        "mount_point": "/",
        "sysfs_device": "/sys/devices/pci/nvme0/nvme0n1",
    }

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
                storage_attestor=lambda _path: dict(self.STORAGE),
            )
        return destination, payloads, summary

    def test_freezes_exact_read_only_libraries_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination, payloads, summary = self._freeze(Path(directory))
            self.assertEqual(
                summary["status"],
                "prepared_requires_separate_validation",
            )
            for name, payload in payloads.items():
                path = destination / name
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual(path.stat().st_mode & 0o777, 0o444)
            raw = (destination / "manifest.json").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), summary["manifest_sha256"])
            manifest = json.loads(raw)
            self.assertEqual(manifest["actions_not_performed"][0], "Torch import")
            self.assertEqual((destination / freezer.MANIFEST_NAME).stat().st_mode & 0o777, 0o444)
            self.assertEqual((destination / freezer.PREPARED_NAME).stat().st_mode & 0o777, 0o444)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o555)
            with mock.patch.object(
                freezer,
                "BINARY_PARENT",
                destination.parent,
            ):
                validated = freezer.validate_bundle(
                    destination,
                    {
                        name: {
                            "role": f"test-{name}",
                            "source": str(destination.parent.parent / "sources" / name),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                        }
                        for name, payload in payloads.items()
                    },
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertEqual(
                validated["status"],
                "validated_host_only_not_imported",
            )

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
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertTrue(destination.is_dir())
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                self.assertRaisesRegex(RuntimeError, "bundle exists"),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
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
                    storage_attestor=lambda _path: dict(self.STORAGE),
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
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )

    def test_missing_completion_or_mode_drift_is_not_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            destination, _payloads, _summary = self._freeze(temporary)
            binary_parent = temporary / "binaries"
            second = temporary / "second"
            second.mkdir()
            entries, _unused = self._sources(second)
            (destination / freezer.PREPARED_NAME).chmod(0o644)
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                self.assertRaisesRegex(RuntimeError, "metadata file"),
            ):
                freezer.validate_bundle(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )

    def test_early_fsync_failure_leaves_no_prepared_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            binary_parent = temporary / "binaries"
            binary_parent.mkdir()
            entries, _payloads = self._sources(temporary)
            destination = binary_parent / "bundle"
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                mock.patch.object(
                    freezer.os,
                    "fsync",
                    side_effect=OSError("injected fsync failure"),
                ),
                self.assertRaises(OSError),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertTrue(destination.is_dir())
            self.assertFalse((destination / freezer.PREPARED_NAME).exists())

    def test_late_root_chmod_failure_cannot_validate_as_prepared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            binary_parent = temporary / "binaries"
            binary_parent.mkdir()
            entries, _payloads = self._sources(temporary)
            destination = binary_parent / "bundle"
            real_fchmod = os.fchmod

            def fail_root_read_only(descriptor: int, mode: int) -> None:
                if stat.S_ISDIR(os.fstat(descriptor).st_mode) and mode == 0o555:
                    raise OSError("injected root chmod failure")
                real_fchmod(descriptor, mode)

            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                mock.patch.object(
                    freezer.os,
                    "fchmod",
                    side_effect=fail_root_read_only,
                ),
                self.assertRaises(OSError),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertTrue((destination / freezer.PREPARED_NAME).is_file())
            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                self.assertRaisesRegex(RuntimeError, "root mode drift"),
            ):
                freezer.validate_bundle(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )

    def test_late_prepare_failure_requires_separate_successful_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            binary_parent = temporary / "binaries"
            binary_parent.mkdir()
            entries, _payloads = self._sources(temporary)
            destination = binary_parent / "bundle"
            real_fsync = os.fsync
            injected = False

            def fail_final_parent_once(descriptor: int) -> None:
                nonlocal injected
                target = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
                ready = (
                    target == binary_parent
                    and (destination / freezer.PREPARED_NAME).is_file()
                    and destination.stat().st_mode & 0o777 == 0o555
                )
                if ready and not injected:
                    injected = True
                    raise OSError("injected final parent fsync failure")
                real_fsync(descriptor)

            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                mock.patch.object(
                    freezer.os,
                    "fsync",
                    side_effect=fail_final_parent_once,
                ),
                self.assertRaises(OSError),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertTrue(injected)
            # The failed preparation is not authorized by its visible marker.
            # A new invocation must reopen and revalidate every member.
            with mock.patch.object(freezer, "BINARY_PARENT", binary_parent):
                recovered = freezer.validate_bundle(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertEqual(
                recovered["status"],
                "validated_host_only_not_imported",
            )
            self.assertEqual(
                recovered["validation_protocol"],
                "separate_successful_validate_existing_invocation_required",
            )

    def test_final_root_fsync_failure_also_requires_separate_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            binary_parent = temporary / "binaries"
            binary_parent.mkdir()
            entries, _payloads = self._sources(temporary)
            destination = binary_parent / "bundle"
            real_fsync = os.fsync
            injected = False

            def fail_final_root_once(descriptor: int) -> None:
                nonlocal injected
                target = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
                ready = (
                    target == destination
                    and (destination / freezer.PREPARED_NAME).is_file()
                    and destination.stat().st_mode & 0o777 == 0o555
                )
                if ready and not injected:
                    injected = True
                    raise OSError("injected final root fsync failure")
                real_fsync(descriptor)

            with (
                mock.patch.object(freezer, "BINARY_PARENT", binary_parent),
                mock.patch.object(
                    freezer.os,
                    "fsync",
                    side_effect=fail_final_root_once,
                ),
                self.assertRaises(OSError),
            ):
                freezer.freeze(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertTrue(injected)
            with mock.patch.object(freezer, "BINARY_PARENT", binary_parent):
                recovered = freezer.validate_bundle(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            self.assertEqual(
                recovered["status"],
                "validated_host_only_not_imported",
            )

    def test_validator_rejects_each_member_corruption(self) -> None:
        for corrupted in sorted(freezer.BUNDLE_FILENAMES):
            with self.subTest(member=corrupted), tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory)
                destination, payloads, _summary = self._freeze(temporary)
                path = destination / corrupted
                path.chmod(0o644)
                path.write_bytes(payloads[corrupted] + b"-corrupt")
                path.chmod(0o444)
                entries = {
                    name: {
                        "role": f"test-{name}",
                        "source": str(temporary / "sources" / name),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                    for name, payload in payloads.items()
                }
                with (
                    mock.patch.object(
                        freezer,
                        "BINARY_PARENT",
                        destination.parent,
                    ),
                    self.assertRaisesRegex(RuntimeError, "digest drift"),
                ):
                    freezer.validate_bundle(
                        destination,
                        entries,
                        storage_attestor=lambda _path: dict(self.STORAGE),
                    )

    def test_validator_rejects_inventory_manifest_and_storage_corruption(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            destination, payloads, _summary = self._freeze(temporary)
            entries = {
                name: {
                    "role": f"test-{name}",
                    "source": str(temporary / "sources" / name),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
                for name, payload in payloads.items()
            }
            destination.chmod(0o755)
            (destination / "unexpected.so").write_bytes(b"unexpected")
            destination.chmod(0o555)
            with (
                mock.patch.object(freezer, "BINARY_PARENT", destination.parent),
                self.assertRaisesRegex(RuntimeError, "inventory drift"),
            ):
                freezer.validate_bundle(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            destination, payloads, _summary = self._freeze(temporary)
            entries = {
                name: {
                    "role": f"test-{name}",
                    "source": str(temporary / "sources" / name),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
                for name, payload in payloads.items()
            }
            manifest = destination / freezer.MANIFEST_NAME
            manifest.chmod(0o644)
            value = json.loads(manifest.read_bytes())
            value["status"] = "corrupt"
            manifest.write_bytes(freezer.canonical(value))
            manifest.chmod(0o444)
            with (
                mock.patch.object(freezer, "BINARY_PARENT", destination.parent),
                self.assertRaisesRegex(RuntimeError, "manifest identity drift"),
            ):
                freezer.validate_bundle(
                    destination,
                    entries,
                    storage_attestor=lambda _path: dict(self.STORAGE),
                )
            bad_storage = {
                **self.STORAGE,
                "source": "/dev/sda2",
            }
            with (
                mock.patch.object(freezer, "BINARY_PARENT", destination.parent),
                self.assertRaisesRegex(RuntimeError, "internal NVMe"),
            ):
                freezer.validate_bundle(
                    destination,
                    entries,
                    storage_attestor=lambda _path: bad_storage,
                )

    def test_module_has_no_accelerator_import(self) -> None:
        for path in (
            Path(freezer.__file__),
            Path(freezer.operational.__file__),
        ):
            tree = ast.parse(path.read_text())
            names = [
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            ]
            names.extend(
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            )
            self.assertFalse(
                any(
                    name.split(".")[0]
                    in {
                        "torch",
                        "vllm",
                        "vllm_xpu_kernels",
                        "intel_extension_for_pytorch",
                    }
                    for name in names
                )
            )


if __name__ == "__main__":
    unittest.main()
