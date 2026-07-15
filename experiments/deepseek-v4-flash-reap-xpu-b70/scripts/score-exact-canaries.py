#!/usr/bin/env python3
"""Score the ordered exact-output DeepSeek promotion canaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    capture = json.loads(args.capture.read_text(encoding="utf-8"))
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    observed = {
        row["id"]: str(row.get("content") or "").strip()
        for row in capture["rows"]
    }
    expected = {row["id"]: row["expected"] for row in suite["prompts"]}
    exact_by_id = {
        prompt_id: observed.get(prompt_id) == value
        for prompt_id, value in expected.items()
    }
    result = {
        "capture": str(args.capture),
        "suite": str(args.suite),
        "cached_tokens_all_zero": capture.get("cached_tokens_all_zero") is True,
        "exact_by_id": exact_by_id,
        "observed": observed,
        "passed": (
            capture.get("cached_tokens_all_zero") is True
            and all(exact_by_id.values())
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
