#!/usr/bin/env python3
"""Cheap fail-closed restart verifier for the pinned 0731 K160 checkpoint.

This validates immutable metadata, inventory, sizes, and the full-hash receipt.
It deliberately does not reread 108 GB on every launch.  The one-time payload
hash/header pass is owned by validate-20260826-pinned-hf-downloads.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


REVISION = "ddc04540efda3d2a0788b129f1fad828ddc19b60"
TREE_SHA256 = "443198b60bf8215efe1e487644e4b3d67cf4069ea572b5795630f76c6f47ea6b"
SOURCE_REVISION = "9e165c30e2704aec5d9d593cce3eebd58bbef1cb"
EXPECTED = {
    "files": 80,
    "bytes": 107_818_438_413,
    "shards": 48,
    "shard_bytes": 107_808_354_264,
    "tensors": 45_821,
    "tensor_bytes": 107_803_320_952,
    "mtp_tensors": 2_977,
}
EVIDENCE_ROOT = Path(
    "/home/steve/llm-optimizations/data/model-intake/post-download-validation-20260826"
)


class VerificationError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read JSON {path}: {exc}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(name: object) -> bool:
    if not isinstance(name, str) or not name or "\0" in name or "\\" in name:
        return False
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def load_jsonl(path: Path) -> list[Any]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read JSONL {path}: {exc}") from exc


def validate_full_receipt(
    path: Path,
    model_root: Path,
    expected_files: set[str],
    expected_shards: set[str],
) -> None:
    path = path.resolve()
    if path.name != "summary.json" or path.parent.parent != EVIDENCE_ROOT:
        raise VerificationError("full validation receipt is outside the pinned evidence root")
    receipt = load_json(path)
    if (
        receipt.get("format") != "b70-pinned-hf-post-download-validation-v1"
        or receipt.get("status") != "pass"
        or not receipt.get("completed_utc")
    ):
        raise VerificationError("full validation receipt is not a pass")
    targets = receipt.get("plan", {}).get("targets", [])
    matching = [entry for entry in targets if entry.get("id") == "deepseek-v4-flash-0731-reap"]
    if len(matching) != 1:
        raise VerificationError("receipt does not bind exactly one 0731 target")
    target = matching[0]
    if (
        target.get("revision") != REVISION
        or target.get("tree_sha256") != TREE_SHA256
        or target.get("repo_id") != "0xSero/DeepSeek-V4-Flash-0731-REAP"
        or target.get("root") != str(model_root.resolve())
        or target.get("file_count") != EXPECTED["files"]
        or target.get("total_bytes") != EXPECTED["bytes"]
        or target.get("shard_count") != EXPECTED["shards"]
        or target.get("shard_bytes") != EXPECTED["shard_bytes"]
        or target.get("tensor_count") != EXPECTED["tensors"]
        or target.get("index_total_size") != EXPECTED["tensor_bytes"]
    ):
        raise VerificationError("receipt target identity mismatch")
    hashes = path.parent / "deepseek-v4-flash-0731-reap-hashes.jsonl"
    headers = path.parent / "deepseek-v4-flash-0731-reap-headers.jsonl"
    dry_run = path.parent / "deepseek-v4-flash-0731-reap-dry-run.stdout.json"
    if not hashes.is_file() or not headers.is_file() or not dry_run.is_file():
        raise VerificationError("full validation receipt sidecars are incomplete")
    hash_rows = load_jsonl(hashes)
    header_rows = load_jsonl(headers)
    dry_rows = load_json(dry_run)
    if (
        len(hash_rows) != EXPECTED["files"]
        or any(not isinstance(row, dict) or row.get("status") != "pass" for row in hash_rows)
        or {row.get("file") for row in hash_rows} != expected_files
        or len(header_rows) != EXPECTED["shards"]
        or any(not isinstance(row, dict) or row.get("status") != "pass" for row in header_rows)
        or {row.get("file") for row in header_rows} != expected_shards
        or not isinstance(dry_rows, list)
        or len(dry_rows) != EXPECTED["files"]
        or any(not isinstance(row, dict) or row.get("size") != "-" for row in dry_rows)
        or {row.get("file") for row in dry_rows} != expected_files
    ):
        raise VerificationError("full validation receipt sidecar content mismatch")


def validate(root: Path, receipt: Path | None) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise VerificationError(f"model root is not a directory: {root}")
    incomplete = list((root / ".cache/huggingface/download").rglob("*.incomplete"))
    if incomplete:
        raise VerificationError(f"incomplete Hugging Face artifacts remain: {len(incomplete)}")

    tree_path = root / ".cache/huggingface/trees" / f"{REVISION}.json"
    if sha256(tree_path) != TREE_SHA256:
        raise VerificationError("pinned Hugging Face tree metadata hash mismatch")
    tree = load_json(tree_path)
    files = tree.get("files") if isinstance(tree, dict) else None
    if not isinstance(files, dict) or len(files) != EXPECTED["files"]:
        raise VerificationError("pinned file inventory count mismatch")
    if any(not safe_relative(name) or not isinstance(meta, dict) for name, meta in files.items()):
        raise VerificationError("unsafe or malformed pinned inventory entry")
    if sum(meta.get("size", -1) for meta in files.values()) != EXPECTED["bytes"]:
        raise VerificationError("pinned inventory byte count mismatch")
    for name, meta in files.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != meta["size"]:
            raise VerificationError(f"missing, linked, or wrong-sized artifact: {name}")

    config = load_json(root / "config.json")
    config_expected = {
        "architectures": ["DeepseekV4ForCausalLM"],
        "model_type": "deepseek_v4",
        "num_hidden_layers": 43,
        "hidden_size": 4096,
        "moe_intermediate_size": 2048,
        "n_routed_experts": 160,
        "num_experts_per_tok": 6,
        "dspark_target_layer_ids": [40, 41, 42],
        "dspark_block_size": 5,
        "dspark_markov_rank": 256,
        "max_position_embeddings": 1_048_576,
    }
    bad = {key: config.get(key) for key, value in config_expected.items() if config.get(key) != value}
    if bad:
        raise VerificationError(f"config identity mismatch: {bad}")
    quant = config.get("quantization_config", {})
    if quant != {
        "activation_scheme": "dynamic",
        "fmt": "e4m3",
        "quant_method": "fp8",
        "scale_fmt": "ue8m0",
        "weight_block_size": [128, 128],
    }:
        raise VerificationError("quantization identity mismatch")

    index = load_json(root / "model.safetensors.index.json")
    weight_map = index.get("weight_map") if isinstance(index, dict) else None
    if not isinstance(weight_map, dict) or len(weight_map) != EXPECTED["tensors"]:
        raise VerificationError("safetensors index tensor count mismatch")
    if int(index.get("metadata", {}).get("total_size", -1)) != EXPECTED["tensor_bytes"]:
        raise VerificationError("safetensors index byte count mismatch")
    expected_shards = {f"model-{number:05d}-of-00048.safetensors" for number in range(1, 49)}
    if set(weight_map.values()) != expected_shards:
        raise VerificationError("safetensors index shard closure mismatch")
    mtp_names = [name for name in weight_map if name.startswith("mtp.")]
    if len(mtp_names) != EXPECTED["mtp_tensors"]:
        raise VerificationError("DSpark tensor count mismatch")
    if {weight_map[name] for name in mtp_names} != {
        "model-00046-of-00048.safetensors",
        "model-00047-of-00048.safetensors",
        "model-00048-of-00048.safetensors",
    }:
        raise VerificationError("DSpark shard placement mismatch")
    shard_bytes = sum((root / name).stat().st_size for name in expected_shards)
    if shard_bytes != EXPECTED["shard_bytes"]:
        raise VerificationError("shard byte count mismatch")

    reap = load_json(root / "REAP_MANIFEST.json")
    if (
        reap.get("source_model") != "deepseek-ai/DeepSeek-V4-Flash-0731"
        or reap.get("source_revision") != SOURCE_REVISION
        or reap.get("kept_experts_per_layer") != 160
        or reap.get("original_experts_per_layer") != 256
        or reap.get("dspark_mtp_target_layers") != [40, 41, 42]
    ):
        raise VerificationError("REAP provenance mismatch")
    structural = load_json(root / "validation/structural-validation.json")
    if (
        structural.get("status") != "pass"
        or structural.get("scopes") != 46
        or structural.get("tensor_count") != EXPECTED["tensors"]
        or structural.get("tensor_bytes") != EXPECTED["tensor_bytes"]
    ):
        raise VerificationError("publisher structural receipt mismatch")

    checksum_lines = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    pattern = re.compile(r"^[0-9a-f]{64}  (.+)$")
    covered: set[str] = set()
    for line in checksum_lines:
        match = pattern.fullmatch(line)
        if not match or not safe_relative(match.group(1)) or match.group(1) in covered:
            raise VerificationError("malformed publisher checksum manifest")
        covered.add(match.group(1))
    if covered != set(files) - {"SHA256SUMS"}:
        raise VerificationError("publisher checksum coverage mismatch")

    if receipt is not None:
        validate_full_receipt(receipt, root, set(files), expected_shards)
    return {
        "status": "pass",
        "classification": "cheap_restart_identity_and_inventory",
        "crypto_receipt": str(receipt.resolve()) if receipt else "pending",
        "model_root": str(root),
        "revision": REVISION,
        "files": EXPECTED["files"],
        "bytes": EXPECTED["bytes"],
        "shards": EXPECTED["shards"],
        "tensors": EXPECTED["tensors"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    receipt_default = os.environ.get("DEEPSEEK_0731_VALIDATION_SUMMARY")
    parser.add_argument(
        "--full-validation-summary",
        type=Path,
        default=Path(receipt_default) if receipt_default else None,
    )
    parser.add_argument("--allow-pending-crypto", action="store_true")
    args = parser.parse_args()
    if args.full_validation_summary is None and not args.allow_pending_crypto:
        raise VerificationError("a passing full validation summary is required")
    print(json.dumps(validate(args.model, args.full_validation_summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
