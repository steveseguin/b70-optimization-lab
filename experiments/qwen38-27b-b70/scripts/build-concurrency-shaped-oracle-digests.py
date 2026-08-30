#!/usr/bin/env python3
"""Freeze compact token-ID digests from one retained concurrency batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def token_digest(token_ids: list[int]) -> str:
    payload = json.dumps(token_ids, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")

    source_bytes = args.source.read_bytes()
    source = json.loads(source_bytes)
    matches = [
        batch
        for batch in source["batches"]
        if batch.get("concurrency") == args.concurrency
        and batch.get("repeat") == args.repeat
    ]
    if len(matches) != 1:
        raise SystemExit(f"expected one matching batch, got {len(matches)}")
    batch = matches[0]
    rows = []
    for row in batch["rows"]:
        tokens = row.get("token_ids")
        count = row.get("completion_tokens")
        if not isinstance(tokens, list) or count != len(tokens) or count != 128:
            raise SystemExit(f"incomplete token IDs for {row.get('prompt_id')}")
        rows.append(
            {
                "base_prompt_id": re.sub(r"-c[0-9]+$", "", row["prompt_id"]),
                "prompt_id": row["prompt_id"],
                "prompt_sha256": row["prompt_sha256"],
                "completion_tokens": count,
                "token_ids_sha256": token_digest(tokens),
            }
        )
    if len(rows) != args.concurrency:
        raise SystemExit(f"expected {args.concurrency} rows, got {len(rows)}")
    if batch.get("cached_tokens_all_zero") is not True:
        raise SystemExit("source batch is not cache-zero")

    out = {
        "schema": "neural.download.concurrency-token-oracle-digests.v1",
        "oracle_shape": {
            "concurrency": args.concurrency,
            "repeat": args.repeat,
        },
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_classification": source.get("classification"),
        "cached_tokens_zero": True,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
