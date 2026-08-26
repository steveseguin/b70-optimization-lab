#!/usr/bin/env python3
"""Offline regression tests for the repository Git-bundle inventory guard."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("validate-git-bundle-inventory.py")
SPEC = importlib.util.spec_from_file_location("validate_git_bundle_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BundleInventoryRepositoryTest(unittest.TestCase):
    def test_checked_in_inventory_covers_all_published_bundles_offline(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        result = MODULE.validate_inventory(
            repo / "data/git-bundle-portability-inventory-v1.json",
            repo_root=repo,
        )
        self.assertEqual(result["bundle_count"], 54)
        self.assertEqual(result["legacy_frozen_count"], 53)
        self.assertEqual(result["manifest_backed_count"], 1)
        self.assertEqual(result["public_remote_proofs"], 0)
        self.assertFalse(result["network_used"])


class BundleInventoryPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = self.root / "patches"
        self.patches.mkdir()
        self.source = self.root / "source"
        self.public = self.root / "public.git"
        self._git("init", "-q", "-b", "main", str(self.source), cwd=self.root)
        self._git("init", "--bare", "-q", str(self.public), cwd=self.root)
        self._git("config", "user.name", "Bundle Inventory Test", cwd=self.source)
        self._git("config", "user.email", "bundle@example.invalid", cwd=self.source)

        (self.source / "base.txt").write_text("public base\n")
        self._git("add", "base.txt", cwd=self.source)
        self._git("commit", "-q", "-m", "base", cwd=self.source)
        self.base = self._git("rev-parse", "HEAD", cwd=self.source)
        self.base_tree = self._git("show", "-s", "--format=%T", self.base, cwd=self.source)
        self._git("remote", "add", "origin", str(self.public), cwd=self.source)
        self._git("push", "-q", "origin", "main", cwd=self.source)

        self.legacy = self.patches / "legacy.bundle"
        self._git("bundle", "create", str(self.legacy), "HEAD", cwd=self.source)

        (self.source / "record.txt").write_text("private record\n")
        self._git("add", "record.txt", cwd=self.source)
        self._git("commit", "-q", "-m", "record", cwd=self.source)
        self.record = self._git("rev-parse", "HEAD", cwd=self.source)
        self.record_tree = self._git("show", "-s", "--format=%T", self.record, cwd=self.source)
        self.record_ref = "refs/tags/example-record"
        self._git("tag", "example-record", self.record, cwd=self.source)
        self._git("push", "-q", "origin", self.record_ref, cwd=self.source)
        self.thin = self.patches / "thin.bundle"
        self._git(
            "bundle",
            "create",
            str(self.thin),
            self.record_ref,
            f"^{self.base}",
            cwd=self.source,
        )

        self.manifest_path = self.patches / "thin.provenance.json"
        self.manifest = {
            "schema": MODULE.MANIFEST_SCHEMA,
            "bundle": self.thin.name,
            "bundle_sha256": self._sha256(self.thin),
            "bundle_size": self.thin.stat().st_size,
            "classification": "thin-public-prerequisite",
            "expected_ref": self.record_ref,
            "expected_tip": self.record,
            "expected_tree": self.record_tree,
            "prerequisites": [
                {
                    "commit": self.base,
                    "tree": self.base_tree,
                    "public_remote": "https://example.invalid/public.git",
                    "provenance_remote_name": "origin",
                    "provenance_ref": "refs/remotes/origin/main",
                }
            ],
            "included_commits": [],
            "public_recovery_refs": [
                {
                    "role": "record",
                    "public_remote": "https://example.invalid/public.git",
                    "ref": self.record_ref,
                    "commit": self.record,
                    "tree": self.record_tree,
                }
            ],
        }
        self._write_json(self.manifest_path, self.manifest)

        self.entries = [
            self._entry(
                self.legacy,
                "legacy-self-contained",
                "synthetic frozen legacy fixture",
            ),
            self._entry(
                self.thin,
                "manifest-backed-thin-public-prerequisite",
                "synthetic manifest-backed fixture",
                manifest=self.manifest_path,
            ),
        ]
        self.entries.sort(key=lambda entry: entry["path"])
        self.legacy_digest = MODULE._canonical_legacy(
            [entry for entry in self.entries if entry["classification"].startswith("legacy-")]
        )
        self.saved_legacy_digest = MODULE.FROZEN_LEGACY_ALLOWLIST_SHA256
        MODULE.FROZEN_LEGACY_ALLOWLIST_SHA256 = self.legacy_digest
        self.inventory_path = self.root / "inventory.json"
        self._write_inventory(self.entries)

    def tearDown(self) -> None:
        MODULE.FROZEN_LEGACY_ALLOWLIST_SHA256 = self.saved_legacy_digest
        self.temp.cleanup()

    @staticmethod
    def _git(*args: str, cwd: Path) -> str:
        env = {
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
        }
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return completed.stdout.strip()

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n")

    def _entry(
        self,
        bundle: Path,
        classification: str,
        recovery_basis: str,
        *,
        manifest: Path | None = None,
    ) -> dict[str, object]:
        signature, prerequisites, refs = MODULE._bundle_header(bundle)
        entry: dict[str, object] = {
            "path": bundle.relative_to(self.root).as_posix(),
            "sha256": self._sha256(bundle),
            "size": bundle.stat().st_size,
            "signature": signature,
            "classification": classification,
            "prerequisites": prerequisites,
            "advertised_refs": refs,
            "recovery_basis": recovery_basis,
        }
        if manifest is not None:
            entry["manifest"] = {
                "path": manifest.relative_to(self.root).as_posix(),
                "sha256": self._sha256(manifest),
            }
        return entry

    def _write_inventory(
        self,
        entries: list[dict[str, object]],
        *,
        legacy_digest: str | None = None,
    ) -> None:
        value = {
            "schema": MODULE.SCHEMA,
            "bundle_roots": ["patches"],
            "legacy_allowlist_sha256": legacy_digest or self.legacy_digest,
            "bundles": sorted(entries, key=lambda entry: entry["path"]),
        }
        self._write_json(self.inventory_path, value)

    def test_offline_contract_validation_accepts_declared_thin_bundle(self) -> None:
        result = MODULE.validate_inventory(self.inventory_path, repo_root=self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["network_used"])

    def test_bundle_header_accepts_literal_head_ref(self) -> None:
        _, prerequisites, refs = MODULE._bundle_header(self.legacy)
        self.assertEqual(prerequisites, [])
        self.assertEqual(refs, [{"ref": "HEAD", "tip": self.base}])

    def test_rejects_new_bundle_missing_from_inventory(self) -> None:
        shutil.copyfile(self.legacy, self.patches / "untracked.bundle")
        with self.assertRaisesRegex(MODULE.ValidationError, "bundle census mismatch"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_rejects_changed_bundle_bytes(self) -> None:
        with self.legacy.open("ab") as handle:
            handle.write(b"changed")
        with self.assertRaisesRegex(MODULE.ValidationError, "bundle bytes changed"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_new_bundle_cannot_be_grandfathered_as_legacy(self) -> None:
        extra = self.patches / "extra.bundle"
        shutil.copyfile(self.legacy, extra)
        expanded = self.entries + [
            self._entry(extra, "legacy-self-contained", "attempted new grandfather entry")
        ]
        expanded.sort(key=lambda entry: entry["path"])
        forged_digest = MODULE._canonical_legacy(
            [entry for entry in expanded if entry["classification"].startswith("legacy-")]
        )
        self._write_inventory(expanded, legacy_digest=forged_digest)
        with self.assertRaisesRegex(MODULE.ValidationError, "legacy allowlist is frozen"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_rejects_manifest_that_omits_header_prerequisite(self) -> None:
        self.manifest["prerequisites"] = []
        self._write_json(self.manifest_path, self.manifest)
        entries = json.loads(json.dumps(self.entries))
        thin_entry = next(entry for entry in entries if entry["path"] == "patches/thin.bundle")
        thin_entry["manifest"]["sha256"] = self._sha256(self.manifest_path)
        self._write_inventory(entries)
        with self.assertRaisesRegex(MODULE.ValidationError, "prerequisite set does not match header"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_public_verification_rejects_false_remote_label(self) -> None:
        original_run = MODULE._run

        def fail_ls_remote(
            args: list[str], *, cwd: Path | None = None, timeout: int = 180
        ):
            if args[:2] == ["git", "ls-remote"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            return original_run(args, cwd=cwd, timeout=timeout)

        with mock.patch.object(MODULE, "_run", side_effect=fail_ls_remote):
            with self.assertRaisesRegex(MODULE.ValidationError, "not uniquely advertised"):
                MODULE.validate_inventory(
                    self.inventory_path,
                    repo_root=self.root,
                    verify_public_remotes=True,
                )

    def test_public_verification_restores_thin_bundle_with_synthetic_remote(self) -> None:
        original_run = MODULE._run

        def redirect_public_remote(
            args: list[str], *, cwd: Path | None = None, timeout: int = 180
        ):
            rewritten = [str(self.public) if arg == "https://example.invalid/public.git" else arg for arg in args]
            return original_run(rewritten, cwd=cwd, timeout=timeout)

        with mock.patch.object(MODULE, "_run", side_effect=redirect_public_remote):
            result = MODULE.validate_inventory(
                self.inventory_path,
                repo_root=self.root,
                verify_public_remotes=True,
            )
        self.assertEqual(result["public_remote_proofs"], 1)
        self.assertTrue(result["network_used"])


if __name__ == "__main__":
    unittest.main()
