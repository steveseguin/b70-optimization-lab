#!/usr/bin/env python3

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("verify-qwen38-flash-next-fp8-tree.py")
SPEC = importlib.util.spec_from_file_location("qwen_flash_next_tree_verifier", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def write_fixture(base: Path, *, bad_index_reference: bool = False):
    root = base / "model"
    root.mkdir()
    revision = "1" * 40
    shard_name = "model-00001-of-00001.safetensors"
    config = b'{"model_type":"fixture"}\n'
    referenced_shard = "missing.safetensors" if bad_index_reference else shard_name
    index = (
        json.dumps(
            {"metadata": {"total_size": 5}, "weight_map": {"weight": referenced_shard}},
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    shard = b"small-lfs-fixture"
    content = {
        "config.json": config,
        "model.safetensors.index.json": index,
        shard_name: shard,
    }
    for name, data in content.items():
        (root / name).write_bytes(data)

    files = {
        "config.json": {
            "size": len(config),
            "blob_id": git_blob(config),
            "lfs_sha256": None,
        },
        "model.safetensors.index.json": {
            "size": len(index),
            "blob_id": git_blob(index),
            "lfs_sha256": None,
        },
        shard_name: {
            "size": len(shard),
            "blob_id": "2" * 40,
            "lfs_sha256": hashlib.sha256(shard).hexdigest(),
        },
    }
    tree = json.dumps(
        {"format_version": 1, "files": files}, separators=(",", ":"), sort_keys=True
    ).encode()
    tree_path = root / ".cache" / "huggingface" / "trees" / f"{revision}.json"
    tree_path.parent.mkdir(parents=True)
    tree_path.write_bytes(tree)
    contract = MODULE.Contract(
        repo_id="fixture/model",
        revision=revision,
        tree_metadata_sha256=hashlib.sha256(tree).hexdigest(),
        root_file_count=3,
        root_total_bytes=sum(map(len, content.values())),
        shard_count=1,
        config_sha256=hashlib.sha256(config).hexdigest(),
        index_sha256=hashlib.sha256(index).hexdigest(),
    )
    return root, contract


class TreeVerifierTests(unittest.TestCase):
    def test_complete_fixture_passes_and_distinguishes_digest_kinds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, contract = write_fixture(Path(temporary))
            receipt = MODULE.verify_tree(root, contract)
            self.assertEqual(receipt["status"], "pass")
            self.assertEqual(receipt["observed"]["root_file_count"], 3)
            self.assertEqual(receipt["observed"]["indexed_shard_count"], 1)
            kinds = {row["path"]: row["digest_kind"] for row in receipt["files"]}
            self.assertEqual(kinds["config.json"], "git_blob_sha1")
            self.assertEqual(kinds["model-00001-of-00001.safetensors"], "lfs_sha256")

    def test_metadata_identity_mismatch_fails_before_artifact_hashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, contract = write_fixture(Path(temporary))
            wrong = MODULE.Contract(
                **{**contract.__dict__, "tree_metadata_sha256": "0" * 64}
            )
            with mock.patch.object(MODULE, "git_blob_sha1") as blob_hash:
                with self.assertRaisesRegex(
                    MODULE.VerificationError, "metadata SHA-256"
                ):
                    MODULE.verify_tree(root, wrong)
            blob_hash.assert_not_called()

    def test_extra_root_file_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, contract = write_fixture(Path(temporary))
            (root / "extra.txt").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(MODULE.VerificationError, "inventory mismatch"):
                MODULE.verify_tree(root, contract)

    def test_lfs_digest_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, contract = write_fixture(Path(temporary))
            shard = root / "model-00001-of-00001.safetensors"
            shard.write_bytes(b"same-size-corrupt")
            self.assertEqual(shard.stat().st_size, len(b"small-lfs-fixture"))
            with self.assertRaisesRegex(
                MODULE.VerificationError, "lfs_sha256 mismatch"
            ):
                MODULE.verify_tree(root, contract)

    def test_ordinary_git_blob_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, contract = write_fixture(Path(temporary))
            config = root / "config.json"
            config.write_bytes(b'{"model_type":"rupture"}\n')
            self.assertEqual(config.stat().st_size, len(b'{"model_type":"fixture"}\n'))
            with self.assertRaisesRegex(
                MODULE.VerificationError, "git_blob_sha1 mismatch"
            ):
                MODULE.verify_tree(root, contract)

    def test_index_reference_must_close_over_declared_shards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, contract = write_fixture(Path(temporary), bad_index_reference=True)
            with self.assertRaisesRegex(
                MODULE.VerificationError, "indexed shard set mismatch"
            ):
                MODULE.verify_tree(root, contract)

    def test_cli_writes_pass_receipt_atomically_outside_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, contract = write_fixture(base)
            receipt = base / "receipts" / "verified.json"
            with mock.patch.object(MODULE, "PINNED", contract):
                self.assertEqual(
                    MODULE.main(["--model-root", str(root), "--receipt", str(receipt)]),
                    0,
                )
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(list(receipt.parent.glob("*.tmp")), [])

    def test_cli_writes_failure_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, contract = write_fixture(base)
            (root / "extra.txt").write_text("extra", encoding="utf-8")
            receipt = base / "failure.json"
            with mock.patch.object(MODULE, "PINNED", contract):
                self.assertEqual(
                    MODULE.main(["--model-root", str(root), "--receipt", str(receipt)]),
                    2,
                )
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "fail")
            self.assertIn("inventory mismatch", payload["error"])

    def test_receipt_inside_model_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = write_fixture(Path(temporary))
            with self.assertRaisesRegex(MODULE.VerificationError, "outside"):
                MODULE.receipt_outside_model(root, root / "receipt.json")


if __name__ == "__main__":
    unittest.main()
