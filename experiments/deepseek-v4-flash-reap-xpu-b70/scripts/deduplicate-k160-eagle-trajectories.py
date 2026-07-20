#!/usr/bin/env python3
"""Promote first-occurrence-only K160 trajectories without altering raw data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def completion_tokens(row: dict[str, Any]) -> int:
    return int(row["response"]["usage"].get("completion_tokens") or 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    if args.output.exists() or args.summary.exists():
        raise FileExistsError("output and summary must not already exist")

    seen: dict[str, dict[str, Any]] = {}
    clean_rows: list[dict[str, Any]] = []
    raw_rows = 0
    raw_tokens = 0
    duplicate_rows = 0
    duplicate_tokens = 0
    duplicate_prompt_ids: Counter[str] = Counter()

    with args.input.open() as stream:
        for expected_index, line in enumerate(stream):
            if not line.strip():
                continue
            row = json.loads(line)
            raw_rows += 1
            tokens = completion_tokens(row)
            raw_tokens += tokens
            if int(row["request_index"]) != expected_index:
                raise RuntimeError("raw request_index sequence is not contiguous")
            prompt_id = str(row["prompt_id"])
            if prompt_id in seen:
                first = seen[prompt_id]
                immutable_fields = (
                    "split",
                    "category",
                    "prompt_sha256",
                    "source_id",
                    "source_revision",
                    "prompt_token_ids",
                )
                if any(row.get(field) != first.get(field) for field in immutable_fields):
                    raise RuntimeError(
                        f"duplicate prompt metadata differs for {prompt_id}"
                    )
                duplicate_rows += 1
                duplicate_tokens += tokens
                duplicate_prompt_ids[prompt_id] += 1
                continue
            seen[prompt_id] = row
            promoted = dict(row)
            promoted["original_request_index"] = int(row["request_index"])
            promoted["request_index"] = len(clean_rows)
            clean_rows.append(promoted)

    category_tokens: Counter[str] = Counter()
    for row in clean_rows:
        category = str(row["category"])
        category_tokens[category] += completion_tokens(row)
        row["cumulative_category_tokens"] = category_tokens[category]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        for row in clean_rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "schema_version": "k160-eagle-trajectory-dedup-v1",
        "policy": "retain_first_prompt_id_occurrence",
        "input_path": str(args.input.resolve()),
        "input_sha256": file_sha256(args.input),
        "output_path": str(args.output.resolve()),
        "output_sha256": file_sha256(args.output),
        "raw_rows": raw_rows,
        "raw_completion_tokens": raw_tokens,
        "promoted_rows": len(clean_rows),
        "promoted_completion_tokens": sum(category_tokens.values()),
        "duplicate_rows_removed": duplicate_rows,
        "duplicate_completion_tokens_removed": duplicate_tokens,
        "duplicate_prompt_ids": len(duplicate_prompt_ids),
        "category_completion_tokens": dict(sorted(category_tokens.items())),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.summary.open("x") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
