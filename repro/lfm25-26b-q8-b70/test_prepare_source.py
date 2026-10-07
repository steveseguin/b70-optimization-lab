"""CPU-only acceptance checks; no public network, compiler, model or device."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("prepare_source", Path(__file__).with_name("prepare-source.py"))
PREP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)


class SourcePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def fixture(self, entries=None):
        entries = entries or [("p/a.txt", b"original source\n", tarfile.REGTYPE),
                              ("p/nested/tool", b"#!/bin/sh\nexit 0\n", tarfile.REGTYPE)]
        archive = self.root / "input.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name, data, kind in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.mode = 0o755 if name.endswith("tool") else 0o644
                member.size = len(data) if kind == tarfile.REGTYPE else 0
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = "/tmp/outside"
                tar.addfile(member, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        manifest = {"revision": "1" * 40, "archive": {"prefix": "p", "members": len(entries),
                    "bytes": archive.stat().st_size, "sha256": PREP.sha256(archive),
                    "file_bytes": sum(len(data) for _, data, kind in entries if kind == tarfile.REGTYPE)},
                    "critical_files": {}}
        return archive, manifest

    def run_prepare(self, archive, manifest, output=None):
        return PREP.prepare(manifest, output or self.root / "source", archive_path=archive, min_free_bytes=0)

    def test_clean_offline_source_bytes_modes_and_receipt(self):
        archive, manifest = self.fixture()
        manifest["critical_files"]["a.txt"] = hashlib.sha256(b"original source\n").hexdigest()
        with mock.patch.object(PREP.urllib.request, "urlopen", side_effect=AssertionError("offline means no network")):
            receipt = self.run_prepare(archive, manifest)
        self.assertEqual((self.root / "source/a.txt").read_bytes(), b"original source\n")
        self.assertTrue((self.root / "source/nested/tool").stat().st_mode & 0o111)
        self.assertEqual(receipt["source_files"], 2)
        self.assertFalse(receipt["build_performed"])
        self.assertFalse(receipt["runtime_qualified"])
        for item in receipt["files"]:
            self.assertEqual(PREP.sha256(self.root / "source" / item["path"]), item["sha256"])
        self.assertEqual(json.loads((self.root / "source/SOURCE-PREPARATION.json").read_text()), receipt)

    def test_archive_corruption_refused_before_output(self):
        archive, manifest = self.fixture()
        raw = bytearray(archive.read_bytes()); raw[-1] ^= 1; archive.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.run_prepare(archive, manifest)
        self.assertFalse((self.root / "source").exists())

    def test_wrong_census_refused_before_output(self):
        archive, manifest = self.fixture()
        manifest["archive"]["members"] += 1
        with self.assertRaisesRegex(ValueError, "census"):
            self.run_prepare(archive, manifest)
        self.assertFalse((self.root / "source").exists())

    def test_unsafe_members_refused_before_output(self):
        for name, kind in [("p/../escape", tarfile.REGTYPE), ("/p/absolute", tarfile.REGTYPE),
                           ("p/link", tarfile.SYMTYPE), ("p/hard", tarfile.LNKTYPE), ("p/fifo", tarfile.FIFOTYPE)]:
            with self.subTest(name=name):
                archive, manifest = self.fixture([(name, b"unsafe", kind)])
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    self.run_prepare(archive, manifest)
                self.assertFalse((self.root / "source").exists())

    def test_duplicate_and_file_parent_refused(self):
        for names in [("p/a", "p/a"), ("p/a", "p/a/b")]:
            archive, manifest = self.fixture([(name, b"x", tarfile.REGTYPE) for name in names])
            with self.assertRaisesRegex(ValueError, "duplicate|file used"):
                self.run_prepare(archive, manifest)
            self.assertFalse((self.root / "source").exists())

    def test_existing_output_is_preserved(self):
        archive, manifest = self.fixture()
        output = self.root / "source"; output.mkdir(); (output / "keep").write_text("keep")
        with self.assertRaisesRegex(ValueError, "absent"):
            self.run_prepare(archive, manifest)
        self.assertEqual((output / "keep").read_text(), "keep")

    def test_symlink_ancestor_and_archive_refused(self):
        archive, manifest = self.fixture()
        alias = self.root / "alias"; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.run_prepare(archive, manifest, alias / "source")
        linked = self.root / "linked.tar.gz"; linked.symlink_to(archive)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.run_prepare(linked, manifest)

    def test_low_space_refuses_before_temporary_or_output_writes(self):
        archive, manifest = self.fixture()
        fs = mock.Mock(f_flag=0, f_frsize=4096, f_bsize=4096, f_bavail=1)
        with mock.patch.object(PREP.os, "statvfs", return_value=fs), mock.patch.object(PREP.tempfile, "TemporaryDirectory") as scratch:
            with self.assertRaisesRegex(ValueError, "insufficient"):
                self.run_prepare(archive, manifest)
            scratch.assert_not_called()

    def test_preparation_cap_and_negative_reserve_refused(self):
        archive, manifest = self.fixture()
        manifest["archive"]["file_bytes"] = PREP.MAX_ADDITIONAL_BYTES
        with self.assertRaisesRegex(ValueError, "512 MiB"):
            self.run_prepare(archive, manifest)
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            PREP.prepare(manifest, self.root / "source", archive_path=archive, min_free_bytes=-1)

    def test_wrong_critical_pin_never_records_success(self):
        archive, manifest = self.fixture()
        manifest["critical_files"]["a.txt"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "critical"):
            self.run_prepare(archive, manifest)
        self.assertTrue((self.root / "source/a.txt").exists())  # inspectable partial output
        self.assertFalse((self.root / "source/SOURCE-PREPARATION.json").exists())

    def test_download_has_size_bound_and_no_automatic_retry(self):
        response = io.BytesIO(b"too much data")
        response.url = "https://example.invalid/archive"
        with mock.patch.object(PREP.urllib.request, "urlopen", return_value=response) as request:
            with self.assertRaisesRegex(ValueError, "size or time"):
                PREP.download({"url": response.url, "bytes": 1}, self.root / "oversized")
            self.assertEqual(request.call_count, 1)
        self.assertEqual((self.root / "oversized").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
