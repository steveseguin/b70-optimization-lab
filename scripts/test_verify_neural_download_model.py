#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("verify-neural-download-model.py")
SPEC = importlib.util.spec_from_file_location("verify_neural_download_model", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class VerifyNeuralDownloadModelTest(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, str]:
        model_dir = root / "model"
        model_dir.mkdir()
        payload = b"gguf-test-payload" * 100
        (model_dir / "model.gguf").write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "format": "neural-download-model-manifest-v1",
            "repository": "publisher/model",
            "revision": "0123456789abcdef",
            "files": [{"name": "model.gguf", "sha256": digest}],
        }))
        return model_dir, manifest, digest

    def run_main(self, manifest: Path, model_dir: Path, result: Path) -> int:
        argv = [str(SCRIPT), str(manifest), str(model_dir), "--json", str(result)]
        with mock.patch.object(sys, "argv", argv):
            return VERIFIER.main()

    def test_matching_direct_and_ordinary_views_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            model_dir, manifest, digest = self.fixture(Path(temp))
            result = Path(temp) / "result.json"
            with mock.patch.object(VERIFIER, "hash_direct", return_value=(digest, "mock-direct")):
                self.assertEqual(self.run_main(manifest, model_dir, result), 0)
            parsed = json.loads(result.read_text())
            self.assertEqual(parsed["status"], "verified")
            self.assertTrue(parsed["files"][0]["views_coherent"])

    def test_either_digest_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            model_dir, manifest, _ = self.fixture(Path(temp))
            result = Path(temp) / "result.json"
            with mock.patch.object(
                VERIFIER, "hash_direct", return_value=("0" * 64, "mock-direct")
            ):
                self.assertEqual(self.run_main(manifest, model_dir, result), 1)
            parsed = json.loads(result.read_text())["files"][0]
            self.assertFalse(parsed["direct_ok"])
            self.assertTrue(parsed["ordinary_ok"])
            self.assertFalse(parsed["views_coherent"])

    def test_direct_unavailable_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            model_dir, manifest, _ = self.fixture(Path(temp))
            result = Path(temp) / "result.json"
            with mock.patch.object(
                VERIFIER,
                "hash_direct",
                side_effect=VERIFIER.DirectUnavailable("no direct path"),
            ):
                self.assertEqual(self.run_main(manifest, model_dir, result), 2)
            self.assertEqual(json.loads(result.read_text())["status"], "unverifiable")

    def test_unsafe_or_empty_manifest_fails_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_dir = root / "model"
            model_dir.mkdir()
            result = root / "result.json"
            for files in ([], [{"name": "../escape.gguf", "sha256": "x"}]):
                manifest = root / "manifest.json"
                manifest.write_text(json.dumps({
                    "format": "neural-download-model-manifest-v1",
                    "repository": "publisher/model",
                    "revision": "revision",
                    "files": files,
                }))
                self.assertEqual(self.run_main(manifest, model_dir, result), 3)
                self.assertEqual(json.loads(result.read_text())["status"], "config-error")

    def test_missing_file_or_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_dir, manifest, _ = self.fixture(root)
            result = root / "result.json"
            (model_dir / "model.gguf").unlink()
            self.assertEqual(self.run_main(manifest, model_dir, result), 1)
            self.assertEqual(json.loads(result.read_text())["status"], "mismatch")


if __name__ == "__main__":
    unittest.main()
