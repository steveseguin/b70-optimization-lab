#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("package-qwen38-runtime-stage.py")
SPEC = importlib.util.spec_from_file_location("package_qwen38_runtime_stage", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class RuntimeStagePackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.stage = self.root / "stage"
        (self.stage / "nested").mkdir(parents=True)
        self.payloads = {
            "module.py": b"VALUE = 7\n",
            "nested/libexample.so": b"tiny-shared-object-fixture\n",
        }
        for relative, payload in self.payloads.items():
            path = self.stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        self.manifest_raw = "".join(
            f"{digest(payload)}  {relative}\n"
            for relative, payload in sorted(self.payloads.items())
        ).encode()
        self.entries = MODULE.parse_sha256_manifest(self.manifest_raw)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_production_manifest_identity_is_frozen(self) -> None:
        raw, entries = MODULE.load_production_manifest()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(), MODULE.EXPECTED_MANIFEST_SHA256
        )
        self.assertEqual(len(entries), 18)

    def test_exact_inventory_and_hashes_pass(self) -> None:
        validated = MODULE.validate_stage(self.stage, self.entries)
        self.assertEqual([item.path for item in validated], sorted(self.payloads))

    def test_extra_runtime_file_fails_closed(self) -> None:
        (self.stage / "unexpected.py").write_text("pass\n", encoding="utf-8")
        with self.assertRaisesRegex(MODULE.StageError, "extra=unexpected.py"):
            MODULE.validate_stage(self.stage, self.entries)

    def test_python_cache_fails_closed(self) -> None:
        cache = self.stage / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-313.pyc").write_bytes(b"cache")
        with self.assertRaisesRegex(MODULE.StageError, "cache artifacts"):
            MODULE.validate_stage(self.stage, self.entries)

    def test_content_mismatch_fails_closed(self) -> None:
        (self.stage / "module.py").write_text("VALUE = 8\n", encoding="utf-8")
        with self.assertRaisesRegex(MODULE.StageError, "SHA-256 mismatch"):
            MODULE.validate_stage(self.stage, self.entries)

    def test_archive_is_deterministic_and_extraction_verifies(self) -> None:
        validated = MODULE.validate_stage(self.stage, self.entries)
        first = self.root / "first.tar"
        second = self.root / "second.tar"
        first_metadata = MODULE.build_archive(
            self.stage, first, self.manifest_raw, validated
        )
        second_metadata = MODULE.build_archive(
            self.stage, second, self.manifest_raw, validated
        )
        self.assertEqual(first_metadata, second_metadata)
        self.assertEqual(digest(first.read_bytes()), digest(second.read_bytes()))
        MODULE.verify_archive_extraction(
            first,
            self.manifest_raw,
            self.entries,
            validated,
            self.root / "verify",
        )

    def test_archive_extra_member_fails_closed(self) -> None:
        validated = MODULE.validate_stage(self.stage, self.entries)
        archive = self.root / "extra.tar"
        MODULE.build_archive(self.stage, archive, self.manifest_raw, validated)
        extra = self.root / "extra.txt"
        extra.write_text("not part of the package\n", encoding="utf-8")
        with tarfile.open(archive, mode="a") as handle:
            handle.add(extra, arcname=f"{MODULE.ARCHIVE_PREFIX}/extra.txt")
        with self.assertRaisesRegex(MODULE.StageError, "inventory/order mismatch"):
            MODULE.verify_archive_extraction(
                archive,
                self.manifest_raw,
                self.entries,
                validated,
                self.root / "verify-extra",
            )

    def test_split_parts_reassemble_and_are_described(self) -> None:
        archive = self.root / "fixture.tar"
        archive.write_bytes(b"0123456789abcdef")
        archive_sha, archive_size, parts = MODULE.split_and_hash_archive(archive, 5)
        self.assertEqual(archive_sha, digest(archive.read_bytes()))
        self.assertEqual(archive_size, 16)
        self.assertEqual([part["size_bytes"] for part in parts], [5, 5, 5, 1])
        rebuilt = b"".join(
            (archive.parent / str(part["name"])).read_bytes() for part in parts
        )
        self.assertEqual(rebuilt, archive.read_bytes())
        for part in parts:
            payload = (archive.parent / str(part["name"])).read_bytes()
            self.assertEqual(part["sha256"], digest(payload))

    def test_metadata_is_canonical_json(self) -> None:
        validated = MODULE.validate_stage(self.stage, self.entries)
        raw = MODULE.canonical_json_bytes(
            MODULE.archive_metadata(digest(self.manifest_raw), validated)
        )
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(json.loads(raw)["file_count"], 2)


if __name__ == "__main__":
    unittest.main()
