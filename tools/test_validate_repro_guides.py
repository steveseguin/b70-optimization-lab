#!/usr/bin/env python3
"""Focused tests for validate-repro-guides.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
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
        self.assertEqual(sum(counts.values()), 41)

    def test_video_observations_require_real_evidence_and_valid_timing(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / 'timing.json').write_text('{}')
            observation = {
                'scope': 'Early window, not a full-run median', 'evidence': 'timing.json',
                'headline_row_label': 'Measured setup', 'rows': [
                    {'label': 'Measured setup', 'status': 'Early window', 'period_seconds': 5.2415,
                     'new_video_seconds': 6, 'samples': 52, 'evidence': 'timing.json'},
                    {'label': 'Unmeasured setup', 'status': 'No timing retained', 'period_seconds': None,
                     'new_video_seconds': 6, 'samples': None, 'evidence': 'timing.json'},
                ],
            }
            self.assertEqual(MODULE._validate_video_measurements(repo, 'example', observation), [])
            observation['headline_row_label'] = 'Unmeasured setup'
            self.assertTrue(any('headline_row_label' in error for error in MODULE._validate_video_measurements(repo, 'example', observation)))
            observation['headline_row_label'] = 'Measured setup'
            for invalid in (0, -1, True, float('nan'), float('inf')):
                observation['rows'][0]['period_seconds'] = invalid
                self.assertTrue(any('positive finite' in error for error in MODULE._validate_video_measurements(repo, 'example', observation)))
            observation['rows'][0]['period_seconds'] = 5.2415
            observation['rows'][0]['evidence'] = 'missing.json'
            self.assertTrue(any('does not resolve' in error for error in MODULE._validate_video_measurements(repo, 'example', observation)))

    def test_video_row_receipts_must_be_declared_dependencies(self):
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            guide = 'repro/example/README.md'
            (repo / 'repro/example').mkdir(parents=True)
            (repo / guide).write_text('# Example')
            (repo / 'model.json').write_text('{}')
            (repo / 'timing.json').write_text('{}')
            (repo / 'row.json').write_text('{}')
            package = {
                'format': MODULE.PACKAGE_FORMAT, 'id': 'example', 'guide': guide,
                'audience': 'expert', 'clean_host_tested': False, 'status': 'candidate',
                'hardware': {'cards': 4}, 'model': {'revision': '0' * 40, 'manifest': 'model.json'},
                'runtime': {'kind': 'native'}, 'project_patches': {'required': False, 'items': []},
                'commands': {name: 'true' for name in MODULE.PACKAGE_COMMANDS},
                'dependencies': [guide, 'model.json', 'timing.json'], 'missing': ['clean host replay'],
                'library': {
                    **{name: 'Example' for name in ('model_family', 'publisher', 'variant', 'summary', 'quantization', 'runtime_label')},
                    'operating_systems': ['Linux'], 'delivery': ['native'], 'modalities': ['video'],
                    'use_cases': ['video'], 'tags': ['video'], 'published_at': '2026-10-10',
                    'featured_metric': None, 'benchmark_status': 'Pending',
                },
                'contributors': [{'id': 'lab', 'name': 'Lab', 'contribution': 'Timing', 'validated_effect': 'Scoped timing',
                                  'kind': 'lab', 'status': 'credited', 'profile': 'https://example.org', 'evidence': 'timing.json'}],
                'video_measurements': {'scope': 'Early window', 'evidence': 'timing.json', 'rows': [
                    {'label': 'Measured setup', 'status': 'Early window', 'period_seconds': 5.24,
                     'samples': 52, 'evidence': 'row.json'}]},
            }
            path = repo / 'package.json'
            path.write_text(json.dumps(package))
            errors = MODULE._validate_package(repo, 'package.json', self._entry(guide))
            self.assertEqual(len(errors), 1, errors)
            self.assertIn('video_measurements.rows[0].evidence must be declared in dependencies', errors[0])
            package['dependencies'].append('row.json')
            path.write_text(json.dumps(package))
            self.assertEqual(MODULE._validate_package(repo, 'package.json', self._entry(guide)), [])

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

    def test_rejects_untracked_dependency_in_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("tracked\n")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            untracked = repo / "untracked.txt"
            untracked.write_text("not public\n")
            errors = MODULE._validate_internal_dependency(repo, "example", "untracked.txt")
            self.assertTrue(any("is not tracked" in error for error in errors))

    def test_dependency_declaration_accepts_parent_directory(self) -> None:
        dependencies = {"repro/example"}
        self.assertTrue(
            MODULE._dependency_is_declared("repro/example/run.sh", dependencies)
        )
        self.assertFalse(
            MODULE._dependency_is_declared("scripts/run.sh", dependencies)
        )

    def test_entrypoint_closure_requires_called_helper(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "repro/example").mkdir(parents=True)
            run = repo / "repro/example/run.sh"
            helper = repo / "repro/example/helper.sh"
            run.write_text('#!/usr/bin/env bash\n"${script_dir}/helper.sh"\n')
            helper.write_text("#!/usr/bin/env bash\ntrue\n")
            commands = {
                "launch": "repro/example/run.sh",
            }
            errors = MODULE._validate_package_entrypoint_closure(
                repo,
                "packages/example/package.json",
                commands,
                {"repro/example/run.sh"},
            )
            self.assertTrue(any("helper.sh" in error for error in errors))
            self.assertEqual(
                MODULE._validate_package_entrypoint_closure(
                    repo,
                    "packages/example/package.json",
                    commands,
                    {"repro/example/run.sh", "repro/example/helper.sh"},
                ),
                [],
            )

    def test_entrypoint_closure_rejects_missing_called_helper(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            (repo / "repro/example").mkdir(parents=True)
            run = repo / "repro/example/run.sh"
            run.write_text('#!/usr/bin/env bash\n"${script_dir}/missing-helper.sh"\n')
            errors = MODULE._validate_package_entrypoint_closure(
                repo,
                "packages/example/package.json",
                {"launch": "repro/example/run.sh"},
                {"repro/example/run.sh", "repro/example/missing-helper.sh"},
            )
            self.assertTrue(any("missing-helper.sh" in error for error in errors))
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
            package["commands"]["launch"] = "/home/alice/bin/run-model"
            (repo / package_path).write_text(json.dumps(package))
            (repo / "repro/guide-catalog.json").write_text(
                json.dumps({"format": MODULE.FORMAT, "guides": [entry]})
            )
            errors, _ = MODULE.validate(repo)
            self.assertTrue(any("pinned by sha256 digest" in error for error in errors))
            self.assertTrue(
                any("commands.launch contains a host-local path" in error for error in errors)
            )

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
