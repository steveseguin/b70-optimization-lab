#!/usr/bin/env python3
"""Audit repeated raw trajectory prompts and preserve response divergence evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def response_signature(row: dict[str, Any]) -> dict[str, Any]:
    response = row["response"]
    token_ids = [int(value) for value in response["output_token_ids"]]
    token_bytes = json.dumps(token_ids, separators=(",", ":")).encode()
    return {
        "completion_tokens": int(response["usage"]["completion_tokens"]),
        "finish_reason": response["finish_reason"],
        "output_sha256": response["output_sha256"],
        "output_token_ids_sha256": hashlib.sha256(token_bytes).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)

    first_by_prompt: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    prompt_id_by_hash: dict[str, str] = {}
    duplicate_rows = []
    hash_aliases = []
    raw_rows = 0
    with args.input.open() as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            raw_rows += 1
            prompt_id = row["prompt_id"]
            prompt_hash = row["prompt_sha256"]
            prior_prompt_id = prompt_id_by_hash.setdefault(prompt_hash, prompt_id)
            if prior_prompt_id != prompt_id:
                hash_aliases.append(
                    {
                        "prompt_sha256": prompt_hash,
                        "first_prompt_id": prior_prompt_id,
                        "alias_prompt_id": prompt_id,
                    }
                )
            signature = response_signature(row)
            if prompt_id not in first_by_prompt:
                first_by_prompt[prompt_id] = (row, signature)
                continue
            first, first_signature = first_by_prompt[prompt_id]
            immutable_fields = (
                "split",
                "category",
                "prompt_sha256",
                "source_id",
                "source_revision",
                "prompt_token_ids",
                "max_tokens",
            )
            metadata_equal = all(
                row.get(field) == first.get(field) for field in immutable_fields
            )
            duplicate_rows.append(
                {
                    "prompt_id": prompt_id,
                    "retained_raw_request_index": int(first["request_index"]),
                    "removed_raw_request_index": int(row["request_index"]),
                    "metadata_equal": metadata_equal,
                    "response_equal": signature == first_signature,
                    "retained_response": first_signature,
                    "removed_response": signature,
                }
            )

    result = {
        "schema_version": "k160-eagle-duplicate-response-audit-v1",
        "input_path": str(args.input.resolve()),
        "input_sha256": file_sha256(args.input),
        "raw_rows": raw_rows,
        "unique_prompt_ids": len(first_by_prompt),
        "duplicate_rows": len(duplicate_rows),
        "metadata_mismatch_rows": sum(
            not row["metadata_equal"] for row in duplicate_rows
        ),
        "response_divergence_rows": sum(
            not row["response_equal"] for row in duplicate_rows
        ),
        "distinct_prompt_hash_aliases": hash_aliases,
        "duplicate_lineage": duplicate_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"duplicate_lineage", "distinct_prompt_hash_aliases"}
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
