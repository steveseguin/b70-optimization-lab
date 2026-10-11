"""Historical recovery must preserve evidence and refuse unsafe preparation."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import historical_verifiers as h


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "audits/repository-cleanup/2026-10-10/pin-audit.json"


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class HistoricalPinFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.root = self.parent / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.target = "experiments/lane/tools/verifier.py"
        self.snapshot = "experiments/lane/history/verifier-old.py"
        self.holder = "experiments/lane/tools/client.sh"
        self.old = b"# prior verifier; must never be imported by preparation\nraise RuntimeError('executed')\n"
        self.sha = h.digest(self.old)
        self.source = (
            '#!/bin/bash\n'
            f'[[ "$(sha256sum "{chr(36)}{{repo}}/{self.target}" | cut -d" " -f1)" == {self.sha} ]] || exit 1\n'
            f'python "{chr(36)}{{repo}}/{self.target}"\n'
        ).encode()
        self.write(self.target, b"# evolving shared verifier\n")
        self.write(self.snapshot, self.old)
        self.write(self.holder, self.source)
        self.write("CURRENT.md", b"GPU launch is halted.\n")
        subprocess.run(["git", "-C", str(self.root), "add", self.holder], check=True)
        self.manifest = {
            "schema": "lab.historical-verifier-recovery.v1",
            "versions": [{"original_path": self.target, "sha256": self.sha,
                          "snapshot": self.snapshot, "git_blob": blob_id(self.old),
                          "origin_commit": "1" * 40}],
            "pins": [{"holder": self.holder, "holder_sha256": h.digest(self.source),
                      "target": self.target, "expected_sha256": self.sha,
                      "disposition": "recoverable"}],
            "maintained_replays": [],
        }
        self.manifest_path = self.root / "review.json"
        self.save()

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def save(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def validate(self):
        return h.validate_manifest(self.root, self.manifest_path, h.scan_pins(self.root))

    def prepare(self, name="prepared"):
        return h.prepare_client(self.root, self.manifest_path, self.holder, self.parent / name)

    def test_exact_recovery_needs_no_original_git_objects(self):
        self.assertEqual(self.validate(), {
            "recoverable": 1, "blocked": 0, "versions": 1, "maintained_replays": 0})
        self.assertEqual(h.scan_pins(self.root)[0]["status"], "drift")

    def test_only_tracked_shells_including_staged_new_files_are_scanned(self):
        self.write("experiments/lane/tools/untracked.sh", self.source)
        self.assertEqual(len(h.scan_pins(self.root)), 1)
        subprocess.run(["git", "-C", str(self.root), "add",
                        "experiments/lane/tools/untracked.sh"], check=True)
        self.assertEqual(len(h.scan_pins(self.root)), 2)
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            self.validate()

    def test_holder_comment_change_is_not_waived_by_same_pin(self):
        self.write(self.holder, self.source + b"# modified\n")
        with self.assertRaisesRegex(ValueError, "holder SHA256 differs"):
            self.validate()

    def test_snapshot_tamper_fails_before_any_output(self):
        self.write(self.snapshot, self.old + b"# changed\n")
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            self.prepare()
        self.assertFalse((self.parent / "prepared").exists())

    def test_bad_git_blob_identity_is_rejected(self):
        self.manifest["versions"][0]["git_blob"] = "f" * 40
        self.save()
        with self.assertRaisesRegex(ValueError, "Git blob differs"):
            self.validate()

    def test_stale_exception_must_be_reviewed_if_path_now_matches(self):
        self.write(self.target, self.old)
        with self.assertRaisesRegex(ValueError, "stale"):
            self.validate()

    def test_missing_shared_target_is_not_an_accepted_historical_exception(self):
        (self.root / self.target).unlink()
        self.assertEqual(h.scan_pins(self.root)[0]["status"], "absent")
        with self.assertRaisesRegex(ValueError, "target absent"):
            self.validate()

    def test_missing_tracked_holder_is_not_silently_skipped(self):
        (self.root / self.holder).unlink()
        with self.assertRaises(FileNotFoundError):
            h.scan_pins(self.root)

    def test_duplicate_rows_and_unused_versions_are_rejected(self):
        original = copy.deepcopy(self.manifest)
        self.manifest["pins"].append(copy.deepcopy(self.manifest["pins"][0]))
        self.save()
        with self.assertRaisesRegex(ValueError, "duplicate historical pin"):
            self.validate()
        self.manifest = original
        self.manifest["versions"].append(copy.deepcopy(self.manifest["versions"][0]))
        self.save()
        with self.assertRaisesRegex(ValueError, "duplicate historical version"):
            self.validate()
        self.manifest["versions"][-1]["original_path"] = "experiments/lane/other.py"
        self.save()
        with self.assertRaisesRegex(ValueError, "unreferenced historical version"):
            self.validate()

    def test_blocked_is_reported_but_cannot_be_prepared(self):
        evidence = self.write("experiments/lane/negative.md", b"Original client was never valid.\n")
        self.manifest["versions"] = []
        self.manifest["pins"][0].update({
            "disposition": "blocked", "reason": "Wrong verifier family",
            "evidence": [{"path": evidence.relative_to(self.root).as_posix(),
                          "sha256": h.digest(evidence.read_bytes())}]})
        self.save()
        self.assertEqual(self.validate()["blocked"], 1)
        with self.assertRaisesRegex(ValueError, "blocked"):
            self.prepare()
        self.assertFalse((self.parent / "prepared").exists())
        evidence.write_bytes(b"changed justification")
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            self.validate()

    def test_review_artifact_preserves_sources_and_has_no_executable_files(self):
        receipt = self.prepare()
        output = self.parent / "prepared"
        self.assertFalse(receipt["launch_ready"])
        self.assertEqual((self.root / self.holder).read_bytes(), self.source)
        self.assertEqual((output / "client-original.sh.txt").read_bytes(), self.source)
        self.assertEqual((output / "verifier.py.txt").read_bytes(), self.old)
        derived = (output / "client-for-review.sh.txt").read_text()
        self.assertEqual(derived.count(self.snapshot), 2)
        self.assertEqual(h.HASH_TOKEN.findall(derived),
                         h.HASH_TOKEN.findall(self.source.decode()))
        for file in output.iterdir():
            self.assertEqual(file.stat().st_mode & 0o777, 0o444)
        self.assertIn("parent chain", " ".join(receipt["constraints"]))
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.prepare()
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_preparation_rejects_repo_destination_and_symlink_parent(self):
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            h.prepare_client(self.root, self.manifest_path, self.holder, self.root / "new")
        alias = self.parent / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            h.prepare_client(self.root, self.manifest_path, self.holder, alias / "new")

    def test_manifest_rejects_traversal_absolute_and_symlink_inputs(self):
        for path in ("../outside.py", "/tmp/outside.py", "experiments/../outside.py"):
            with self.subTest(path=path):
                self.manifest["versions"][0]["snapshot"] = path
                self.save()
                with self.assertRaisesRegex(ValueError, "invalid repository path"):
                    self.validate()
        (self.root / self.snapshot).unlink()
        (self.root / self.snapshot).symlink_to(self.root / self.target)
        self.manifest["versions"][0]["snapshot"] = self.snapshot
        self.save()
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.validate()

    def test_redirection_refuses_ambiguous_or_changed_pin(self):
        for source in (self.source + f"# {self.target}\n".encode(),
                       self.source.replace(self.sha.encode(), b"f" * 64)):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "exactly"):
                h.redirect_client(source, self.target, self.snapshot, self.sha)

    def test_maintained_replay_variable_pin_and_maker_are_guarded(self):
        descriptor = f"sha256={self.sha}\n".encode()
        pin_file = self.write("repro/packet/verifier-pin.txt", descriptor)
        maker = self.write("repro/packet/make-replay-attempt.py", b"# never executed\n")
        identity = self.write("repro/packet/verify-identity.sh", b"# never executed\n")
        self.manifest["maintained_replays"] = [{
            "pin_file": pin_file.relative_to(self.root).as_posix(),
            "pin_file_sha256": h.digest(descriptor), "verifier": self.snapshot,
            "maker": maker.relative_to(self.root).as_posix(),
            "maker_sha256": h.digest(maker.read_bytes()),
            "identity": identity.relative_to(self.root).as_posix(),
            "identity_sha256": h.digest(identity.read_bytes()),
        }]
        self.save()
        self.assertEqual(self.validate()["maintained_replays"], 1)
        maker.write_bytes(b"# changed replay implementation\n")
        with self.assertRaisesRegex(ValueError, "SHA256 differs"):
            self.validate()


class RepositoryRecovery(unittest.TestCase):
    def test_every_recovered_client_redirects_both_references_without_repinning(self):
        manifest = h.load_manifest(MANIFEST)
        versions = {(v["original_path"], v["sha256"]): v for v in manifest["versions"]}
        count = 0
        for entry in manifest["pins"]:
            if entry["disposition"] != "recoverable":
                continue
            with self.subTest(holder=entry["holder"]):
                original = h.verified_bytes(ROOT, entry["holder"], entry["holder_sha256"])
                version = versions[entry["target"], entry["expected_sha256"]]
                h.verified_bytes(ROOT, version["snapshot"], entry["expected_sha256"])
                derived = h.redirect_client(original, entry["target"], version["snapshot"],
                                            entry["expected_sha256"])
                self.assertNotEqual(original, derived)
                self.assertEqual(derived.count(version["snapshot"].encode()), 2)
                count += 1
        self.assertEqual(count, 230)

    def test_real_review_is_exact_and_raw_scan_still_reports_drift(self):
        summary = h.validate_manifest(ROOT, MANIFEST, h.scan_pins(ROOT))
        self.assertEqual(summary, {
            "recoverable": 230, "blocked": 1, "versions": 8, "maintained_replays": 5})
        command = [sys.executable, "-B", str(ROOT / "tools/check-pinned-hashes.py"), "--json"]
        raw = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(raw.returncode, 1, raw.stderr)
        self.assertEqual(json.loads(raw.stdout)["counts"]["drift"], 231)
        self.assertEqual(json.loads(raw.stdout)["counts"]["absent"], 0)
        reviewed = subprocess.run(command + ["--historical-manifest", str(MANIFEST)],
                                  capture_output=True, text=True)
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        self.assertEqual(json.loads(reviewed.stdout)["historical_review"], summary)


if __name__ == "__main__":
    unittest.main()
