#!/usr/bin/env python3
"""Build a draft-only DeepSeek V4 DSpark pack from selected HF shards."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


EXPECTED_STAGES = {"0", "1", "2"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_exclusive(path: Path, payload: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    config_path = source / "config.json"
    index_path = source / "model.safetensors.index.json"
    if output.exists():
        raise SystemExit(f"refusing to overwrite draft pack: {output}")
    if not config_path.is_file() or not index_path.is_file():
        raise SystemExit("source must contain config.json and safetensors index")

    config = json.loads(config_path.read_text())
    index = json.loads(index_path.read_text())
    full_map = index.get("weight_map")
    if not isinstance(full_map, dict):
        raise SystemExit("invalid safetensors index: missing weight_map")
    draft_map = {
        name: shard for name, shard in full_map.items() if name.startswith("mtp.")
    }
    stages = {name.split(".", 2)[1] for name in draft_map}
    if stages != EXPECTED_STAGES:
        raise SystemExit(f"expected DSpark stages {EXPECTED_STAGES}, got {stages}")
    required_config = {
        "dspark_block_size": 5,
        "dspark_markov_rank": 256,
        "dspark_target_layer_ids": [40, 41, 42],
        "hidden_size": 4096,
        "vocab_size": 129280,
    }
    mismatched = {
        key: {"expected": value, "actual": config.get(key)}
        for key, value in required_config.items()
        if config.get(key) != value
    }
    if mismatched:
        raise SystemExit(f"unexpected DSpark config: {mismatched}")

    shard_names = sorted(set(draft_map.values()))
    shard_paths = [source / name for name in shard_names]
    missing = [str(path) for path in shard_paths if not path.is_file()]
    if missing:
        raise SystemExit(f"missing DSpark shard files: {missing}")

    output.mkdir(parents=True)
    write_exclusive(output / "config.json", json.dumps(config, indent=2) + "\n")
    draft_index = {
        "metadata": {
            **(index.get("metadata") or {}),
            "draft_only": True,
            "draft_prefix": "mtp.",
        },
        "weight_map": draft_map,
    }
    write_exclusive(
        output / "model.safetensors.index.json",
        json.dumps(draft_index, indent=2, sort_keys=True) + "\n",
    )
    for source_shard in shard_paths:
        (output / source_shard.name).symlink_to(source_shard)

    manifest = {
        "schema_version": 1,
        "classification": "deepseek_v4_dspark_draft_only_pack",
        "source": str(source),
        "source_revision": args.revision,
        "weight_prefix": "mtp.",
        "weight_count": len(draft_map),
        "stages": sorted(stages),
        "logical_shard_bytes": sum(path.stat().st_size for path in shard_paths),
        "files": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in [config_path, index_path, *shard_paths]
        ],
    }
    write_exclusive(
        output / "draft-pack-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
