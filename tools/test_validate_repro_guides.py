#!/usr/bin/env python3
"""Focused tests for validate-repro-guides.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("validate-repro-guides.py")
SPEC = importlib.util.spec_from_file_location("validate_repro_guides", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReproGuideValidationTest(unittest.TestCase):
    def test_repository_catalog_is_valid(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        errors, counts = MODULE.validate(repo)
        self.assertEqual(errors, [])
        self.assertEqual(sum(counts.values()), 29)

    def test_rejects_uncertified_read_guide_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            guide = "repro/example/README.md"
            (repo / "repro/example").mkdir(parents=True)
            (repo / guide).write_text("# Example\n")
            (repo / "index.html").write_text(f'<a href="{guide}">Read guide</a>')
            catalog = {
                "format": MODULE.FORMAT,
                "guides": [self._entry(guide)],
            }
            (repo / "repro/guide-catalog.json").write_text(json.dumps(catalog))
            errors, _ = MODULE.validate(repo)
            self.assertTrue(any("not a certified starter-guide" in error for error in errors))

    def test_rejects_missing_internal_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            guide = "repro/example/README.md"
            (repo / "repro/example").mkdir(parents=True)
            (repo / guide).write_text("# Example\n")
            (repo / "index.html").write_text("")
            entry = self._entry(guide)
            entry["dependency_links"] = ["patches/missing.patch"]
            (repo / "repro/guide-catalog.json").write_text(
                json.dumps({"format": MODULE.FORMAT, "guides": [entry]})
            )
            errors, _ = MODULE.validate(repo)
            self.assertTrue(any("does not resolve" in error for error in errors))

    def test_rejects_mutable_container_package(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            guide = "repro/example/README.md"
            package_path = "packages/example/package.json"
            (repo / "repro/example").mkdir(parents=True)
            (repo / "packages/example").mkdir(parents=True)
            (repo / guide).write_text("# Example\n")
            (repo / "index.html").write_text("")
            manifest = repo / "repro/example/model.json"
            manifest.write_text("{}")
            entry = self._entry(guide)
            entry["package"] = package_path
            package = {
                "format": MODULE.PACKAGE_FORMAT,
                "id": "example",
                "name": "Example",
                "status": "candidate",
                "audience": "expert",
                "guide": guide,
                "clean_host_tested": False,
                "hardware": {"cards": 1},
                "model": {"revision": "0" * 40, "manifest": manifest.relative_to(repo).as_posix()},
                "runtime": {"kind": "container", "image": "example:latest"},
                "project_patches": {"required": False, "items": []},
                "commands": {name: "true" for name in MODULE.PACKAGE_COMMANDS},
                "dependencies": [guide],
                "missing": ["clean-host replay"],
            }
            (repo / package_path).write_text(json.dumps(package))
            (repo / "repro/guide-catalog.json").write_text(
                json.dumps({"format": MODULE.FORMAT, "guides": [entry]})
            )
            errors, _ = MODULE.validate(repo)
            self.assertTrue(any("pinned by sha256 digest" in error for error in errors))

    def test_rejects_stale_generated_package_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "repro").mkdir()
            (repo / "packages").mkdir()
            (repo / "packages/README.md").write_text("# Packages\n")
            (repo / "packages/catalog.json").write_text("{}\n")
            (repo / "index.html").write_text("")
            (repo / "repro/guide-catalog.json").write_text(
                json.dumps({"format": MODULE.FORMAT, "guides": []})
            )
            errors, _ = MODULE.validate(repo)
            self.assertTrue(any("catalog.json is stale" in error for error in errors))

    def test_rejects_unordered_or_unlinked_performance_profile(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            profiles = [{
                "id": "decode-context",
                "label": "Decode over context",
                "metric": "decode",
                "unit": "tok/s",
                "x_label": "Active context tokens",
                "scope": "Two measured rows",
                "evidence": "data/missing.json",
                "points": [
                    {"context_tokens": 4096, "value": 10.0, "samples": 1},
                    {"context_tokens": 2048, "value": 11.0, "samples": 1},
                ],
            }]
            errors = MODULE._validate_performance_profiles(repo, "example", profiles)
            self.assertTrue(any("does not resolve" in error for error in errors))
            self.assertTrue(any("unique, increasing" in error for error in errors))

    def test_performance_profile_accepts_measured_zero_depth(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "data").mkdir()
            (repo / "data/measured.json").write_text("{}\n")
            profiles = [{
                "id": "decode-context",
                "label": "Decode over context",
                "metric": "decode",
                "unit": "tok/s",
                "x_label": "Existing context depth",
                "scope": "Measured zero and 2K depths",
                "evidence": "data/measured.json",
                "points": [
                    {"context_tokens": 0, "value": 12.0, "samples": 5},
                    {"context_tokens": 2048, "value": 11.0, "samples": 5},
                ],
            }]
            self.assertEqual(
                MODULE._validate_performance_profiles(repo, "example", profiles), []
            )

    def test_performance_profile_accepts_measured_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "data").mkdir()
            (repo / "data/measured.json").write_text("{}\n")
            profiles = [{
                "id": "aggregate-concurrency",
                "label": "Aggregate decode over concurrent sequences",
                "metric": "aggregate_decode",
                "unit": "tok/s",
                "x_metric": "concurrent_sequences",
                "x_label": "Concurrent engine sequences",
                "scope": "Two raw-engine measured rows",
                "evidence": "data/measured.json",
                "points": [
                    {"concurrent_sequences": 1, "value": 100.0, "per_user_value": 100.0},
                    {"concurrent_sequences": 4, "value": 120.0, "per_user_value": 30.0},
                ],
            }]
            self.assertEqual(
                MODULE._validate_performance_profiles(repo, "example", profiles), []
            )

    def test_performance_profile_accepts_measured_speculative_depth(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "data").mkdir()
            (repo / "data/measured.json").write_text("{}\n")
            profiles = [{
                "id": "decode-speculative-depth",
                "label": "Decode by MTP mode",
                "metric": "decode",
                "unit": "tok/s",
                "x_metric": "speculative_tokens",
                "x_label": "Requested speculative tokens",
                "scope": "Three directly measured modes",
                "evidence": "data/measured.json",
                "points": [
                    {"speculative_tokens": 0, "value": 35.0, "samples": 1},
                    {"speculative_tokens": 1, "value": 61.0, "samples": 1},
                    {"speculative_tokens": 2, "value": 83.0, "samples": 1},
                ],
            }]
            self.assertEqual(
                MODULE._validate_performance_profiles(repo, "example", profiles), []
            )

    @staticmethod
    def _entry(guide: str) -> dict[str, object]:
        return {
            "id": "example",
            "guide": guide,
            "classification": "lab-replay",
            "audience": "expert",
            "clean_host_tested": False,
            "components": {name: False for name in MODULE.COMPONENTS},
            "dependency_links": [],
            "missing": ["clean-host replay"],
        }


if __name__ == "__main__":
    unittest.main()
