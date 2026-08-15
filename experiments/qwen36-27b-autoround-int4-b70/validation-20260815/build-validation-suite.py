#!/usr/bin/env python3
"""Build the frozen interleaved selection-plus-holdout validation suite."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SELECTION_SHA256 = "df03f49d36c36d2b8ac4cd117b7cb2e42c74878af1f6926690ebb89eeccd47ac"
HOLDOUT_SHA256 = "9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, expected: str) -> list[dict[str, str]]:
    actual = digest(path)
    if actual != expected:
        raise SystemExit(f"suite hash mismatch for {path}: {actual}")
    data = json.loads(path.read_text(encoding="utf-8"))
    prompts = data.get("prompts")
    if not isinstance(prompts, list):
        raise SystemExit(f"invalid suite structure: {path}")
    return prompts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    selection_path = args.repo / "repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json"
    holdout_path = args.repo / "experiments/laguna-s-2.1-xpu-b70/realistic-suite-v1.json"
    selection = load(selection_path, SELECTION_SHA256)
    holdout = load(holdout_path, HOLDOUT_SHA256)

    prompts: list[dict[str, str]] = []
    for index in range(max(len(selection), len(holdout))):
        if index < len(selection):
            item = selection[index]
            prompts.append({
                "id": f"selection--{item['id']}",
                "group": "historical-selection",
                "original_id": item["id"],
                "prompt": item["prompt"],
            })
        if index < len(holdout):
            item = holdout[index]
            prompts.append({
                "id": f"holdout--{item['id']}",
                "group": "independent-holdout",
                "original_id": item["id"],
                "prompt": item["prompt"],
            })

    result = {
        "suite_id": "qwen36-27b-int4-independent-validation-20260815-v1",
        "version": 1,
        "description": (
            "Preregistered interleaving of the historical 12-prompt selection "
            "suite and a later independent 13-prompt mixed-task holdout."
        ),
        "metric": "99 inter-token intervals between generated events 1 and 100 after TTFT",
        "source_suites": [
            {"group": "historical-selection", "path": str(selection_path), "sha256": SELECTION_SHA256},
            {"group": "independent-holdout", "path": str(holdout_path), "sha256": HOLDOUT_SHA256},
        ],
        "prompts": prompts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.out)
    print(f"sha256={digest(args.out)}")
    print(f"prompts={len(prompts)} selection={len(selection)} holdout={len(holdout)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

