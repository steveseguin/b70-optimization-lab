#!/usr/bin/env python3
"""Append deterministic short low-locality prompts without reordering input."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def short_prompt(rng: random.Random, index: int, seed: int, split: str) -> str:
    stems = (
        "amber birch cobalt delta ember flint grove harbor iris juniper kepler "
        "linen morrow north opal prairie quartz river sable tundra umber violet "
        "willow xenon yellow zephyr"
    ).split()
    count = rng.randrange(48, 73)
    entries = [
        f"{rng.choice(stems)}-{rng.randrange(10000, 99999)}-{position:02d}"
        for position in range(count)
    ]
    order = list(range(count))
    rng.shuffle(order)
    selected = order[: rng.randrange(34, min(55, count) + 1)]
    return (
        "Copy exactly the referenced entries from SOURCE in INDEX_SEQUENCE order. "
        "Emit one entry per line with no numbering, punctuation changes, or extra "
        "text.\nSOURCE:\n"
        + "\n".join(f"{position}: {entry}" for position, entry in enumerate(entries))
        + "\nINDEX_SEQUENCE:\n"
        + ",".join(map(str, selected))
        + f"\nImmutable task nonce: {split}-low-locality-short-{index:05d}-{seed}."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-prompts", "--base-train", dest="base_train", type=Path, required=True
    )
    parser.add_argument(
        "--other-prompts", "--dev", dest="dev", type=Path, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=160721)
    parser.add_argument("--split", choices=("train", "dev"), default="train")
    args = parser.parse_args()
    if args.output.exists() or args.manifest.exists():
        raise FileExistsError("extension output and manifest must not exist")

    train = load_jsonl(args.base_train)
    dev = load_jsonl(args.dev)
    if not train or not dev:
        raise RuntimeError("base and counterpart prompt manifests must be nonempty")
    if any(row["split"] != args.split for row in train):
        raise RuntimeError("base prompt split does not match --split")
    counterpart_split = "dev" if args.split == "train" else "train"
    if any(row["split"] != counterpart_split for row in dev):
        raise RuntimeError("counterpart prompt split is wrong")
    rng = random.Random(args.seed)
    additions = []
    for index in range(args.count):
        prompt = short_prompt(rng, index, args.seed, args.split)
        additions.append(
            {
                "schema_version": "k160-eagle-procedural-prompt-v1",
                "split": args.split,
                "category": "low-locality",
                "source_id": "k160-eagle-procedural-low-locality-short-v2",
                "source_revision": "2026-07-20",
                "prompt_id": f"{args.split}-low-locality-short-{index:05d}",
                "prompt_sha256": sha(prompt),
                "prompt": prompt,
            }
        )
    extended = train + additions
    prompt_ids = [row["prompt_id"] for row in extended]
    train_hashes = {row["prompt_sha256"] for row in extended}
    dev_hashes = {row["prompt_sha256"] for row in dev}
    if len(prompt_ids) != len(set(prompt_ids)):
        raise RuntimeError("extended train prompt IDs are not unique")
    if len(train_hashes) != len(extended):
        raise RuntimeError("extended train prompt hashes are not unique")
    if train_hashes & dev_hashes:
        raise RuntimeError("extended train and DEV prompt hashes overlap")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        for row in extended:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "schema_version": "k160-eagle-prompt-source-extension-v1",
        "policy": "append_only_short_low_locality_v2",
        "extended_split": args.split,
        "base_train_path": str(args.base_train.resolve()),
        "base_train_sha256": file_sha256(args.base_train),
        "dev_path": str(args.dev.resolve()),
        "dev_sha256": file_sha256(args.dev),
        "output_path": str(args.output.resolve()),
        "output_sha256": file_sha256(args.output),
        "base_train_prompt_count": len(train),
        "added_prompt_count": len(additions),
        "extended_train_prompt_count": len(extended),
        "extended_train_prompt_set_sha256": sha("\n".join(sorted(train_hashes))),
        "dev_prompt_set_sha256": sha("\n".join(sorted(dev_hashes))),
        "disjoint": True,
        "seed": args.seed,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("x") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
