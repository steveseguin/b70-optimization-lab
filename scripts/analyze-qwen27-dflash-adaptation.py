#!/usr/bin/env python3
"""Paired clustered analysis for offline Qwen27 DFlash adaptation screens."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260710)
    return parser.parse_args()


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot take a percentile of an empty list")
    position = quantile * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def record_key(record: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(record["prompt_id"]),
        str(record["sample"]),
        int(record["start"]),
    )


def paired_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    baseline = {
        record_key(row): row for row in summary["baseline"].get("records", [])
    }
    final = {record_key(row): row for row in summary["final"].get("records", [])}
    if baseline.keys() != final.keys():
        missing_final = sorted(baseline.keys() - final.keys())[:5]
        missing_base = sorted(final.keys() - baseline.keys())[:5]
        raise ValueError(
            f"Unpaired records: missing_final={missing_final}, "
            f"missing_baseline={missing_base}"
        )
    rows = []
    for key in sorted(baseline):
        before = baseline[key]
        after = final[key]
        rows.append(
            {
                "prompt_id": key[0],
                "sample": key[1],
                "start": key[2],
                "family": str(after["family"]),
                "baseline": int(before["accepted_drafts"]),
                "candidate": int(after["accepted_drafts"]),
                "delta": int(after["accepted_drafts"])
                - int(before["accepted_drafts"]),
            }
        )
    return rows


def cluster_means(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(float(row["delta"]))
    return {key: sum(values) / len(values) for key, values in groups.items()}


def bootstrap_cluster_means(
    means: dict[str, float], *, samples: int, rng: random.Random
) -> list[float]:
    keys = sorted(means)
    return [
        sum(means[rng.choice(keys)] for _ in keys) / len(keys)
        for _ in range(samples)
    ]


def sign_flip_pvalue(
    means: dict[str, float], *, samples: int, rng: random.Random
) -> float:
    values = list(means.values())
    observed = sum(values) / len(values)
    if observed <= 0:
        return 1.0
    nonpositive = 0
    for _ in range(samples):
        null_mean = sum(value * rng.choice((-1.0, 1.0)) for value in values) / len(
            values
        )
        if null_mean >= observed:
            nonpositive += 1
    return (nonpositive + 1) / (samples + 1)


def holm_adjust(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for index, (label, value) in enumerate(ordered):
        candidate = min(1.0, value * (count - index))
        running = max(running, candidate)
        adjusted[label] = running
    return adjusted


def analyze_one(
    path: str, *, samples: int, seed: int
) -> tuple[str, dict[str, Any], float]:
    summary = json.loads(Path(path).read_text())
    rows = paired_rows(summary)
    prompt_means = cluster_means(rows, "prompt_id")
    family_means = cluster_means(rows, "family")
    prompt_boot = bootstrap_cluster_means(
        prompt_means, samples=samples, rng=random.Random(seed)
    )
    family_boot = bootstrap_cluster_means(
        family_means, samples=samples, rng=random.Random(seed + 1)
    )
    raw_mean = sum(float(row["delta"]) for row in rows) / len(rows)
    label = Path(path).parent.name
    pvalue = sign_flip_pvalue(
        prompt_means, samples=samples, rng=random.Random(seed + 2)
    )
    result = {
        "label": label,
        "summary": str(Path(path).resolve()),
        "paired_anchors": len(rows),
        "prompt_clusters": len(prompt_means),
        "family_clusters": len(family_means),
        "baseline_visible_tokens_per_step": summary["baseline"][
            "visible_tokens_per_step"
        ],
        "candidate_visible_tokens_per_step": summary["final"][
            "visible_tokens_per_step"
        ],
        "raw_mean_delta_accepted_drafts": raw_mean,
        "prompt_cluster_mean_delta": sum(prompt_means.values()) / len(prompt_means),
        "prompt_cluster_bootstrap_95_ci": [
            percentile(prompt_boot, 0.025),
            percentile(prompt_boot, 0.975),
        ],
        "prompt_cluster_one_sided_95_lcb": percentile(prompt_boot, 0.05),
        "family_cluster_mean_delta": sum(family_means.values()) / len(family_means),
        "family_cluster_bootstrap_95_ci": [
            percentile(family_boot, 0.025),
            percentile(family_boot, 0.975),
        ],
        "one_sided_prompt_cluster_sign_flip_p": pvalue,
        "positive_anchor_fraction": sum(row["delta"] > 0 for row in rows)
        / len(rows),
        "negative_anchor_fraction": sum(row["delta"] < 0 for row in rows)
        / len(rows),
        "zero_anchor_fraction": sum(row["delta"] == 0 for row in rows) / len(rows),
    }
    return label, result, pvalue


def main() -> int:
    args = parse_args()
    analyses = []
    pvalues = {}
    for index, path in enumerate(args.summary):
        label, result, pvalue = analyze_one(
            path,
            samples=args.bootstrap_samples,
            seed=args.seed + index * 100,
        )
        analyses.append(result)
        pvalues[label] = pvalue
    adjusted = holm_adjust(pvalues)
    for result in analyses:
        result["holm_adjusted_one_sided_p"] = adjusted[result["label"]]
        result["statistically_positive"] = bool(
            result["prompt_cluster_one_sided_95_lcb"] > 0
            and adjusted[result["label"]] < 0.05
        )
    output = {
        "classification": "diagnostic_paired_dflash_acceptance_not_endpoint_not_localmaxxing",
        "bootstrap_samples": args.bootstrap_samples,
        "seed": args.seed,
        "multiple_comparison_correction": "Holm over one-sided prompt-cluster sign-flip p-values",
        "candidates": analyses,
    }
    Path(args.out).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
