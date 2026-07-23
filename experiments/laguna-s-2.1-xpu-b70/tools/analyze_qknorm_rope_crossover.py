#!/usr/bin/env python3
"""Analyze the preregistered Laguna QKNorm + RoPE ABBA crossover."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path
from typing import Any


METRIC = "tok_s_1_100_after_ttft"
PROM_LINE = re.compile(
    r"^(?P<name>[^{\s]+)(?P<labels>\{[^}]*\})?\s+"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)$"
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prom_samples(path: Path) -> list[tuple[str, str, float]]:
    samples: list[tuple[str, str, float]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = PROM_LINE.match(raw_line)
        if match:
            samples.append(
                (
                    match.group("name"),
                    match.group("labels") or "",
                    float(match.group("value")),
                )
            )
    return samples


def one_sample(samples: list[tuple[str, str, float]], name: str) -> float:
    values = [value for metric, _labels, value in samples if metric == name]
    if len(values) != 1:
        raise ValueError(f"expected one {name} sample, found {len(values)}")
    return values[0]


def run_summary(label: str, directory: Path) -> dict[str, Any]:
    bench_path = directory / "bench.json"
    metrics_path = directory / "metrics-after-suite.prom"
    exactness_path = directory / "exactness-vs-q1.json"
    bench = load_json(bench_path)
    exactness = load_json(exactness_path)
    samples = prom_samples(metrics_path)

    drafts = int(one_sample(samples, "vllm:spec_decode_num_drafts_total"))
    draft_tokens = int(one_sample(samples, "vllm:spec_decode_num_draft_tokens_total"))
    accepted = int(one_sample(samples, "vllm:spec_decode_num_accepted_tokens_total"))
    decode_seconds = one_sample(samples, "vllm:request_decode_time_seconds_sum")
    accepted_by_position = [
        int(value)
        for _name, labels, value in sorted(
            (
                sample
                for sample in samples
                if sample[0] == "vllm:spec_decode_num_accepted_tokens_per_pos_total"
            ),
            key=lambda sample: int(
                re.search(r'position="(\d+)"', sample[1]).group(1)  # type: ignore[union-attr]
            ),
        )
    ]
    rows = bench["rows"]
    return {
        "label": label,
        "directory": str(directory.resolve()),
        "bench_sha256": sha256(bench_path),
        "headline_tok_s": float(bench["summary"][METRIC]["median"]),
        "mean_tok_s": float(bench["summary"][METRIC]["mean"]),
        "p10_tok_s": float(bench["summary"][METRIC]["p10"]),
        "fresh": bool(bench["fresh_response_validity"]["valid"]),
        "cached_tokens_all_zero": bool(
            bench["fresh_response_validity"]["cached_tokens_all_zero"]
        ),
        "realistic_final_gate": bool(bench["realistic_final_gate"]["passed"]),
        "teacher_exact": bool(exactness["all_exact"]),
        "teacher_exact_count": int(
            exactness["candidates"][0]["comparison"]["exact_count"]
        ),
        "long_then_next": bool(
            exactness["candidates"][0]["comparison"]["long_then_next"]["passed"]
        ),
        "rollover_count": int(
            exactness["candidates"][0]["comparison"]["rollover"]["count"]
        ),
        "rollover_exact_count": int(
            exactness["candidates"][0]["comparison"]["rollover"]["exact_count"]
        ),
        "speculation": {
            "draft_cycles": drafts,
            "draft_tokens": draft_tokens,
            "accepted_tokens": accepted,
            "accepted_by_position": accepted_by_position,
            "acceptance_rate": accepted / draft_tokens,
        },
        "request_decode_seconds": decode_seconds,
        "aggregate_cycle_ms": 1000.0 * decode_seconds / drafts,
        "completion_tokens": sum(int(row["completion_tokens"]) for row in rows),
        "row_metrics": [
            {
                "prompt_id": row["prompt_id"],
                "tok_s": float(row[METRIC]),
            }
            for row in rows
        ],
    }


def paired(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    control_rows = control["row_metrics"]
    candidate_rows = candidate["row_metrics"]
    if [row["prompt_id"] for row in control_rows] != [
        row["prompt_id"] for row in candidate_rows
    ]:
        raise ValueError("prompt identity/order differs between paired legs")

    rows = []
    for control_row, candidate_row in zip(control_rows, candidate_rows, strict=True):
        delta_pct = 100.0 * (candidate_row["tok_s"] / control_row["tok_s"] - 1.0)
        rows.append(
            {
                "prompt_id": control_row["prompt_id"],
                "control_tok_s": control_row["tok_s"],
                "candidate_tok_s": candidate_row["tok_s"],
                "delta_pct": delta_pct,
            }
        )
    control_spec = control["speculation"]
    candidate_spec = candidate["speculation"]
    return {
        "control": control["label"],
        "candidate": candidate["label"],
        "headline_delta_tok_s": (
            candidate["headline_tok_s"] - control["headline_tok_s"]
        ),
        "headline_delta_pct": 100.0
        * (candidate["headline_tok_s"] / control["headline_tok_s"] - 1.0),
        "aggregate_cycle_delta_ms": (
            candidate["aggregate_cycle_ms"] - control["aggregate_cycle_ms"]
        ),
        "aggregate_cycle_delta_pct": 100.0
        * (candidate["aggregate_cycle_ms"] / control["aggregate_cycle_ms"] - 1.0),
        "candidate_row_wins": sum(row["delta_pct"] > 0.0 for row in rows),
        "candidate_row_losses_or_ties": sum(row["delta_pct"] <= 0.0 for row in rows),
        "median_paired_delta_pct": statistics.median(row["delta_pct"] for row in rows),
        "speculation_work_identical": control_spec == candidate_spec,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a1", type=Path, required=True)
    parser.add_argument("--b1", type=Path, required=True)
    parser.add_argument("--b2", type=Path, required=True)
    parser.add_argument("--a2", type=Path, required=True)
    parser.add_argument("--all-vs-teacher", type=Path, required=True)
    parser.add_argument("--cross-leg", type=Path, required=True)
    parser.add_argument("--record-floor", type=float, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()

    runs = {
        "A1": run_summary("A1-control", args.a1),
        "B1": run_summary("B1-candidate", args.b1),
        "B2": run_summary("B2-candidate", args.b2),
        "A2": run_summary("A2-control", args.a2),
    }
    pairs = {
        "B1_vs_A1": paired(runs["A1"], runs["B1"]),
        "B2_vs_A2": paired(runs["A2"], runs["B2"]),
    }
    all_vs_teacher = load_json(args.all_vs_teacher)
    cross_leg = load_json(args.cross_leg)

    speculation_vectors = [
        json.dumps(run["speculation"], sort_keys=True) for run in runs.values()
    ]
    quality_pass = all(
        run["fresh"]
        and run["cached_tokens_all_zero"]
        and run["realistic_final_gate"]
        and run["teacher_exact"]
        and run["teacher_exact_count"] == 13
        and run["long_then_next"]
        and run["rollover_count"] == 1
        and run["rollover_exact_count"] == 1
        for run in runs.values()
    ) and bool(all_vs_teacher["all_exact"] and cross_leg["all_exact"])
    all_speculation_work_identical = len(set(speculation_vectors)) == 1
    paired_direction_pass = all(
        pair["headline_delta_tok_s"] > 0.0 for pair in pairs.values()
    )
    paired_rows_pass = all(
        pair["candidate_row_wins"] >= 9 and pair["median_paired_delta_pct"] > 0.0
        for pair in pairs.values()
    )
    paired_cycles_pass = all(
        pair["aggregate_cycle_delta_ms"] < 0.0 for pair in pairs.values()
    )
    matched_pair_work_pass = all(
        pair["speculation_work_identical"] for pair in pairs.values()
    )
    candidate_lower = min(runs["B1"]["headline_tok_s"], runs["B2"]["headline_tok_s"])
    control_lower = min(runs["A1"]["headline_tok_s"], runs["A2"]["headline_tok_s"])
    lower_beats_control = candidate_lower > control_lower
    lower_beats_record = candidate_lower > args.record_floor

    gates = {
        "quality_and_honesty": quality_pass,
        "all_four_speculation_work_identical": all_speculation_work_identical,
        "matched_pair_speculation_work_identical": matched_pair_work_pass,
        "candidate_headline_wins_both_pairs": paired_direction_pass,
        "candidate_wins_at_least_9_of_13_rows_and_positive_median_both_pairs": (
            paired_rows_pass
        ),
        "candidate_aggregate_cycle_lower_both_pairs": paired_cycles_pass,
        "candidate_lower_start_beats_control_lower_start": lower_beats_control,
        "candidate_lower_start_beats_existing_record": lower_beats_record,
    }
    strict_preregistered_record_pass = all(gates.values())
    paired_causal_evidence = (
        quality_pass
        and matched_pair_work_pass
        and paired_direction_pass
        and paired_rows_pass
        and paired_cycles_pass
    )
    result = {
        "experiment": "laguna-m8-qknorm-rope-abba",
        "order": ["A1-control", "B1-candidate", "B2-candidate", "A2-control"],
        "record_floor_tok_s": args.record_floor,
        "runs": runs,
        "pairs": pairs,
        "candidate_lower_start_tok_s": candidate_lower,
        "control_lower_start_tok_s": control_lower,
        "candidate_lower_delta_from_record_tok_s": (
            candidate_lower - args.record_floor
        ),
        "candidate_lower_delta_from_record_pct": 100.0
        * (candidate_lower / args.record_floor - 1.0),
        "gates": gates,
        "strict_preregistered_record_pass": strict_preregistered_record_pass,
        "paired_causal_evidence": paired_causal_evidence,
        "disposition": (
            "record_candidate"
            if strict_preregistered_record_pass
            else (
                "exact_reproducible_component_stack_candidate_not_record"
                if paired_causal_evidence
                else "negative_or_inconclusive"
            )
        ),
        "combined_exactness": {
            "all_vs_teacher": str(args.all_vs_teacher.resolve()),
            "all_vs_teacher_pass": bool(all_vs_teacher["all_exact"]),
            "cross_leg": str(args.cross_leg.resolve()),
            "cross_leg_pass": bool(cross_leg["all_exact"]),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    markdown = [
        "# Laguna QKNorm + RoPE ABBA result",
        "",
        "| Leg | Treatment | Headline tok/s | Cycle ms | Drafts | Accepted |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for key in ("A1", "B1", "B2", "A2"):
        run = runs[key]
        markdown.append(
            f"| {key} | {run['label']} | {run['headline_tok_s']:.6f} | "
            f"{run['aggregate_cycle_ms']:.6f} | "
            f"{run['speculation']['draft_cycles']} | "
            f"{run['speculation']['accepted_tokens']} |"
        )
    markdown.extend(
        [
            "",
            "| Pair | Headline delta | Cycle delta | Row wins | "
            "Median paired delta | Same speculation work |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, pair in pairs.items():
        markdown.append(
            f"| {name} | {pair['headline_delta_pct']:+.4f}% | "
            f"{pair['aggregate_cycle_delta_pct']:+.4f}% | "
            f"{pair['candidate_row_wins']}/13 | "
            f"{pair['median_paired_delta_pct']:+.4f}% | "
            f"{pair['speculation_work_identical']} |"
        )
    markdown.extend(
        [
            "",
            f"- All runs exact/fresh/cache-zero: `{quality_pass}`",
            f"- All-four speculation-work gate: `{all_speculation_work_identical}`",
            f"- Matched-pair causal evidence: `{paired_causal_evidence}`",
            f"- Candidate lower start: `{candidate_lower:.9f} tok/s`",
            f"- Existing record: `{args.record_floor:.9f} tok/s`",
            f"- Strict preregistered record pass: `{strict_preregistered_record_pass}`",
            f"- Disposition: `{result['disposition']}`",
            "",
        ]
    )
    args.markdown_out.write_text("\n".join(markdown), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
