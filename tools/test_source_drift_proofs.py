"""Mutations must not be hidden by narrowly declared source changes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
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


class AllowCachedDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = "experiments/qwen38-27b-b70/scripts/compare-ladder-oracles.py"
        packet = ROOT / "experiments/qwen38-27b-b70/data/2026-10-07-fp8-two-card-multi-user"
        with tarfile.open(packet / "evidence.tar.gz") as archive:
            cls.frozen = archive.extractfile("source/" + path).read()
        cls.current = (ROOT / path).read_bytes()
        cls.entry = next(e for e in json.loads((packet / "source-drift.json").read_text())["entries"] if e["path"] == path)

    def test_real_delta_and_exact_hash_bindings(self):
        self.assertEqual(hashlib.sha256(self.frozen).hexdigest(), self.entry["frozen_sha256"])
        self.assertEqual(hashlib.sha256(self.current).hexdigest(), self.entry["current_sha256"])
        self.assertEqual(self.entry["acceptance"], "pending")
        proof.prove_allow_cached_default_false(self.entry, self.frozen, self.current)

    def test_default_or_cache_gate_changes_rejected(self):
        changes = [
            (b"action='store_true'", b"action='store_true', default=True"),
            (b"action='store_true'", b"action='store_false'"),
            (b"a.allow_cached or batch.get('cached_tokens_all_zero') is True", b"True"),
            (b"a.allow_cached or batch.get('cached_tokens_all_zero') is True", b"a.allow_cached"),
            (b"a.allow_cached or batch.get('cached_tokens_all_zero') is True", b"a.allow_cached or batch.get('cached_tokens_all_zero') is not False"),
            (b"not mismatches and (a.allow_cached", b"(a.allow_cached"),
        ]
        for old, new in changes:
            self.assertIn(old, self.current)
            with self.subTest(change=new), self.assertRaises(AssertionError):
                proof.prove_allow_cached_default_false(self.entry, self.frozen, self.current.replace(old, new))

    def test_token_comparison_and_unrelated_module_changes_rejected(self):
        for changed in (self.current.replace(b"if a == b:", b"if True:"),
                        self.current.replace(b"if ref['prompt_sha256'] != row['prompt_sha256']:", b"if False:"),
                        self.current + b"\nunrelated = True\n"):
            with self.subTest(source=changed[-80:]), self.assertRaisesRegex(AssertionError, "beyond"):
                proof.prove_allow_cached_default_false(self.entry, self.frozen, changed)

    def test_report_and_duplicate_flag_changes_rejected(self):
        for changed in (self.current.replace(b"'allow_cached': a.allow_cached", b"'allow_cached': True"),
                        self.current.replace(b"'allow_cached': a.allow_cached, ", b""),
                        self.current.replace(b"    a = ap.parse_args()", b"    ap.add_argument('--allow-cached', action='store_true', help='prefix caching on: cache hits do not fail a batch (its tokens still must match)')\n    a = ap.parse_args()")):
            with self.subTest(source=changed[-80:]), self.assertRaises(AssertionError):
                proof.prove_allow_cached_default_false(self.entry, self.frozen, changed)

    def test_default_cli_verdict_matches_and_opt_in_keeps_token_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old, new = root / "old.py", root / "new.py"
            old.write_bytes(self.frozen); new.write_bytes(self.current)
            row = {"prompt_id": "p", "prompt_sha256": "hash", "token_ids": [1, 2]}
            ref = {"oracle": {"rows": [row]}}
            candidate = {"oracle": {"rows": [row]}, "batches": [
                {"concurrency": 1, "repeat": 1, "cached_tokens_all_zero": True, "rows": [row]}]}
            reference_path, candidate_path = root / "reference.json", root / "candidate.json"
            reference_path.write_text(json.dumps(ref))

            def run(path, *args):
                candidate_path.write_text(json.dumps(candidate))
                return subprocess.run([sys.executable, "-B", str(path), str(candidate_path),
                                       str(reference_path), *args], capture_output=True).returncode

            self.assertEqual(run(old), 0); self.assertEqual(run(new), 0)
            candidate["batches"][0]["cached_tokens_all_zero"] = False
            self.assertEqual(run(old), 1); self.assertEqual(run(new), 1)
            self.assertEqual(run(new, "--allow-cached"), 0)
            candidate["batches"][0]["rows"] = [{**row, "token_ids": [1, 3]}]
            self.assertEqual(run(new, "--allow-cached"), 1)


if __name__ == "__main__":
    unittest.main()
