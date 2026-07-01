#!/usr/bin/env python3
"""Analyze Gemma realistic-suite repeatability or paired A/B results.

The realistic final gate reports a median across prompts, but the per-prompt
rows are more useful for close calls. This script compares runs by prompt ID /
prompt hash, reports same-recipe noise, and bootstraps paired control-vs-
candidate ratios so small "wins" are not promoted from single-run variance.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


PRIMARY = "tok_s_1_100_after_ttft"
FULL = "tok_s_after_ttft_full"
WALL = "tok_s_wall_full"
TTFT = "ttft_s"


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def stat(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
            "min": None,
            "max": None,
            "stdev": None,
            "cv_pct": None,
        }
    mean = statistics.fmean(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "count": len(values),
        "mean": mean,
        "median": statistics.median(values),
        "p10": percentile(values, 0.10),
        "p90": percentile(values, 0.90),
        "min": min(values),
        "max": max(values),
        "stdev": stdev,
        "cv_pct": None if mean == 0 else (stdev / mean) * 100.0,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def resolve_suite_path(path: Path, payload: dict[str, Any]) -> Path:
    if "rows" in payload and "realistic_final_gate" in payload:
        return path
    bench_path = payload.get("bench_path")
    if not bench_path:
        raise SystemExit(f"{path}: not a realistic-suite JSON or summary with bench_path")
    suite_path = Path(str(bench_path))
    if not suite_path.is_absolute():
        suite_path = path.parent / suite_path
    if not suite_path.exists():
        raise SystemExit(f"{path}: bench_path does not exist: {suite_path}")
    return suite_path


def load_run(path: Path, *, allow_invalid: bool) -> dict[str, Any]:
    original = path
    payload = read_json(path)
    suite_path = resolve_suite_path(path, payload)
    if suite_path != path:
        payload = read_json(suite_path)
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"{suite_path}: missing realistic-suite rows")

    gate = payload.get("realistic_final_gate") or {}
    valid = bool(gate.get("passed")) and bool(gate.get("cached_tokens_all_zero"))
    if not valid and not allow_invalid:
        raise SystemExit(
            f"{suite_path}: realistic gate/cached-token check failed "
            "(use --allow-invalid only for forensic analysis)"
        )

    label = None
    if isinstance(original, Path):
        label = original.parent.name if original.name == "summary.json" else original.parent.name
    by_prompt: dict[str, dict[str, Any]] = {}
    for row in rows:
        prompt_key = str(row.get("prompt_sha256") or row.get("prompt_id") or row.get("prompt_index"))
        if prompt_key in by_prompt:
            raise SystemExit(f"{suite_path}: duplicate prompt key {prompt_key}")
        by_prompt[prompt_key] = row

    summary = payload.get("summary") or {}
    primary_values = metric_values(rows, PRIMARY)
    return {
        "input_path": str(original),
        "suite_path": str(suite_path),
        "label": label,
        "gate_passed": bool(gate.get("passed")),
        "cached_tokens_all_zero": bool(gate.get("cached_tokens_all_zero")),
        "prompt_count": len(rows),
        "primary_median": statistics.median(primary_values) if primary_values else None,
        "primary_summary": summary.get(PRIMARY) or stat(primary_values),
        "full_summary": summary.get(FULL) or stat(metric_values(rows, FULL)),
        "wall_summary": summary.get(WALL) or stat(metric_values(rows, WALL)),
        "ttft_ms_summary": summary.get("ttft_ms"),
        "by_prompt": by_prompt,
    }


def metric_values(rows: list[dict[str, Any]], metric: str) -> list[float]:
    out = []
    for row in rows:
        value = row.get(metric)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            out.append(float(value))
    return out


def values_by_prompt(runs: list[dict[str, Any]], metric: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for run in runs:
        for key, row in run["by_prompt"].items():
            value = row.get(metric)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                out.setdefault(key, []).append(float(value))
    return out


def run_medians(runs: list[dict[str, Any]], metric: str) -> list[float]:
    out = []
    for run in runs:
        vals = metric_values(list(run["by_prompt"].values()), metric)
        if vals:
            out.append(statistics.median(vals))
    return out


def pairwise_abs_pct(values: list[float]) -> list[float]:
    out = []
    for i, left in enumerate(values):
        for right in values[i + 1 :]:
            denom = (abs(left) + abs(right)) / 2.0
            if denom:
                out.append(abs(right - left) / denom * 100.0)
    return out


def same_group_report(runs: list[dict[str, Any]]) -> dict[str, Any]:
    medians = run_medians(runs, PRIMARY)
    pairwise = pairwise_abs_pct(medians)
    by_prompt = values_by_prompt(runs, PRIMARY)
    prompt_cvs = []
    for vals in by_prompt.values():
        if len(vals) > 1:
            s = stat(vals)
            cv = s["cv_pct"]
            if isinstance(cv, (int, float)):
                prompt_cvs.append(float(cv))
    return {
        "run_count": len(runs),
        "prompt_count": len(by_prompt),
        "run_medians": medians,
        "run_median_stats": stat(medians),
        "pairwise_abs_delta_pct": {
            **stat(pairwise),
            "values": pairwise,
        },
        "per_prompt_cv_pct": stat(prompt_cvs),
        "decision_note": (
            "Single-run comparisons inside this same-recipe band are unreliable "
            "for deltas smaller than the p90 pairwise absolute run-median delta. "
            "Use paired A/B blocks and bootstrap CIs for micro-change decisions."
        ),
    }


def bootstrap_ab(
    control: dict[str, list[float]],
    candidate: dict[str, list[float]],
    *,
    iterations: int,
    seed: int,
) -> dict[str, Any]:
    keys = sorted(set(control).intersection(candidate))
    if not keys:
        raise SystemExit("control and candidate groups share no prompt keys")
    rng = random.Random(seed)
    mean_ratios = []
    median_ratios = []
    median_raw_deltas = []
    for _ in range(iterations):
        ratios = []
        raw_deltas = []
        for _ in keys:
            key = rng.choice(keys)
            left = rng.choice(control[key])
            right = rng.choice(candidate[key])
            if left:
                ratios.append((right / left - 1.0) * 100.0)
            raw_deltas.append(right - left)
        mean_ratios.append(statistics.fmean(ratios))
        median_ratios.append(statistics.median(ratios))
        median_raw_deltas.append(statistics.median(raw_deltas))

    def ci(values: list[float]) -> dict[str, float | None]:
        return {
            "p025": percentile(values, 0.025),
            "p50": percentile(values, 0.50),
            "p975": percentile(values, 0.975),
        }

    prompt_ratios = []
    for key in keys:
        c = statistics.fmean(control[key])
        t = statistics.fmean(candidate[key])
        prompt_ratios.append({
            "prompt_key": key,
            "control_mean": c,
            "candidate_mean": t,
            "ratio_pct": None if c == 0 else (t / c - 1.0) * 100.0,
            "raw_delta": t - c,
            "control_n": len(control[key]),
            "candidate_n": len(candidate[key]),
        })

    ratio_values = [r["ratio_pct"] for r in prompt_ratios if isinstance(r["ratio_pct"], float)]
    return {
        "paired_prompt_count": len(keys),
        "prompt_ratios": prompt_ratios,
        "prompt_ratio_pct_stats": stat(ratio_values),
        "bootstrap_iterations": iterations,
        "mean_ratio_pct_ci": ci(mean_ratios),
        "median_ratio_pct_ci": ci(median_ratios),
        "median_raw_delta_tok_s_ci": ci(median_raw_deltas),
    }


def ab_report(
    control_runs: list[dict[str, Any]],
    candidate_runs: list[dict[str, Any]],
    *,
    iterations: int,
    seed: int,
    min_effect_pct: float,
) -> dict[str, Any]:
    control_by_prompt = values_by_prompt(control_runs, PRIMARY)
    candidate_by_prompt = values_by_prompt(candidate_runs, PRIMARY)
    boot = bootstrap_ab(
        control_by_prompt,
        candidate_by_prompt,
        iterations=iterations,
        seed=seed,
    )
    control_medians = run_medians(control_runs, PRIMARY)
    candidate_medians = run_medians(candidate_runs, PRIMARY)
    lower = boot["median_ratio_pct_ci"]["p025"]
    median_ratio = boot["median_ratio_pct_ci"]["p50"]
    if isinstance(lower, (int, float)) and lower > min_effect_pct:
        decision = "candidate_win"
    elif isinstance(median_ratio, (int, float)) and median_ratio > 0:
        decision = "inconclusive_positive"
    else:
        decision = "no_win"
    return {
        "control": {
            "run_count": len(control_runs),
            "run_medians": control_medians,
            "run_median_stats": stat(control_medians),
        },
        "candidate": {
            "run_count": len(candidate_runs),
            "run_medians": candidate_medians,
            "run_median_stats": stat(candidate_medians),
        },
        "paired_bootstrap": boot,
        "promotion_rule": {
            "min_effect_pct": min_effect_pct,
            "decision": decision,
            "rule": (
                "Promote a micro-change only when the 95% bootstrap lower "
                "bound of the paired prompt median ratio is above min_effect_pct "
                "and all candidate runs pass the realistic final gate."
            ),
        },
    }


def markdown_summary(report: dict[str, Any]) -> str:
    lines = []
    if "same_recipe_repeatability" in report:
        same = report["same_recipe_repeatability"]
        stats = same["run_median_stats"]
        pair = same["pairwise_abs_delta_pct"]
        lines += [
            "# Realistic Suite Repeatability Analysis",
            "",
            f"- runs: {same['run_count']}",
            f"- run medians: {', '.join(f'{v:.3f}' for v in same['run_medians'])}",
            f"- run-median mean: {stats['mean']:.3f} tok/s" if isinstance(stats["mean"], float) else "- run-median mean: n/a",
            f"- run-median CV: {stats['cv_pct']:.3f}%" if isinstance(stats["cv_pct"], float) else "- run-median CV: n/a",
            f"- pairwise abs delta p90: {pair['p90']:.3f}%" if isinstance(pair["p90"], float) else "- pairwise abs delta p90: n/a",
            "",
            same["decision_note"],
        ]
    if "ab_comparison" in report:
        ab = report["ab_comparison"]
        boot = ab["paired_bootstrap"]
        rule = ab["promotion_rule"]
        ci = boot["median_ratio_pct_ci"]
        lines += [
            "# Realistic Suite Paired A/B Analysis",
            "",
            f"- control run medians: {', '.join(f'{v:.3f}' for v in ab['control']['run_medians'])}",
            f"- candidate run medians: {', '.join(f'{v:.3f}' for v in ab['candidate']['run_medians'])}",
            f"- paired prompts: {boot['paired_prompt_count']}",
            (
                "- median paired ratio 95% CI: "
                f"{ci['p025']:.3f}% / {ci['p50']:.3f}% / {ci['p975']:.3f}%"
            ),
            f"- decision: {rule['decision']}",
            "",
            rule["rule"],
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--same", action="append", default=[], help="same-recipe summary.json or realistic-suite.json")
    parser.add_argument("--control", action="append", default=[], help="control summary.json or realistic-suite.json")
    parser.add_argument("--candidate", action="append", default=[], help="candidate summary.json or realistic-suite.json")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--min-effect-pct", type=float, default=1.0)
    parser.add_argument("--allow-invalid", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    if not args.same and not (args.control and args.candidate):
        raise SystemExit("provide --same paths, or both --control and --candidate paths")

    report: dict[str, Any] = {
        "metric": PRIMARY,
        "notes": [
            "Uses per-prompt realistic-suite rows, not historical headline outliers.",
            "All non-forensic inputs should pass realistic_final_gate and cached_tokens=0.",
        ],
    }
    if args.same:
        same_runs = [load_run(Path(p), allow_invalid=args.allow_invalid) for p in args.same]
        report["same_recipe_runs"] = [
            {k: v for k, v in run.items() if k != "by_prompt"} for run in same_runs
        ]
        report["same_recipe_repeatability"] = same_group_report(same_runs)

    if args.control or args.candidate:
        if not args.control or not args.candidate:
            raise SystemExit("--control and --candidate must be used together")
        control_runs = [load_run(Path(p), allow_invalid=args.allow_invalid) for p in args.control]
        candidate_runs = [load_run(Path(p), allow_invalid=args.allow_invalid) for p in args.candidate]
        report["control_runs"] = [
            {k: v for k, v in run.items() if k != "by_prompt"} for run in control_runs
        ]
        report["candidate_runs"] = [
            {k: v for k, v in run.items() if k != "by_prompt"} for run in candidate_runs
        ]
        report["ab_comparison"] = ab_report(
            control_runs,
            candidate_runs,
            iterations=args.bootstrap,
            seed=args.seed,
            min_effect_pct=args.min_effect_pct,
        )

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown_summary(report))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
