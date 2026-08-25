#!/usr/bin/env python3
"""Freeze compact token-ID oracle digests from a retained concurrency result."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def token_digest(token_ids: list[int]) -> str:
    payload = json.dumps(token_ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    source_bytes = args.source.read_bytes()
    source = json.loads(source_bytes)
    rows = []
    for row in source["oracle"]["rows"]:
        token_ids = row.get("token_ids")
        count = row.get("completion_tokens")
        if not isinstance(token_ids, list) or count != len(token_ids) or count < 1:
            raise SystemExit(f"incomplete token IDs for {row.get('prompt_id')}")
        rows.append({
            "prompt_id": row["prompt_id"],
            "base_prompt_id": re.sub(r"-c\d+$", "", row["prompt_id"]),
            "prompt_sha256": row["prompt_sha256"],
            "completion_tokens": count,
            "token_ids_sha256": token_digest(token_ids),
        })
    out = {
        "schema": "neural.download.concurrency-token-oracle-digests.v1",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_classification": source.get("classification"),
        "cached_tokens_zero": source["oracle"]["cached_tokens_all_zero"],
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
