#!/usr/bin/env python3
"""Focused tests for validate-recipe-publication.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("validate-recipe-publication.py")
SPEC = importlib.util.spec_from_file_location("validate_recipe_publication", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecipePublicationValidationTest(unittest.TestCase):
    def test_rejects_build_script_digest_disagreement(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "repro/example").mkdir(parents=True)
            (repo / "patches").mkdir()
            patch = repo / "patches/example.patch"
            patch.write_text("actual patch\n")
            build = repo / "repro/example/build.sh"
            build.write_text(
                "#!/usr/bin/env bash\n"
                "patch_file=${repo_root}/patches/example.patch\n"
                f"patch_file_sha256={'0' * 64}\n"
            )
            subprocess.run(
                ["git", "-C", str(repo), "add", "patches/example.patch", "repro/example/build.sh"],
                check=True,
            )
            errors: list[str] = []
            MODULE._validate_build_script(repo, build, errors)
            self.assertTrue(any("digest contract failed" in error for error in errors))

    def test_rejects_untracked_script_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "repro/example").mkdir(parents=True)
            build = repo / "repro/example/build.sh"
            helper = repo / "repro/example/helper.sh"
            build.write_text('#!/usr/bin/env bash\n"${script_dir}/helper.sh"\n')
            helper.write_text("#!/usr/bin/env bash\ntrue\n")
            subprocess.run(["git", "-C", str(repo), "add", "repro/example/build.sh"], check=True)
            errors: list[str] = []
            MODULE._validate_build_script(repo, build, errors)
            self.assertTrue(any("is not tracked" in error for error in errors))

    def test_rejects_published_manifest_without_required_binary_assets(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "repro/example").mkdir(parents=True)
            guide = repo / "repro/example/README.md"
            build = repo / "repro/example/build.sh"
            patch = repo / "repro/example/example.patch"
            evidence = repo / "repro/example/result.json"
            guide.write_text("# Example\n")
            build.write_text("#!/usr/bin/env bash\ntrue\n")
            patch.write_text("patch\n")
            evidence.write_text("{}\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            manifest = self._manifest(MODULE._sha256(patch))
            manifest_path = repo / "repro/example/publication-manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            errors = MODULE.validate_manifest(repo, manifest_path)
            self.assertTrue(any("lacks release kinds" in error for error in errors))

    @staticmethod
    def _manifest(patch_sha256: str) -> dict[str, object]:
        return {
            "format": MODULE.FORMAT,
            "recipe_id": "example",
            "publication_status": "published",
            "guide": "repro/example/README.md",
            "repository": {
                "build_scripts": ["repro/example/build.sh"],
                "immutable_inputs": [{
                    "path": "repro/example/example.patch",
                    "sha256": patch_sha256,
                }],
            },
            "source_repositories": [{
                "url": "https://example.com/source.git",
                "commit": "0" * 40,
            }],
            "release": {
                "tag": "example-v1",
                "url": "https://example.com/releases/example-v1",
                "remote_verified_at": "2026-09-01T00:00:00Z",
                "assets": [{
                    "name": "build.log",
                    "kind": "build-log",
                    "url": "https://example.com/build.log",
                    "sha256": "1" * 64,
                    "size": 1,
                }],
            },
            "binary_sections": {
                "missing.so": {
                    "runpath": "$ORIGIN",
                    "sections": {
                        ".text": "2" * 64,
                        ".rodata": "3" * 64,
                        ".data": "4" * 64,
                        "OFFLOAD_DEVICE_CODE": "5" * 64,
                    },
                }
            },
            "validation": {
                "clean_source_build": True,
                "runtime_smoke": True,
                "quality_gate": True,
                "quality_evidence": ["repro/example/result.json"],
            },
        }


if __name__ == "__main__":
    unittest.main()
