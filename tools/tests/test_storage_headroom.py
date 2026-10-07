"""CPU-only storage admission regressions; fake capacity/mounts, real temp paths."""

import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("storage_headroom", ROOT / "scripts/check-storage-headroom.py")
storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage)


def mount(path, identifier=1):
    return {"mount_point": str(path), "mount_id": identifier,
            "filesystem_type": "ext4", "source": "/dev/test"}


class StorageAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def inspect(self, destination, available=100, reserve=50, planned=50,
                required=None, mounts=None, readonly=False):
        stats = SimpleNamespace(f_bavail=available, f_frsize=1,
                                f_flag=os.ST_RDONLY if readonly else 0)
        with patch.object(storage, "read_mounts", return_value=mounts or [mount("/")]), \
                patch.object(storage.os, "statvfs", return_value=stats) as statvfs:
            result = storage.inspect_destination(destination, reserve, planned, required)
        return result, statvfs.call_args.args[0]

    def test_capacity_includes_output_and_floor_at_exact_boundary(self):
        passed, _ = self.inspect(self.root, available=100)
        failed, _ = self.inspect(self.root, available=99)
        self.assertTrue(passed["admitted"])
        self.assertFalse(failed["admitted"])
        self.assertEqual(passed["remaining_after_planned_write_bytes"], 50)

    def test_missing_output_uses_nearest_existing_parent_without_creating_it(self):
        output = self.root / "new/run/result.json"
        report, checked = self.inspect(output)
        self.assertTrue(report["admitted"])
        self.assertEqual(checked, self.root)
        self.assertFalse((self.root / "new").exists())

    def test_unmounted_external_directory_fails_even_with_capacity(self):
        report, _ = self.inspect(self.root / "new", required=self.root)
        self.assertFalse(report["admitted"])
        self.assertIn("not mounted", report["failures"][0])

    def test_mounted_external_destination_passes(self):
        report, _ = self.inspect(self.root / "new", required=self.root,
                                 mounts=[mount("/"), mount(self.root, 2)])
        self.assertTrue(report["admitted"])
        self.assertEqual(report["filesystem"]["mount_id"], 2)

    def test_symlink_escape_does_not_borrow_external_free_space(self):
        external = self.root / "external"
        external.mkdir()
        (external / "escape").symlink_to(self.root, target_is_directory=True)
        report, checked = self.inspect(external / "escape/output", required=external,
                                       mounts=[mount("/"), mount(external, 2)])
        self.assertFalse(report["admitted"])
        self.assertEqual(checked, self.root)
        self.assertIn("outside required mount", report["failures"][0])

    def test_nested_mount_is_not_the_required_filesystem(self):
        nested = self.root / "nested"
        nested.mkdir()
        report, _ = self.inspect(nested / "new", required=self.root,
                                 mounts=[mount("/"), mount(self.root, 2), mount(nested, 3)])
        self.assertFalse(report["admitted"])
        self.assertIn("different mount", report["failures"][0])

    def test_readonly_filesystem_refused(self):
        report, _ = self.inspect(self.root, readonly=True)
        self.assertFalse(report["admitted"])
        self.assertIn("read-only", report["failures"][0])

    def test_existing_output_file_and_invalid_file_parent(self):
        output = self.root / "file"
        output.touch()
        report, checked = self.inspect(output)
        self.assertTrue(report["admitted"])
        self.assertEqual(checked, output)
        with self.assertRaises(NotADirectoryError):
            self.inspect(output / "child")

    def test_unit_parser_rejects_negative_and_ambiguous_values(self):
        for value in ("-1", "1.5GiB", "50G", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                storage.byte_count(value)
        self.assertEqual(storage.byte_count("50GiB"), 50 * 1024**3)
        self.assertEqual(storage.byte_count("50GB"), 50 * 1000**3)
        self.assertEqual(storage.byte_count("0"), 0)

    def test_mountinfo_escaped_paths(self):
        text = "12 1 8:1 / /media/cold\\040store rw - ext4 /dev/test rw\n"
        with patch.object(storage.Path, "read_text", return_value=text):
            self.assertEqual(storage.read_mounts()[0]["mount_point"], "/media/cold store")

    def test_cli_returns_refusal_and_json(self):
        stats = SimpleNamespace(f_bavail=99, f_frsize=1, f_flag=0)
        output = io.StringIO()
        with patch.object(storage.os, "statvfs", return_value=stats), \
                patch.object(storage, "read_mounts", return_value=[mount("/")]), \
                contextlib.redirect_stdout(output):
            code = storage.main([str(self.root), "--min-free-bytes", "50", "--planned-write-bytes", "50"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["admitted"])

    def test_inspection_error_fails_closed(self):
        output = io.StringIO()
        with patch.object(storage, "read_mounts", side_effect=PermissionError("denied")), \
                contextlib.redirect_stdout(output):
            code = storage.main([str(self.root), "--planned-write-bytes", "0"])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output.getvalue())["admitted"])


if __name__ == "__main__":
    unittest.main()
