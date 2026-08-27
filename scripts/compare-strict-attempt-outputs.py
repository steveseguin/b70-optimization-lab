#!/usr/bin/env python3
"""Compare complete token arrays from two strict benchmark attempts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


METRIC = "class_balanced_tok_s_1_100_intervals_after_ttft"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display(path: Path) -> str:
    path = path.resolve()
    root = Path.cwd().resolve()
    return str(path.relative_to(root) if path.is_relative_to(root) else path)


def load_attempt(root: Path) -> dict[str, Any]:
    root = root.resolve()
    performance_path = root / "performance.json"
    canaries_path = root / "canaries.json"
    identity_path = root / "campaign-identity.json"
    performance = json.loads(performance_path.read_text())
    canaries = json.loads(canaries_path.read_text())
    identity = json.loads(identity_path.read_text())
    suite_sha = identity.get("suite_sha256")
    if suite_sha is None:
        suite_sha = identity.get("artifacts", {}).get("suite", {}).get("sha256")
    if not suite_sha:
        raise ValueError(f"missing suite SHA-256: {identity_path}")
    rows = {row["prompt_id"]: row for row in performance["rows"]}
    return {
        "root": root,
        "identity": identity,
        "suite_sha256": suite_sha,
        "performance": performance,
        "canaries": canaries,
        "rows": rows,
        "performance_path": performance_path,
        "canaries_path": canaries_path,
        "identity_path": identity_path,
    }


def summarize(attempt: dict[str, Any]) -> dict[str, Any]:
    performance = attempt["performance"]
    identity = attempt["identity"]
    metric = performance["summary"][METRIC]["median"]
    return {
        "profile": identity.get("profile"),
        "attempt": identity.get("attempt"),
        "class_balanced_median_tok_s": metric,
        "performance_gate_passed": performance["realistic_final_gate"]["passed"],
        "fresh_response_valid": performance["fresh_response_validity"]["valid"],
        "cached_tokens_all_zero": performance["fresh_response_validity"]["cached_tokens_all_zero"],
        "canaries_passed": attempt["canaries"]["pass_all"],
        "artifacts": {
            "identity": {"path": display(attempt["identity_path"]), "sha256": sha256(attempt["identity_path"])},
            "performance": {"path": display(attempt["performance_path"]), "sha256": sha256(attempt["performance_path"])},
            "canaries": {"path": display(attempt["canaries_path"]), "sha256": sha256(attempt["canaries_path"])},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    left = load_attempt(args.left)
    right = load_attempt(args.right)
    if left["suite_sha256"] != right["suite_sha256"]:
        raise ValueError("attempts use different suite identities")
    if set(left["rows"]) != set(right["rows"]):
        raise ValueError("attempts use different prompt sets")

    divergences = []
    for prompt_id in sorted(left["rows"]):
        left_ids = left["rows"][prompt_id]["token_ids"]
        right_ids = right["rows"][prompt_id]["token_ids"]
        if left_ids == right_ids:
            continue
        common = min(len(left_ids), len(right_ids))
        first = next((i for i in range(common) if left_ids[i] != right_ids[i]), common)
        divergences.append(
            {
                "prompt_id": prompt_id,
                "first_divergence_token_zero_based": first,
                "left_token_count": len(left_ids),
                "right_token_count": len(right_ids),
            }
        )

    left_summary = summarize(left)
    right_summary = summarize(right)
    total = len(left["rows"])
    exact = total - len(divergences)
    gates_pass = all(
        item[key]
        for item in (left_summary, right_summary)
        for key in (
            "performance_gate_passed",
            "fresh_response_valid",
            "cached_tokens_all_zero",
            "canaries_passed",
        )
    )
    result = {
        "schema": "neural.download.strict-attempt-output-comparison.v1",
        "suite_sha256": left["suite_sha256"],
        "left": left_summary,
        "right": right_summary,
        "comparison": {
            "exact_prompts": exact,
            "total_prompts": total,
            "complete_token_arrays_exact": exact == total,
            "divergent_prompts": divergences,
        },
        "qualification": {
            "all_workload_and_canary_gates_passed": gates_pass,
            "strict_pair_qualified": gates_pass and exact == total,
            "required": "both complete fixed-suite attempts pass every workload/canary gate and match every complete token array",
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x") as handle:
            handle.write(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
