#!/usr/bin/env python3
"""Analyze all preregistered independent-validation arms."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
from pathlib import Path
from typing import Any


ARMS = {
    "nospec-01a": {"mode": "nospec", "pair": "0,1"},
    "spec-01a": {"mode": "spec", "pair": "0,1"},
    "nospec-23a": {"mode": "nospec", "pair": "2,3"},
    "spec-23a": {"mode": "spec", "pair": "2,3"},
    "spec-01b": {"mode": "spec", "pair": "0,1"},
    "spec-23b": {"mode": "spec", "pair": "2,3"},
}
GROUPS = {
    "selection": "selection--",
    "holdout": "holdout--",
    "combined": "",
}


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * pct
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def stats(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "median": statistics.median(values),
        "p10": percentile(values, 0.10),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def bootstrap_median(values: list[float], *, samples: int, seed: int) -> dict[str, float | int]:
    rng = random.Random(seed)
    n = len(values)
    medians = [statistics.median(rng.choices(values, k=n)) for _ in range(samples)]
    return {
        "samples": samples,
        "seed": seed,
        "lower_95": percentile(medians, 0.025),
        "median": statistics.median(medians),
        "upper_95": percentile(medians, 0.975),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def row_map(bench: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["prompt_id"]: row for row in bench["rows"]}


def group_rows(bench: dict[str, Any], group: str) -> list[dict[str, Any]]:
    prefix = GROUPS[group]
    return [row for row in bench["rows"] if not prefix or row["prompt_id"].startswith(prefix)]


def exact_compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_rows, right_rows = row_map(left), row_map(right)
    common = sorted(set(left_rows) & set(right_rows))
    mismatches = []
    for prompt_id in common:
        a, b = left_rows[prompt_id], right_rows[prompt_id]
        if a.get("token_ids") != b.get("token_ids"):
            at, bt = a.get("token_ids") or [], b.get("token_ids") or []
            common_prefix = 0
            for x, y in zip(at, bt):
                if x != y:
                    break
                common_prefix += 1
            mismatches.append({
                "prompt_id": prompt_id,
                "common_prefix_tokens": common_prefix,
                "left_tokens": len(at),
                "right_tokens": len(bt),
                "left_first_difference": at[common_prefix] if common_prefix < len(at) else None,
                "right_first_difference": bt[common_prefix] if common_prefix < len(bt) else None,
            })
    return {
        "compared": len(common),
        "expected": 25,
        "exact": len(common) == 25 and not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()

    benches: dict[str, dict[str, Any]] = {}
    qualities: dict[str, dict[str, Any]] = {}
    arm_summaries: dict[str, Any] = {}
    for name, identity in ARMS.items():
        arm = args.root / name
        bench = load_json(arm / "data/bench.json")
        quality = load_json(arm / "data/quality.json")
        benches[name], qualities[name] = bench, quality
        gate = bench.get("realistic_final_gate") or {}
        accounting = bench.get("metric_accounting") or {}
        rows = bench.get("rows") or []
        error_lines = []
        log_path = arm / "run/server.stdout.log"
        log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        for line in log.splitlines():
            if re.search(r"device lost|ze_result_error|traceback|enginecore.*died", line, re.I):
                error_lines.append(line[-500:])
        acceptance = [float(x) for x in re.findall(r"Avg Draft acceptance rate: ([0-9.]+)%", log)]
        group_metrics = {}
        for group in GROUPS:
            selected = group_rows(bench, group)
            rates = [float(row["tok_s_1_100_intervals_after_ttft"]) for row in selected]
            group_metrics[group] = {
                "window_tok_s": stats(rates),
                "ttft_ms": stats([float(row["ttft_s"]) * 1000 for row in selected]),
                "full_after_ttft_tok_s": stats([float(row["tok_s_after_ttft_full"]) for row in selected]),
                "wall_tok_s": stats([float(row["tok_s_wall_full"]) for row in selected]),
                "completion_tokens": stats([float(row["completion_tokens"]) for row in selected]),
            }
        arm_summaries[name] = {
            **identity,
            "gate_passed": bool(gate.get("passed")),
            "cached_tokens_all_zero": bool(gate.get("cached_tokens_all_zero")),
            "accounting": accounting,
            "rows": len(rows),
            "all_rows_have_100_events": all((row.get("stream_token_id_count") or 0) >= 100 for row in rows),
            "quality_pass_all": quality.get("pass_all"),
            "quality_baseline_match_all": quality.get("baseline_match_all"),
            "server_error_lines": error_lines,
            "acceptance_percent": stats(acceptance) if acceptance else None,
            "groups": group_metrics,
        }

    target_parity = {
        "spec-01a_vs_nospec-01a": exact_compare(benches["spec-01a"], benches["nospec-01a"]),
        "spec-01b_vs_nospec-01a": exact_compare(benches["spec-01b"], benches["nospec-01a"]),
        "spec-23a_vs_nospec-23a": exact_compare(benches["spec-23a"], benches["nospec-23a"]),
        "spec-23b_vs_nospec-23a": exact_compare(benches["spec-23b"], benches["nospec-23a"]),
    }
    repeat_parity = {
        "spec-01a_vs_spec-01b": exact_compare(benches["spec-01a"], benches["spec-01b"]),
        "spec-23a_vs_spec-23b": exact_compare(benches["spec-23a"], benches["spec-23b"]),
        "nospec-01a_vs_nospec-23a": exact_compare(benches["nospec-01a"], benches["nospec-23a"]),
    }

    candidate_names = [name for name, item in ARMS.items() if item["mode"] == "spec"]
    aggregate = {}
    for group in GROUPS:
        arm_medians = [arm_summaries[name]["groups"][group]["window_tok_s"]["median"] for name in candidate_names]
        prompt_rates: dict[str, list[float]] = {}
        for name in candidate_names:
            for row in group_rows(benches[name], group):
                prompt_rates.setdefault(row["prompt_id"], []).append(
                    float(row["tok_s_1_100_intervals_after_ttft"])
                )
        per_prompt_medians = [statistics.median(values) for values in prompt_rates.values()]
        aggregate[group] = {
            "candidate_arm_medians": arm_medians,
            "candidate_arm_median_stats": stats(arm_medians),
            "per_prompt_median_stats": stats(per_prompt_medians),
            "prompt_bootstrap_95": bootstrap_median(
                per_prompt_medians, samples=200_000, seed=20260815 + len(per_prompt_medians)
            ),
        }

    all_arm_valid = all(
        item["gate_passed"]
        and item["cached_tokens_all_zero"]
        and item["all_rows_have_100_events"]
        and item["quality_pass_all"] is True
        and not item["server_error_lines"]
        for item in arm_summaries.values()
    )
    all_target_exact = all(item["exact"] for item in target_parity.values())
    all_repeat_exact = all(item["exact"] for item in repeat_parity.values())
    result = {
        "classification": "independent-contribution-style-validation",
        "root": str(args.root),
        "source_plan_commit": "1dfb42afe",
        "suite_sha256": hashlib.sha256((args.root / "nospec-01a/validation-suite.json").read_bytes()).hexdigest(),
        "arms": arm_summaries,
        "candidate_aggregate": aggregate,
        "target_parity": target_parity,
        "repeat_parity": repeat_parity,
        "verdict": {
            "all_arms_valid": all_arm_valid,
            "all_candidate_outputs_target_exact": all_target_exact,
            "all_repeats_exact": all_repeat_exact,
            "strict_validation_passed": all_arm_valid and all_target_exact and all_repeat_exact,
        },
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Independent Qwen3.6 27B INT4 validation result",
        "",
        f"- strict validation passed: **{result['verdict']['strict_validation_passed']}**",
        f"- all arms valid: `{all_arm_valid}`",
        f"- all speculative outputs target-exact: `{all_target_exact}`",
        f"- all same-identity repeats exact: `{all_repeat_exact}`",
        "",
        "## Current-accounting speed",
        "",
        "| Arm | Mode | Pair | Selection median | Holdout median | Combined median |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for name, identity in ARMS.items():
        groups = arm_summaries[name]["groups"]
        lines.append(
            f"| `{name}` | {identity['mode']} | `{identity['pair']}` | "
            f"{groups['selection']['window_tok_s']['median']:.3f} | "
            f"{groups['holdout']['window_tok_s']['median']:.3f} | "
            f"{groups['combined']['window_tok_s']['median']:.3f} |"
        )
    lines.extend(["", "## Candidate aggregate", ""])
    for group, item in aggregate.items():
        s, b = item["candidate_arm_median_stats"], item["prompt_bootstrap_95"]
        lines.append(
            f"- {group}: median of four arm medians `{s['median']:.3f}` tok/s "
            f"(range `{s['min']:.3f}`–`{s['max']:.3f}`); prompt-bootstrap "
            f"95% interval `{b['lower_95']:.3f}`–`{b['upper_95']:.3f}`."
        )
    lines.extend(["", "See `analysis.json` for row groups, quality, parity, acceptance, and errors."])
    args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result["verdict"], sort_keys=True))
    return 0 if result["verdict"]["strict_validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

