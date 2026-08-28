#!/usr/bin/env python3
"""Tiny, native-code-free tests for the runtime download installer."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


SCRIPT_PATH = Path(__file__).resolve().with_name("prepare-runtime.py")


def load_tool() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "qwen38_prepare_runtime", SCRIPT_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load prepare-runtime.py")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


TOOL = load_tool()


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def tar_info(name: str, payload: bytes, mode: int = 0o644) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.type = tarfile.REGTYPE
    return info


class Fixture:
    def __init__(self, root: Path, mutation: str = "valid") -> None:
        self.root = root
        self.parts_dir = root / "parts"
        self.parts_dir.mkdir()
        self.work_dir = root / "work"
        self.work_dir.mkdir()
        self.contract_path = root / "runtime-contract.json"
        self.manifest_path = root / "runtime-stage.sha256"
        self.kernel_stage = root / "installed-stage"
        self.receipt_path = root / "install-receipt.json"
        payloads = {"a.py": b"answer = 42\n", "nested/b.so": b"tiny-so-fixture"}
        files = [
            {"path": name, "sha256": digest(payload), "size_bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        ]
        manifest = "".join(
            f"{item['sha256']}  {item['path']}\n" for item in files
        ).encode("utf-8")
        self.manifest_path.write_bytes(manifest)
        archive_name = "fixture.tar"
        prefix = "qwen38-flash-next-runtime-stage"
        contract: dict[str, Any] = {
            "archive": {
                "archive_metadata_sha256": "0" * 64,
                "compression": "none",
                "name": archive_name,
                "prefix": prefix,
                "sha256": "0" * 64,
                "size_bytes": 1,
            },
            "files": files,
            "format": TOOL.CONTRACT_FORMAT,
            "hybrid_runtime": {
                "build_head": "fixture",
                "freshly_rebuilt_file": "nested/b.so",
                "retained_known_loadable_files": 1,
                "statement": "fixture",
            },
            "manifest": {
                "name": "runtime-stage.sha256",
                "sha256": digest(manifest),
                "size_bytes": len(manifest),
            },
            "parts": [],
            "publication": {
                "public_readback_verified": False,
                "status": "not-hosted",
            },
            "status": "pre-publication",
        }
        archive_metadata = TOOL.canonical_json_bytes(
            TOOL.expected_archive_metadata(contract, digest(manifest))
        )
        contract["archive"]["archive_metadata_sha256"] = digest(archive_metadata)
        archive_path = root / archive_name
        with tarfile.open(archive_path, "w", format=tarfile.GNU_FORMAT) as archive:
            members = [
                (f"{prefix}/ARCHIVE-METADATA.json", archive_metadata, 0o644),
                (f"{prefix}/runtime-stage.sha256", manifest, 0o644),
                *[
                    (
                        f"{prefix}/{name}",
                        payload,
                        0o755 if name.endswith(".so") else 0o644,
                    )
                    for name, payload in sorted(payloads.items())
                ],
            ]
            if mutation == "missing":
                members.pop()
            if mutation == "layout":
                name, payload, mode = members[-1]
                members[-1] = (name.replace(prefix, "wrong-prefix", 1), payload, mode)
            if mutation == "extra":
                members.append((f"{prefix}/extra.py", b"extra\n", 0o644))
            if mutation == "traversal":
                members.append(("../escape.py", b"escape\n", 0o644))
            for name, payload, mode in members:
                archive.addfile(tar_info(name, payload, mode), io.BytesIO(payload))

        archive_payload = archive_path.read_bytes()
        split_at = max(1, len(archive_payload) // 2)
        chunks = [archive_payload[:split_at], archive_payload[split_at:]]
        parts = []
        for index, chunk in enumerate(chunks):
            name = f"{archive_name}.part-{index:04d}"
            (self.parts_dir / name).write_bytes(chunk)
            parts.append(
                {
                    "index": index,
                    "name": name,
                    "sha256": digest(chunk),
                    "size_bytes": len(chunk),
                    "url": None,
                }
            )
        contract["parts"] = parts
        contract["archive"]["size_bytes"] = len(archive_payload)
        contract["archive"]["sha256"] = digest(archive_payload)
        if mutation == "reassembly":
            contract["archive"]["sha256"] = "f" * 64
        self.contract_path.write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if mutation == "hash":
            first = self.parts_dir / parts[0]["name"]
            value = bytearray(first.read_bytes())
            value[0] ^= 1
            first.write_bytes(value)

    def install(self) -> dict[str, Any]:
        return TOOL.install_runtime(
            self.contract_path,
            self.manifest_path,
            self.parts_dir,
            self.kernel_stage,
            self.receipt_path,
            self.work_dir,
        )


class RuntimeInstallerTest(unittest.TestCase):
    def fixture(self, mutation: str = "valid") -> Fixture:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Fixture(Path(temporary.name), mutation)

    def assert_failure(self, mutation: str, message: str) -> None:
        fixture = self.fixture(mutation)
        with self.assertRaisesRegex(TOOL.RuntimeStageError, message):
            fixture.install()
        self.assertFalse(fixture.kernel_stage.exists())
        self.assertFalse(fixture.receipt_path.exists())

    def test_valid_reassembly_installs_exact_nested_layout(self) -> None:
        fixture = self.fixture()
        receipt = fixture.install()
        installed = fixture.kernel_stage / "vllm_xpu_kernels"
        self.assertEqual((installed / "a.py").read_bytes(), b"answer = 42\n")
        self.assertEqual((installed / "nested/b.so").read_bytes(), b"tiny-so-fixture")
        self.assertEqual(receipt["status"], "pass")
        self.assertTrue(fixture.receipt_path.is_file())

    def test_production_mode_rejects_substitute_contract(self) -> None:
        fixture = self.fixture()
        with self.assertRaisesRegex(
            TOOL.RuntimeStageError,
            "production install requires the tracked runtime contract",
        ):
            TOOL.install_runtime(
                fixture.contract_path,
                fixture.manifest_path,
                fixture.parts_dir,
                fixture.kernel_stage,
                fixture.receipt_path,
                fixture.work_dir,
                require_frozen=True,
            )
        self.assertFalse(fixture.kernel_stage.exists())
        self.assertFalse(fixture.receipt_path.exists())

    def test_rejects_preexisting_destination(self) -> None:
        fixture = self.fixture()
        fixture.kernel_stage.mkdir()
        marker = fixture.kernel_stage / "owned-by-caller"
        marker.write_text("keep\n", encoding="utf-8")
        with self.assertRaisesRegex(TOOL.RuntimeStageError, "already exists"):
            fixture.install()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")

    def test_rejects_preexisting_receipt(self) -> None:
        fixture = self.fixture()
        fixture.receipt_path.write_text("keep\n", encoding="utf-8")
        with self.assertRaisesRegex(TOOL.RuntimeStageError, "receipt already exists"):
            fixture.install()
        self.assertEqual(fixture.receipt_path.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse(fixture.kernel_stage.exists())

    def test_rejects_traversal_member(self) -> None:
        self.assert_failure("traversal", "unsafe relative path")

    def test_rejects_extra_member(self) -> None:
        self.assert_failure("extra", "archive inventory/order mismatch")

    def test_rejects_missing_member(self) -> None:
        self.assert_failure("missing", "archive inventory/order mismatch")

    def test_rejects_part_hash_mismatch(self) -> None:
        self.assert_failure("hash", "part SHA-256 mismatch")

    def test_rejects_reassembly_hash_mismatch(self) -> None:
        self.assert_failure("reassembly", "reassembled archive SHA-256 mismatch")

    def test_rejects_wrong_archive_layout(self) -> None:
        self.assert_failure("layout", "archive inventory/order mismatch")


if __name__ == "__main__":
    unittest.main()
