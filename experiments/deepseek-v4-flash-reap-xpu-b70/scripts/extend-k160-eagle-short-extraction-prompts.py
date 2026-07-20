#!/usr/bin/env python3
"""Append deterministic compact extraction prompts without reordering input."""

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
        rows = [json.loads(line) for line in stream if line.strip()]
    for row in rows:
        if sha(row["prompt"]) != row["prompt_sha256"]:
            raise RuntimeError(f"prompt hash mismatch: {row['prompt_id']}")
    return rows


def compact_extraction_prompt(
    rng: random.Random, index: int, seed: int, split: str
) -> str:
    owners = ("Amina", "Chao", "Eleni", "Hiro", "Kavya", "Marta", "Rina")
    priorities = ("low", "medium", "high", "urgent")
    records = [
        {
            "id": f"R{index:04d}-{row:02d}",
            "owner": rng.choice(owners),
            "priority": rng.choice(priorities),
            "minutes": rng.randrange(2, 600),
        }
        for row in range(rng.randrange(5, 9))
    ]
    return (
        "Return valid JSON only. Group these records under keys low, medium, high, "
        "and urgent. Preserve id, owner, and minutes; order each group by minutes "
        "descending. Add total_minutes equal to the sum across all records.\nRECORDS="
        + json.dumps(records, separators=(",", ":"))
        + f"\nImmutable task nonce: {split}-extraction-short-v4-{index:05d}-{seed}."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-prompts", type=Path, required=True)
    parser.add_argument("--other-prompts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "dev"), required=True)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    if args.count <= 0:
        raise ValueError("count must be positive")
    if args.output.exists() or args.manifest.exists():
        raise FileExistsError("extension output and manifest must not exist")

    base = load_jsonl(args.base_prompts)
    other = load_jsonl(args.other_prompts)
    other_split = "dev" if args.split == "train" else "train"
    if not base or any(row["split"] != args.split for row in base):
        raise RuntimeError("base prompt split is wrong")
    if not other or any(row["split"] != other_split for row in other):
        raise RuntimeError("counterpart prompt split is wrong")

    rng = random.Random(args.seed)
    additions = []
    for index in range(args.count):
        prompt = compact_extraction_prompt(rng, index, args.seed, args.split)
        additions.append(
            {
                "schema_version": "k160-eagle-procedural-prompt-v1",
                "split": args.split,
                "category": "extraction",
                "source_id": "k160-eagle-procedural-extraction-short-v4",
                "source_revision": "2026-07-20",
                "prompt_id": f"{args.split}-extraction-short-v4-{index:05d}",
                "prompt_sha256": sha(prompt),
                "prompt": prompt,
            }
        )
    extended = base + additions
    prompt_ids = [row["prompt_id"] for row in extended]
    prompt_hashes = {row["prompt_sha256"] for row in extended}
    other_ids = {row["prompt_id"] for row in other}
    other_hashes = {row["prompt_sha256"] for row in other}
    if len(prompt_ids) != len(set(prompt_ids)) or set(prompt_ids) & other_ids:
        raise RuntimeError("prompt IDs are not unique and disjoint")
    if len(prompt_hashes) != len(extended) or prompt_hashes & other_hashes:
        raise RuntimeError("prompt hashes are not unique and disjoint")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        for row in extended:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "schema_version": "k160-eagle-prompt-source-extension-v1",
        "policy": "append_only_short_extraction_v4",
        "extended_split": args.split,
        "base_path": str(args.base_prompts.resolve()),
        "base_sha256": file_sha256(args.base_prompts),
        "counterpart_path": str(args.other_prompts.resolve()),
        "counterpart_sha256": file_sha256(args.other_prompts),
        "output_path": str(args.output.resolve()),
        "output_sha256": file_sha256(args.output),
        "base_prompt_count": len(base),
        "added_prompt_count": len(additions),
        "extended_prompt_count": len(extended),
        "extended_prompt_set_sha256": sha("\n".join(sorted(prompt_hashes))),
        "counterpart_prompt_set_sha256": sha("\n".join(sorted(other_hashes))),
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
