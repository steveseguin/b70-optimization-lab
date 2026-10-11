#!/usr/bin/env python3
"""CPU-only integrity and no-clobber tests for research source restoration."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "restore_sources", Path(__file__).with_name("restore-source-archives.py"))
restore_sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore_sources)


class SourceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = "patches/example/negative.patch"
        self.content = b"retained research\n"
        self.archive = self.root / "sources.tar.xz"
        self.make_archive([(self.name, self.content)])
        self.manifest = {
            "schema": "b70-source-archive-v1",
            "archive": {"file": self.archive.name, "size": self.archive.stat().st_size,
                        "sha256": restore_sources.digest(self.archive)},
            "members": [{"path": self.name, "size": len(self.content),
                         "sha256": hashlib.sha256(self.content).hexdigest()}],
        }
        self.manifest_path = self.root / "manifest.json"
        self.write_manifest()

    def make_archive(self, entries):
        with tarfile.open(self.archive, "w:xz") as archive:
            for name, content in entries:
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def load(self):
        return restore_sources.load_manifest(self.manifest_path)

    def test_exact_restore_and_idempotence(self):
        manifest, members = self.load()
        restore_sources.verify_archive(self.archive, manifest, members)
        destination = self.root / "restored"
        with patch.object(restore_sources.subprocess, "run") as admission:
            self.assertEqual(1, restore_sources.restore(
                self.archive, members, destination, set(members)))
            admission.assert_called_once()
            self.assertIn("50GiB", admission.call_args.args[0])
            self.assertEqual(0, restore_sources.restore(
                self.archive, members, destination, set(members)))
        self.assertEqual(self.content, (destination / self.name).read_bytes())

    def test_different_file_is_never_overwritten(self):
        _, members = self.load()
        target = self.root / "restored" / self.name
        target.parent.mkdir(parents=True)
        target.write_bytes(b"user work")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            restore_sources.restore(self.archive, members, self.root / "restored", set(members))
        self.assertEqual(b"user work", target.read_bytes())

    def test_archive_hash_corruption(self):
        manifest, members = self.load()
        with self.archive.open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "archive size/hash"):
            restore_sources.verify_archive(self.archive, manifest, members)

    def test_member_hash_corruption(self):
        manifest, members = self.load()
        members[self.name]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "member hash"):
            restore_sources.verify_archive(self.archive, manifest, members)

    def test_missing_or_duplicate_member(self):
        for entries in ([], [(self.name, self.content), (self.name, self.content)]):
            with self.subTest(entries=len(entries)):
                self.make_archive(entries)
                self.manifest["archive"].update(size=self.archive.stat().st_size,
                                               sha256=restore_sources.digest(self.archive))
                self.write_manifest()
                manifest, members = self.load()
                with self.assertRaises(ValueError):
                    restore_sources.verify_archive(self.archive, manifest, members)

    def test_unsafe_manifest_path(self):
        for name in ("../escape", "patches/../../escape", "/absolute", "patches/a/../b"):
            with self.subTest(name=name):
                self.manifest["members"][0]["path"] = name
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    self.load()

    def test_symlink_parent_is_rejected(self):
        _, members = self.load()
        destination = self.root / "restored"
        destination.mkdir()
        (destination / "patches").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            restore_sources.restore(self.archive, members, destination, set(members))

    def test_second_pass_missing_member_fails(self):
        _, members = self.load()
        self.make_archive([])
        with patch.object(restore_sources.subprocess, "run"):
            with self.assertRaisesRegex(ValueError, "disappeared"):
                restore_sources.restore(self.archive, members, self.root / "restored", set(members))

    def test_second_pass_duplicate_or_changed_size_fails(self):
        _, members = self.load()
        cases = [[(self.name, b"wrong size")],
                 [(self.name, self.content), (self.name, self.content)]]
        for i, entries in enumerate(cases):
            with self.subTest(case=i):
                self.make_archive(entries)
                with patch.object(restore_sources.subprocess, "run"):
                    with self.assertRaisesRegex(ValueError, "changed during"):
                        restore_sources.restore(self.archive, members, self.root / str(i), set(members))

    def test_external_mount_admission_argument(self):
        _, members = self.load()
        with patch.object(restore_sources.subprocess, "run") as admission:
            restore_sources.restore(self.archive, members, self.root / "restored", set(members),
                                    require_mount=Path("/mnt/archive"))
        self.assertEqual(["--require-mount", "/mnt/archive"], admission.call_args.args[0][-2:])


if __name__ == "__main__":
    unittest.main()
