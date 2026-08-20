#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).with_name("verify-model-direct.py")
SPEC = importlib.util.spec_from_file_location("verify_model_direct", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class VerifyModelDirectTest(unittest.TestCase):
    def _fixture(self, root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        model = root / "model"
        model.mkdir()
        payload = b"model-bytes" * 1000
        (model / "weights.bin").write_bytes(payload)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "repository": "test/model",
            "revision": "0123456789abcdef",
            "lfs_files": [{
                "path": "weights.bin",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }],
            "small_files": [],
        }))
        return model, manifest

    def _run(self, manifest: pathlib.Path, model: pathlib.Path,
             result: pathlib.Path) -> int:
        argv = [str(SCRIPT), str(manifest), str(model), "--json", str(result)]
        with mock.patch.object(sys, "argv", argv):
            return VERIFIER.main()

    def test_good_direct_and_ordinary_paths_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model, manifest = self._fixture(root)
            result = root / "result.json"
            rc = self._run(manifest, model, result)
            self.assertEqual(rc, 0)
            parsed = json.loads(result.read_text())
            self.assertEqual(parsed["status"], "verified")
            self.assertTrue(parsed["files"][0]["paths_coherent"])

    def test_cache_path_mismatch_fails_even_when_direct_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model, manifest = self._fixture(root)
            result = root / "result.json"
            expected = json.loads(manifest.read_text())["lfs_files"][0]["sha256"]
            def direct_ok(_path, _algorithm, modes):
                modes.append("mock-direct")
                return expected
            with mock.patch.object(
                VERIFIER, "hash_bypassing_cache", side_effect=direct_ok
            ), mock.patch.object(
                VERIFIER, "hash_ordinary", return_value="0" * 64
            ):
                rc = self._run(manifest, model, result)
            self.assertEqual(rc, 1)
            parsed = json.loads(result.read_text())
            self.assertEqual(parsed["status"], "mismatch")
            self.assertTrue(parsed["files"][0]["direct_ok"])
            self.assertFalse(parsed["files"][0]["ordinary_ok"])
            self.assertFalse(parsed["files"][0]["paths_coherent"])

    def test_direct_mismatch_fails_even_when_cache_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model, manifest = self._fixture(root)
            result = root / "result.json"
            def direct_bad(_path, _algorithm, modes):
                modes.append("mock-direct")
                return "0" * 64
            with mock.patch.object(
                VERIFIER, "hash_bypassing_cache", side_effect=direct_bad
            ):
                rc = self._run(manifest, model, result)
            self.assertEqual(rc, 1)
            parsed = json.loads(result.read_text())
            self.assertFalse(parsed["files"][0]["direct_ok"])
            self.assertTrue(parsed["files"][0]["ordinary_ok"])
            self.assertFalse(parsed["files"][0]["paths_coherent"])

    def test_direct_unavailable_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model, manifest = self._fixture(root)
            result = root / "result.json"
            with mock.patch.object(
                VERIFIER,
                "hash_bypassing_cache",
                side_effect=VERIFIER.DirectUnavailable("no direct path"),
            ):
                rc = self._run(manifest, model, result)
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(result.read_text())["status"], "unverifiable")

    def test_empty_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model = root / "model"
            model.mkdir()
            manifest = root / "manifest.json"
            manifest.write_text("{}")
            result = root / "result.json"
            rc = self._run(manifest, model, result)
            self.assertEqual(rc, 3)
            parsed = json.loads(result.read_text())
            self.assertEqual(parsed["status"], "config-error")
            self.assertIn("lfs_files must be a list", parsed["errors"])

    def test_malformed_manifest_entry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model = root / "model"
            model.mkdir()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "repository": "test/model",
                "revision": "0123456789abcdef",
                "lfs_files": [{
                    "path": "../escape.bin",
                    "bytes": -1,
                    "sha256": "not-a-digest",
                }],
                "small_files": [],
            }))
            result = root / "result.json"
            rc = self._run(manifest, model, result)
            self.assertEqual(rc, 3)
            self.assertEqual(json.loads(result.read_text())["status"], "config-error")

    def test_missing_or_wrong_size_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model, manifest = self._fixture(root)
            parsed = json.loads(manifest.read_text())
            parsed["lfs_files"].append({
                "path": "missing.bin",
                "bytes": 1,
                "sha256": hashlib.sha256(b"x").hexdigest(),
            })
            parsed["lfs_files"][0]["bytes"] += 1
            manifest.write_text(json.dumps(parsed))
            result = root / "result.json"
            rc = self._run(manifest, model, result)
            self.assertEqual(rc, 1)
            errors = [item["error"] for item in json.loads(
                result.read_text()
            )["files"]]
            self.assertTrue(any(error.startswith("size ") for error in errors))
            self.assertIn("missing", errors)

    def test_malformed_json_and_missing_json_argument_fail_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model = root / "model"
            model.mkdir()
            manifest = root / "manifest.json"
            manifest.write_text("{")
            result = root / "result.json"
            self.assertEqual(self._run(manifest, model, result), 3)
            self.assertEqual(
                json.loads(result.read_text())["status"], "config-error"
            )
            with mock.patch.object(
                sys, "argv", [str(SCRIPT), str(manifest), str(model), "--json"]
            ):
                self.assertEqual(VERIFIER.main(), 3)

    def test_small_git_blob_is_verified_in_both_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            model = root / "model"
            model.mkdir()
            weight_payload = b"w"
            small_payload = b"small-config"
            (model / "weights.bin").write_bytes(weight_payload)
            (model / "config.json").write_bytes(small_payload)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "repository": "test/model",
                "revision": "0123456789abcdef",
                "lfs_files": [{
                    "path": "weights.bin",
                    "bytes": len(weight_payload),
                    "sha256": hashlib.sha256(weight_payload).hexdigest(),
                }],
                "small_files": [{
                    "path": "config.json",
                    "bytes": len(small_payload),
                    "git_blob": VERIFIER.git_blob_digest(small_payload),
                }],
            }))
            result = root / "result.json"

            def direct_bytes(path, modes):
                modes.append("mock-direct")
                return pathlib.Path(path).read_bytes()

            with mock.patch.object(
                VERIFIER, "read_bytes_bypassing_cache", side_effect=direct_bytes
            ):
                rc = self._run(manifest, model, result)
            self.assertEqual(rc, 0)
            parsed = json.loads(result.read_text())
            small = next(
                item for item in parsed["files"]
                if item["section"] == "small_files"
            )
            self.assertTrue(small["ok"])


if __name__ == "__main__":
    unittest.main()
