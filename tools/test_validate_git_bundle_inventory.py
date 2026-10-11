#!/usr/bin/env python3
"""Offline regression tests for the repository Git-bundle inventory guard."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("validate-git-bundle-inventory.py")
SPEC = importlib.util.spec_from_file_location("validate_git_bundle_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BundleInventoryRepositoryTest(unittest.TestCase):
    def test_repository_census_still_rejects_preexisting_uninventoried_gdn_bundle(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        # This is an expected rejection, not an allowlist. The workflow's actual
        # validator command must still fail until legitimate provenance and a
        # complete inventory close the preexisting exact-GDN gap.
        omitted = ("patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/"
                   "vllm-xpu-kernels-q38-gdn-exact-serial-bbae3c5-20260913.bundle")
        with self.assertRaises(MODULE.ValidationError) as raised:
            MODULE.validate_inventory(
                repo / "data/git-bundle-portability-inventory-v1.json", repo_root=repo)
        self.assertEqual(str(raised.exception),
                         f"bundle census mismatch; untracked={[omitted]}, absent=[]")

    def test_all_four_archived_bundles_match_unchanged_frozen_inventory(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        inventory = json.loads((repo / "data/git-bundle-portability-inventory-v1.json").read_text())
        entries = {entry["path"]: entry for entry in inventory["bundles"]}
        archived = MODULE._archived_bundle_metadata(repo, [repo / "patches"])
        self.assertEqual(len(archived), 4)
        for path, actual in archived.items():
            with self.subTest(bundle=path):
                expected = entries[path]
                self.assertIn(expected["classification"], MODULE.LEGACY_CLASSIFICATIONS)
                for field in ("size", "sha256", "signature", "prerequisites", "advertised_refs"):
                    self.assertEqual(actual[field], expected[field])
        legacy = [entry for entry in inventory["bundles"]
                  if entry["classification"] in MODULE.LEGACY_CLASSIFICATIONS]
        self.assertEqual(len(legacy), 53)
        self.assertEqual(MODULE._canonical_legacy(legacy), MODULE.FROZEN_LEGACY_ALLOWLIST_SHA256)
        self.assertEqual(inventory["legacy_allowlist_sha256"], MODULE.FROZEN_LEGACY_ALLOWLIST_SHA256)

    def test_existing_manifest_backed_contracts_still_pass_offline(self) -> None:
        # The strict census fails before this phase; keep direct coverage of all
        # five already-inventoried provenance contracts without exempting the gap.
        repo = Path(__file__).resolve().parents[1]
        inventory = json.loads((repo / "data/git-bundle-portability-inventory-v1.json").read_text())
        entries = [entry for entry in inventory["bundles"]
                   if entry["classification"] in MODULE.MANIFEST_CLASSIFICATIONS]
        self.assertEqual(len(entries), 5)
        for entry in entries:
            with self.subTest(bundle=entry["path"]):
                bundle = repo / entry["path"]
                self.assertEqual(bundle.stat().st_size, entry["size"])
                self.assertEqual(MODULE._sha256(bundle), entry["sha256"])
                self.assertEqual(MODULE._bundle_header(bundle),
                                 (entry["signature"], entry["prerequisites"], entry["advertised_refs"]))
                MODULE._validate_manifest_contract(repo, entry, bundle)


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

    def _archive_bundles(self, bundles: list[Path], *, directory: Path | None = None) -> tuple[Path, Path]:
        directory = directory or self.patches
        directory.mkdir(parents=True, exist_ok=True)
        archive = directory / "source-history.tar.xz"
        members = []
        with tarfile.open(archive, "w:xz") as output:
            for bundle in bundles:
                name = bundle.relative_to(self.root).as_posix()
                data = bundle.read_bytes()
                member = tarfile.TarInfo(name)
                member.size = len(data)
                output.addfile(member, io.BytesIO(data))
                members.append({"path": name, "size": len(data),
                                "sha256": hashlib.sha256(data).hexdigest()})
        manifest = directory / "source-archive-manifest.json"
        self._write_json(manifest, {
            "schema": "b70-source-archive-v1",
            "archive": {"file": archive.name, "size": archive.stat().st_size,
                        "sha256": self._sha256(archive)},
            "members": members,
        })
        for bundle in bundles:
            bundle.unlink()
        return archive, manifest

    def test_archived_legacy_preserves_frozen_inventory_without_extraction(self) -> None:
        self._archive_bundles([self.legacy])
        frozen_inventory = self.inventory_path.read_bytes()
        files_before = sorted(p.relative_to(self.root) for p in self.root.rglob("*") if p.is_file())
        # Archived legacy verification must neither materialize a bundle nor need
        # a temporary disk budget (CI runners may have less than 50 GiB free).
        with mock.patch.object(MODULE.tempfile, "TemporaryDirectory", side_effect=AssertionError("no extraction")):
            result = MODULE.validate_inventory(self.inventory_path, repo_root=self.root)
        self.assertEqual(result["bundle_count"], 2)
        self.assertEqual(result["archived_bundle_count"], 1)
        self.assertFalse(self.legacy.exists())
        self.assertEqual(frozen_inventory, self.inventory_path.read_bytes())
        self.assertEqual(files_before, sorted(p.relative_to(self.root) for p in self.root.rglob("*") if p.is_file()))

    def test_matching_restored_copy_is_counted_once_and_corruption_cannot_shadow_archive(self) -> None:
        original = self.legacy.read_bytes()
        self._archive_bundles([self.legacy])
        self.legacy.write_bytes(original)
        result = MODULE.validate_inventory(self.inventory_path, repo_root=self.root)
        self.assertEqual(result["bundle_count"], 2)
        self.assertEqual(result["archived_bundle_count"], 1)
        self.legacy.write_bytes(original + b"changed local copy")
        with self.assertRaisesRegex(MODULE.ValidationError, "bundle bytes changed"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_corrupt_archive_or_member_pin_fails_even_without_live_bundle(self) -> None:
        archive, manifest = self._archive_bundles([self.legacy])
        original = archive.read_bytes()
        archive.write_bytes(original + b"changed archive")
        with self.assertRaisesRegex(MODULE.ValidationError, "archive size/hash mismatch"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)
        archive.write_bytes(original)
        value = json.loads(manifest.read_text())
        value["members"][0]["sha256"] = "0" * 64
        self._write_json(manifest, value)
        with self.assertRaisesRegex(MODULE.ValidationError, "member hash mismatch"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_uninventoried_archived_bundle_still_fails_census(self) -> None:
        extra = self.patches / "untracked.bundle"
        shutil.copyfile(self.legacy, extra)
        self._archive_bundles([self.legacy, extra])
        with self.assertRaisesRegex(MODULE.ValidationError, "bundle census mismatch.*untracked.bundle"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_archive_metadata_cannot_replace_inventory_header_or_hash_pins(self) -> None:
        self._archive_bundles([self.legacy])
        for field, value, error in (("sha256", "0" * 64, "archived bundle bytes changed"),
                                    ("signature", "# v3 git bundle", "archived bundle signature mismatch")):
            with self.subTest(field=field):
                entries = json.loads(json.dumps(self.entries))
                legacy = next(e for e in entries if e["path"] == "patches/legacy.bundle")
                legacy[field] = value
                self._write_inventory(entries)
                with self.assertRaisesRegex(MODULE.ValidationError, error):
                    MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_duplicate_archive_member_location_is_rejected(self) -> None:
        original = self.legacy.read_bytes()
        self._archive_bundles([self.legacy])
        self.legacy.write_bytes(original)
        self._archive_bundles([self.legacy], directory=self.patches / "duplicate")
        with self.assertRaisesRegex(MODULE.ValidationError, "more than one source archive"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

    def test_archiving_manifest_backed_input_does_not_skip_public_restore_contract(self) -> None:
        self._archive_bundles([self.thin])
        with self.assertRaisesRegex(MODULE.ValidationError, "must be restored before portability proof"):
            MODULE.validate_inventory(self.inventory_path, repo_root=self.root)

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
        self._archive_bundles([self.legacy])
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
