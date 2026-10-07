"""Mutations must not be hidden by the two narrowly declared source changes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import source_drift_proofs as proof

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    spec = importlib.util.spec_from_file_location("replay_drift", ROOT / "tools/replay_fp8_prefill_source_drift.py")
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)


class DriftProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_path = "repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json"
        cls.checker_path = "experiments/qwen38-27b-b70/scripts/check-fp8-practical-session.py"
        with tarfile.open(ROOT / "experiments/qwen38-27b-b70/data/2026-10-04-fp8-two-card-chunked-upload/evidence.tar.gz") as archive:
            cls.old_model = archive.extractfile("source/" + cls.model_path).read()
            cls.old_checker = archive.extractfile("source/" + cls.checker_path).read()
        cls.model = (ROOT / cls.model_path).read_bytes()
        cls.checker = (ROOT / cls.checker_path).read_bytes()

    def test_actual_timeout_default_equivalence(self):
        proof.prove_default_timeout_120({}, self.old_checker, self.checker)

    def test_timeout_default_or_gate_change_is_rejected(self):
        for old, new in [(b"timeout_seconds=120", b"timeout_seconds=121"),
                         (b"clock() - started > timeout_seconds", b"clock() - started >= timeout_seconds"),
                         (b"math.isfinite(timeout_seconds)", b"True")]:
            with self.subTest(change=new), self.assertRaises(AssertionError):
                proof.prove_default_timeout_120({}, self.old_checker, self.checker.replace(old, new))

    def test_unrelated_source_changes_are_rejected(self):
        with self.assertRaisesRegex(AssertionError, "beyond"):
            proof.prove_default_timeout_120({}, self.old_checker, self.checker + b"\nunrelated = True\n")

    def test_actual_metadata_addition(self):
        proof.prove_model_metadata_addition({}, self.old_model, self.model)

    def test_weight_change_is_rejected(self):
        data = json.loads(self.model); data["lfs_files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "weight identity"):
            proof.prove_model_metadata_addition({}, self.old_model, json.dumps(data))

    def test_revision_or_total_change_is_rejected(self):
        for field, value in [("revision", "0" * 40), ("total_weight_bytes", 1)]:
            data = json.loads(self.model); data[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(AssertionError, "identity"):
                proof.prove_model_metadata_addition({}, self.old_model, json.dumps(data))

    def test_extra_or_duplicate_metadata_is_rejected(self):
        data = json.loads(self.model); data["small_files"].append(data["small_files"][0])
        with self.assertRaisesRegex(AssertionError, "metadata additions"):
            proof.prove_model_metadata_addition({}, self.old_model, json.dumps(data))

    def test_replay_requires_exact_frozen_and_current_bindings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root / self.model_path; path.parent.mkdir(parents=True); path.write_bytes(self.model)
            frozen = root / "old.json"; frozen.write_bytes(self.old_model)
            row = {"repository_path": self.model_path, "sha256": replay.digest(self.old_model), "bytes": len(self.old_model)}
            entry = {"frozen_sha256": row["sha256"], "current_sha256": replay.digest(self.model), "acceptance": "pending", "reason": "metadata addition", "retire_by": "fresh acceptance", "frozen_source": "old.json", "proof": {"kind": "model_metadata_addition"}}
            content, _ = replay.checked_source(root, row, {self.model_path: entry})
            self.assertEqual(content, self.old_model)
            with self.assertRaisesRegex(ValueError, "undeclared"):
                replay.checked_source(root, row, {})
            bad = dict(entry, current_sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "binding"):
                replay.checked_source(root, row, {self.model_path: bad})
            bad = dict(entry, acceptance="passed")
            with self.assertRaisesRegex(ValueError, "binding"):
                replay.checked_source(root, row, {self.model_path: bad})
            frozen.write_bytes(self.old_model + b" ")
            with self.assertRaisesRegex(ValueError, "frozen manifest"):
                replay.checked_source(root, row, {self.model_path: entry})

    def test_wrapper_cannot_admit_changed_verifier(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root / "tools/verifier.py"; path.parent.mkdir(); path.write_text("changed")
            row = {"repository_path": "tools/verifier.py", "sha256": replay.digest(b"old"), "bytes": 3}
            with self.assertRaisesRegex(ValueError, "undeclared"):
                replay.checked_source(root, row, {})

    def test_replay_rejects_absolute_or_parent_source_paths(self):
        for path in (str(ROOT / self.model_path), "../escape"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "repository-relative"):
                replay.checked_source(ROOT, {"repository_path": path}, {})


if __name__ == "__main__":
    unittest.main()
