#!/usr/bin/env python3
"""Unit checks for the model-intake catalog and safety helpers."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("model-intake.py")
SPEC = importlib.util.spec_from_file_location("model_intake", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODEL_INTAKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODEL_INTAKE)


class ModelIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = MODEL_INTAKE.load_catalog(MODEL_INTAKE.DEFAULT_CATALOG)

    def test_catalog_has_unique_pinned_entries(self) -> None:
        ids = [entry["id"] for entry in self.catalog["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(len(entry["revision"]) == 40 for entry in self.catalog["entries"]))

    def test_first_wave_size_is_stable(self) -> None:
        queued = MODEL_INTAKE.selected_entries(self.catalog, [], True)
        self.assertEqual(sum(entry["artifact"]["size_bytes"] for entry in queued), 59381999680)
        self.assertEqual([entry["priority"] for entry in queued], [1, 2, 3, 4])

    def test_relative_path_rejection(self) -> None:
        for value in ("../model.gguf", "/tmp/model.gguf", "dir\\model.gguf", ""):
            self.assertFalse(MODEL_INTAKE.safe_relative(value))
        self.assertTrue(MODEL_INTAKE.safe_relative("llm-models/example/model.gguf"))

    def test_metadata_only_entry_cannot_be_selected(self) -> None:
        with self.assertRaisesRegex(MODEL_INTAKE.IntakeError, "metadata-only"):
            MODEL_INTAKE.selected_entries(self.catalog, ["ling-30-tiny-bf16"], False)

    def test_malformed_catalog_fails_closed(self) -> None:
        malformed = {
            "format": MODEL_INTAKE.FORMAT,
            "entries": [
                {
                    "id": "bad",
                    "revision": "main",
                    "artifact": {
                        "filename": "../escape.gguf",
                        "size_bytes": 1,
                        "sha256": "0" * 64,
                    },
                    "destination": "llm-models/bad",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(malformed), encoding="utf-8")
            with self.assertRaises(MODEL_INTAKE.IntakeError):
                MODEL_INTAKE.load_catalog(path)

    def test_direct_verifier_manifest(self) -> None:
        entry = MODEL_INTAKE.selected_entries(
            self.catalog, ["ornith-15-9b-q8"], False
        )[0]
        manifest = MODEL_INTAKE.verifier_manifest(entry)
        self.assertEqual(manifest["repository"], entry["repo_id"])
        self.assertEqual(manifest["lfs_files"][0]["sha256"], entry["artifact"]["sha256"])
        self.assertEqual(manifest["small_files"], [])


if __name__ == "__main__":
    unittest.main()
