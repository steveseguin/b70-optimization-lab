#!/usr/bin/env python3
"""Summarize the frozen Qwen3.8 FP8 strict-profile attempts without inference."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


METRIC = "class_balanced_tok_s_1_100_intervals_after_ttft"


def load_attempt(path: Path) -> dict[str, Any]:
    path = path.resolve()
    performance_path = path / "performance.json"
    canaries_path = path / "canaries.json"
    identity_path = path / "campaign-identity.json"
    performance = json.loads(performance_path.read_text())
    canaries = json.loads(canaries_path.read_text())
    identity = json.loads(identity_path.read_text())
    profile = identity["profile"]
    if identity.get("compile_cache_policy") == "compiled-kernel-replay":
        profile = f"{profile}-sealed-cache"
    rows = {row["prompt_id"]: row for row in performance["rows"]}
    return {
        "path": path,
        "performance_path": performance_path,
        "performance_display_path": str(
            performance_path.relative_to(Path.cwd().resolve())
            if performance_path.is_relative_to(Path.cwd().resolve())
            else performance_path
        ),
        "performance_sha256": hashlib.sha256(performance_path.read_bytes()).hexdigest(),
        "profile": profile,
        "attempt": identity["attempt"],
        "suite_sha256": identity["suite_sha256"],
        "rate": performance["summary"][METRIC]["median"],
        "performance_gate": performance["realistic_final_gate"]["passed"],
        "fresh_response_valid": performance["fresh_response_validity"]["valid"],
        "cached_tokens_all_zero": performance["fresh_response_validity"]["cached_tokens_all_zero"],
        "canaries_pass": canaries["pass_all"],
        "rows": rows,
    }


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if left["suite_sha256"] != right["suite_sha256"]:
        raise ValueError(f"suite mismatch: {left['path']} vs {right['path']}")
    if set(left["rows"]) != set(right["rows"]):
        raise ValueError(f"prompt-set mismatch: {left['path']} vs {right['path']}")
    divergent = []
    for prompt_id in sorted(left["rows"]):
        left_ids = left["rows"][prompt_id]["token_ids"]
        right_ids = right["rows"][prompt_id]["token_ids"]
        if left_ids == right_ids:
            continue
        common = min(len(left_ids), len(right_ids))
        first = next((i for i in range(common) if left_ids[i] != right_ids[i]), common)
        divergent.append(
            {
                "prompt_id": prompt_id,
                "first_divergence_token_zero_based": first,
                "left_token_count": len(left_ids),
                "right_token_count": len(right_ids),
            }
        )
    total = len(left["rows"])
    exact = total - len(divergent)
    return {
        "left": f"{left['profile']}/{left['attempt']}",
        "right": f"{right['profile']}/{right['attempt']}",
        "exact_prompts": exact,
        "total_prompts": total,
        "passed_12_of_12": exact == total,
        "divergent_prompts": divergent,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt_dirs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    attempts = [load_attempt(path.resolve()) for path in args.attempt_dirs]
    groups: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        groups.setdefault(attempt["profile"], []).append(attempt)
    for values in groups.values():
        values.sort(key=lambda item: item["attempt"])

    baseline = next(
        (item for item in attempts if item["profile"] == "mtp0" and item["attempt"] == "r1a"),
        None,
    )
    attempt_rows = []
    pair_comparisons = []
    target_comparisons = []
    for profile in sorted(groups):
        values = groups[profile]
        for item in values:
            attempt_rows.append(
                {
                    "profile": item["profile"],
                    "attempt": item["attempt"],
                    "class_balanced_median_tok_s": item["rate"],
                    "performance_gate": item["performance_gate"],
                    "fresh_response_valid": item["fresh_response_valid"],
                    "cached_tokens_all_zero": item["cached_tokens_all_zero"],
                    "canaries_pass": item["canaries_pass"],
                    "performance_json": item["performance_display_path"],
                    "performance_sha256": item["performance_sha256"],
                }
            )
        if len(values) >= 2:
            pair_comparisons.append(compare(values[0], values[1]))
        if baseline is not None and profile != "mtp0":
            target_comparisons.append(compare(baseline, values[0]))

    pair_by_profile = {entry["left"].split("/")[0]: entry for entry in pair_comparisons}
    profiles = []
    for profile in sorted(groups):
        values = groups[profile]
        pair = pair_by_profile.get(profile)
        qualified = (
            len(values) >= 2
            and all(
                item["performance_gate"]
                and item["fresh_response_valid"]
                and item["cached_tokens_all_zero"]
                and item["canaries_pass"]
                for item in values[:2]
            )
            and pair is not None
            and pair["passed_12_of_12"]
        )
        profiles.append(
            {
                "profile": profile,
                "attempt_count": len(values),
                "strict_headline_qualified": qualified,
                "status": "qualified" if qualified else "withheld",
                "reason": None if qualified else "requires two valid attempts with 12/12 exact token-array agreement",
            }
        )

    result = {
        "schema": "neural.download.qwen38-fp8-strict-matrix-summary.v1",
        "metric": METRIC,
        "policy": {
            "no_extrapolation": True,
            "headline_requires": "two full valid attempts plus 12/12 exact token-array agreement",
            "speculative_target_parity_requires": "12/12 exact token arrays against the frozen MTP0 reference",
        },
        "attempts": attempt_rows,
        "repeat_comparisons": pair_comparisons,
        "target_comparisons": target_comparisons,
        "profiles": profiles,
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
