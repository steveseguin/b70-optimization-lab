#!/usr/bin/env python3
"""Host-only tests for the revision-bound 0731 DSpark pack builder."""

from __future__ import annotations

from contextlib import ExitStack
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("prepare-0731-dspark-draft-pack.py")
SPEC = importlib.util.spec_from_file_location("prepare_0731_dspark_draft_pack", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def safetensors_bytes(name: str, payload: bytes) -> bytes:
    header = {
        name: {
            "dtype": "U8",
            "shape": [len(payload)],
            "data_offsets": [0, len(payload)],
        }
    }
    raw = json.dumps(header, separators=(",", ":")).encode()
    raw += b" " * ((8 - len(raw) % 8) % 8)
    return struct.pack("<Q", len(raw)) + raw + payload


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DraftPackBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "draft-pack"
        self.staging = self.root / ".draft-pack.staging"
        self.receipt_root = self.root / "receipt"
        self.receipt_root.mkdir()
        self.receipt = self.receipt_root / "summary.json"
        self.receipt.write_text('{"status":"pass"}\n', encoding="utf-8")
        for name in MODULE.RECEIPT_SIDECARS:
            (self.receipt_root / name).write_text(name + "\n", encoding="utf-8")

        self.config = {
            "architectures": ["DeepseekV4ForCausalLM"],
            "model_type": "deepseek_v4",
            "dspark_block_size": 5,
            "dspark_markov_rank": 256,
            "dspark_target_layer_ids": [40, 41, 42],
            "hidden_size": 4096,
            "vocab_size": 129280,
        }
        (self.source / "config.json").write_text(
            json.dumps(self.config), encoding="utf-8"
        )
        self.tensor_names = {
            "model-00046-of-00048.safetensors": "mtp.0.weight",
            "model-00047-of-00048.safetensors": "mtp.1.weight",
            "model-00048-of-00048.safetensors": "mtp.2.weight",
        }
        payloads = (b"a", b"bc", b"def")
        for (shard, tensor), payload in zip(self.tensor_names.items(), payloads):
            (self.source / shard).write_bytes(safetensors_bytes(tensor, payload))
        self.index = {
            "metadata": {"total_size": 10},
            "weight_map": {
                "embed.weight": "model-00001-of-00048.safetensors",
                **{tensor: shard for shard, tensor in self.tensor_names.items()},
            },
        }
        (self.source / "model.safetensors.index.json").write_text(
            json.dumps(self.index), encoding="utf-8"
        )
        self.write_publisher_manifest()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_publisher_manifest(self) -> None:
        names = [
            "config.json",
            "model.safetensors.index.json",
            *sorted(self.tensor_names),
        ]
        (self.source / "SHA256SUMS").write_text(
            "".join(f"{digest(self.source / name)}  {name}\n" for name in names),
            encoding="utf-8",
        )

    def identity_patches(self) -> ExitStack:
        stack = ExitStack()
        shard_bytes = {
            name: (self.source / name).stat().st_size for name in self.tensor_names
        }
        tensor_bytes = {
            name: len(payload)
            for name, payload in zip(self.tensor_names, (b"a", b"bc", b"def"))
        }
        stack.enter_context(mock.patch.object(MODULE, "EXPECTED_MTP_TENSORS", 3))
        stack.enter_context(mock.patch.object(MODULE, "EXPECTED_TOTAL_TENSORS", 4))
        stack.enter_context(
            mock.patch.object(MODULE, "EXPECTED_SOURCE_TENSOR_BYTES", 10)
        )
        stack.enter_context(mock.patch.object(MODULE, "EXPECTED_DRAFT_TENSOR_BYTES", 6))
        stack.enter_context(
            mock.patch.object(MODULE, "EXPECTED_SHARD_BYTES", shard_bytes)
        )
        stack.enter_context(
            mock.patch.object(
                MODULE,
                "EXPECTED_SHARD_TENSORS",
                {name: 1 for name in self.tensor_names},
            )
        )
        stack.enter_context(
            mock.patch.object(MODULE, "EXPECTED_SHARD_TENSOR_BYTES", tensor_bytes)
        )
        stack.enter_context(
            mock.patch.object(
                MODULE.VERIFIER,
                "validate",
                return_value={
                    "status": "pass",
                    "revision": MODULE.REVISION,
                    "crypto_receipt": str(self.receipt.resolve()),
                },
            )
        )
        return stack

    def prepare(self) -> MODULE.Prepared:
        return MODULE.prepare(self.source, self.output, self.staging, self.receipt)

    def test_plan_reads_no_safetensors_payload_and_writes_nothing(self) -> None:
        original_sha256 = MODULE.sha256_file

        def metadata_only_sha256(path: Path) -> str:
            self.assertNotEqual(path.suffix, ".safetensors")
            return original_sha256(path)

        with (
            self.identity_patches(),
            mock.patch.object(MODULE, "sha256_file", side_effect=metadata_only_sha256),
        ):
            prepared = self.prepare()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.staging.exists())
        self.assertFalse(prepared.plan["payload_reads"])
        self.assertFalse(prepared.plan["writes"])
        self.assertEqual(prepared.plan["source"]["revision"], MODULE.REVISION)
        self.assertEqual(prepared.plan["selection"]["tensor_count"], 3)

    def test_completed_receipt_is_mandatory_and_identity_bound(self) -> None:
        missing = self.root / "missing-summary.json"
        with self.assertRaisesRegex(MODULE.PackError, "receipt is missing"):
            MODULE.prepare(self.source, self.output, self.staging, missing)

        with self.identity_patches() as stack:
            stack.enter_context(
                mock.patch.object(
                    MODULE.VERIFIER,
                    "validate",
                    return_value={
                        "status": "pass",
                        "revision": "wrong",
                        "crypto_receipt": str(self.receipt.resolve()),
                    },
                )
            )
            with self.assertRaisesRegex(MODULE.PackError, "ddc04540 receipt"):
                self.prepare()

    def test_selection_rejects_non_mtp_entries_in_selected_shards(self) -> None:
        index = json.loads(json.dumps(self.index))
        index["weight_map"]["embed.weight"] = "model-00046-of-00048.safetensors"
        with (
            self.identity_patches(),
            self.assertRaisesRegex(MODULE.PackError, "non-MTP index entries"),
        ):
            MODULE.select_draft_map(index)

    def test_execute_copies_validates_and_atomically_promotes_tiny_pack(self) -> None:
        with self.identity_patches():
            prepared = self.prepare()
            result = MODULE.execute(prepared, MODULE.ACK)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(self.output.is_dir())
        self.assertFalse(self.staging.exists())
        for name in self.tensor_names:
            destination = self.output / name
            self.assertTrue(destination.is_file())
            self.assertFalse(destination.is_symlink())
            self.assertEqual(
                destination.read_bytes(), (self.source / name).read_bytes()
            )
        draft_index = json.loads(
            (self.output / "model.safetensors.index.json").read_text()
        )
        self.assertEqual(draft_index["metadata"]["total_size"], 6)
        self.assertEqual(
            set(draft_index["weight_map"]), set(self.tensor_names.values())
        )
        manifest = json.loads((self.output / "draft-pack-manifest.json").read_text())
        self.assertEqual(manifest["validation"]["status"], "pass")
        self.assertTrue(manifest["validation"]["destination_full_hashes"])
        self.assertEqual(
            manifest["source"]["validation_receipt"]["sha256"], digest(self.receipt)
        )
        for name in self.tensor_names:
            self.assertEqual(
                manifest["shard_hashes"][name]["source_sha256"],
                digest(self.source / name),
            )
            self.assertEqual(
                manifest["shard_hashes"][name]["destination_sha256"],
                digest(self.output / name),
            )

    def test_execute_requires_ack_and_preserves_absent_staging(self) -> None:
        with self.identity_patches():
            prepared = self.prepare()
            with self.assertRaisesRegex(MODULE.PackError, "requires --ack"):
                MODULE.execute(prepared, "wrong")
        self.assertFalse(self.staging.exists())
        self.assertFalse(self.output.exists())

    def test_execute_rechecks_receipt_before_creating_staging(self) -> None:
        with self.identity_patches():
            prepared = self.prepare()
            (self.receipt_root / MODULE.RECEIPT_SIDECARS[0]).write_text(
                "changed\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(MODULE.PackError, "sidecar changed"):
                MODULE.execute(prepared, MODULE.ACK)
        self.assertFalse(self.staging.exists())
        self.assertFalse(self.output.exists())

    def test_staging_must_be_explicit_output_sibling(self) -> None:
        elsewhere = self.root / "elsewhere" / "staging"
        with (
            self.identity_patches(),
            self.assertRaisesRegex(MODULE.PackError, "explicit sibling"),
        ):
            MODULE.prepare(self.source, self.output, elsewhere, self.receipt)


if __name__ == "__main__":
    unittest.main()
