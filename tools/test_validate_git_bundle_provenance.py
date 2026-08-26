#!/usr/bin/env python3
"""Focused tests for validate-git-bundle-provenance.py."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("validate-git-bundle-provenance.py")
SPEC = importlib.util.spec_from_file_location("validate_git_bundle_provenance", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BundleProvenanceTest(unittest.TestCase):
    def test_repository_deepseek_repair_preserves_old_thin_bundle(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        archive = repo / "patches/deepseek-v4-flash-reap-xpu-b70"
        historical = archive / "vllm-deepseek-v4-k160-dspark7-80tps-record-20260718.bundle"
        repaired = archive / "vllm-deepseek-v4-k160-dspark7-80tps-record-20260718-public-anchor.bundle"
        manifest_path = repaired.with_suffix(".provenance.json")
        manifest = MODULE._load_manifest(manifest_path)
        self.assertEqual(
            self._sha256(historical),
            "cebc81bedc22496dc82836b9419428e0377a3eb4e7ac213014a7306c7b30e825",
        )
        self.assertEqual(
            MODULE._bundle_header(historical)[0],
            ["61c87db645c256651b5a366f538898485077ad32"],
        )
        self.assertEqual(
            MODULE._bundle_header(MODULE._resolve_bundle(manifest_path, manifest))[0],
            ["382bbd51448b2f58c73b3e51d051bc352166ba91"],
        )

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.public = self.root / "public.git"
        self._git("init", "-q", "-b", "main", str(self.source), cwd=self.root)
        self._git("init", "--bare", "-q", str(self.public), cwd=self.root)
        self._git("config", "user.name", "Bundle Test", cwd=self.source)
        self._git("config", "user.email", "bundle@example.invalid", cwd=self.source)

        (self.source / "payload.txt").write_text("public anchor\n")
        self._git("add", "payload.txt", cwd=self.source)
        self._git("commit", "-q", "-m", "public anchor", cwd=self.source)
        self.anchor = self._git("rev-parse", "HEAD", cwd=self.source)
        self.anchor_tree = self._git("show", "-s", "--format=%T", self.anchor, cwd=self.source)
        self._git("remote", "add", "origin", str(self.public), cwd=self.source)
        self._git("push", "-q", "-u", "origin", "main", cwd=self.source)

        (self.source / "private-base.txt").write_text("private base\n")
        self._git("add", "private-base.txt", cwd=self.source)
        self._git("commit", "-q", "-m", "private base", cwd=self.source)
        self.private_base = self._git("rev-parse", "HEAD", cwd=self.source)
        self.private_base_tree = self._git(
            "show", "-s", "--format=%T", self.private_base, cwd=self.source
        )
        (self.source / "record.txt").write_text("record\n")
        self._git("add", "record.txt", cwd=self.source)
        self._git("commit", "-q", "-m", "record", cwd=self.source)
        self.record = self._git("rev-parse", "HEAD", cwd=self.source)
        self.record_tree = self._git("show", "-s", "--format=%T", self.record, cwd=self.source)
        self.record_ref = "refs/tags/example-record"
        self.base_ref = "refs/tags/example-base"
        self._git("tag", "example-base", self.private_base, cwd=self.source)
        self._git("tag", "example-record", self.record, cwd=self.source)
        self._git("push", "-q", "origin", self.base_ref, self.record_ref, cwd=self.source)

    def tearDown(self) -> None:
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

    def _manifest(
        self,
        bundle: Path,
        *,
        classification: str,
        prerequisite: tuple[str, str] | None,
    ) -> Path:
        prereqs = []
        if prerequisite is not None:
            commit, tree = prerequisite
            prereqs.append(
                {
                    "commit": commit,
                    "tree": tree,
                    "public_remote": str(self.public),
                    "provenance_remote_name": "origin",
                    "provenance_ref": "refs/remotes/origin/main",
                }
            )
        manifest = {
            "schema": MODULE.SCHEMA,
            "bundle": bundle.name,
            "bundle_sha256": self._sha256(bundle),
            "bundle_size": bundle.stat().st_size,
            "classification": classification,
            "expected_ref": self.record_ref,
            "expected_tip": self.record,
            "expected_tree": self.record_tree,
            "prerequisites": prereqs,
            "included_commits": [
                {
                    "commit": self.private_base,
                    "tree": self.private_base_tree,
                    "must_be_absent_before_bundle": True,
                }
            ],
            "public_recovery_refs": [
                {
                    "role": "record-base",
                    "public_remote": str(self.public),
                    "ref": self.base_ref,
                    "commit": self.private_base,
                    "tree": self.private_base_tree,
                },
                {
                    "role": "record",
                    "public_remote": str(self.public),
                    "ref": self.record_ref,
                    "commit": self.record,
                    "tree": self.record_tree,
                },
            ],
        }
        path = bundle.with_suffix(".provenance.json")
        path.write_text(json.dumps(manifest))
        return path

    def test_accepts_publicly_anchored_thin_bundle_and_restores_exact_tip(self) -> None:
        bundle = self.root / "public-anchor.bundle"
        self._git(
            "bundle",
            "create",
            str(bundle),
            self.record_ref,
            f"^{self.anchor}",
            cwd=self.source,
        )
        manifest = self._manifest(
            bundle,
            classification="thin-public-prerequisite",
            prerequisite=(self.anchor, self.anchor_tree),
        )
        result = MODULE.validate(manifest, provenance_repo=self.source)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["restored_tip"], self.record)
        self.assertEqual(result["restored_tree"], self.record_tree)
        self.assertEqual(result["prerequisites"], [self.anchor])
        self.assertEqual(result["verified_included_commits"], [self.private_base])
        self.assertTrue(result["empty_disposable_public_ref_fetch"])
        self.assertEqual(
            [entry["commit"] for entry in result["verified_public_recovery_refs"]],
            [self.private_base, self.record],
        )

    def test_accepts_self_contained_bundle_in_empty_repository(self) -> None:
        bundle = self.root / "self-contained.bundle"
        self._git("bundle", "create", str(bundle), self.record_ref, cwd=self.source)
        manifest = self._manifest(
            bundle,
            classification="self-contained",
            prerequisite=None,
        )
        result = MODULE.validate(manifest)
        self.assertEqual(result["classification"], "self-contained")
        self.assertEqual(result["prerequisites"], [])
        self.assertTrue(result["empty_disposable_restore"])

    def test_rejects_undeclared_thin_bundle(self) -> None:
        bundle = self.root / "undeclared-thin.bundle"
        self._git(
            "bundle",
            "create",
            str(bundle),
            self.record_ref,
            f"^{self.anchor}",
            cwd=self.source,
        )
        manifest = self._manifest(
            bundle,
            classification="self-contained",
            prerequisite=None,
        )
        with self.assertRaisesRegex(MODULE.ValidationError, "zero prerequisites"):
            MODULE.validate(manifest)

    def test_rejects_private_prerequisite_mislabeled_as_public(self) -> None:
        bundle = self.root / "private-anchor.bundle"
        self._git(
            "bundle",
            "create",
            str(bundle),
            self.record_ref,
            f"^{self.private_base}",
            cwd=self.source,
        )
        manifest = self._manifest(
            bundle,
            classification="thin-public-prerequisite",
            prerequisite=(self.private_base, self.private_base_tree),
        )
        with self.assertRaisesRegex(MODULE.ValidationError, "not reachable from public ref"):
            MODULE.validate(manifest, provenance_repo=self.source)

    def test_rejects_wrong_public_remote_identity(self) -> None:
        bundle = self.root / "remote-mismatch.bundle"
        self._git(
            "bundle",
            "create",
            str(bundle),
            self.record_ref,
            f"^{self.anchor}",
            cwd=self.source,
        )
        manifest = self._manifest(
            bundle,
            classification="thin-public-prerequisite",
            prerequisite=(self.anchor, self.anchor_tree),
        )
        value = json.loads(manifest.read_text())
        value["prerequisites"][0]["public_remote"] = "https://example.invalid/not-public.git"
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(MODULE.ValidationError, "public remote mismatch"):
            MODULE.validate(manifest, provenance_repo=self.source)

    def test_rejects_public_recovery_ref_at_wrong_commit(self) -> None:
        bundle = self.root / "wrong-recovery-ref.bundle"
        self._git("bundle", "create", str(bundle), self.record_ref, cwd=self.source)
        manifest = self._manifest(bundle, classification="self-contained", prerequisite=None)
        value = json.loads(manifest.read_text())
        value["public_recovery_refs"][0]["commit"] = self.anchor
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(MODULE.ValidationError, "not advertised as exact commit"):
            MODULE.validate(manifest)


if __name__ == "__main__":
    unittest.main()
