#!/usr/bin/env python3
"""Analyze fixed MiniCPM baseline rows; never infer semantic quality from style."""

import argparse
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent


def exact_json(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            exact_json(actual[k], v) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            exact_json(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_rows(path):
    value = json.loads(path.read_text())
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a JSON array")
    for row in value:
        for key in ["id", "suite", "input_ids", "output_ids"]:
            if key not in row:
                raise ValueError(f"{path}: row missing {key}")
        for field in ["input_ids", "output_ids"]:
            if not isinstance(row[field], list) or not all(
                type(x) is int for x in row[field]
            ):
                raise ValueError(f"{path}: {row['id']} invalid {field}")
    return value


def primary(rows):
    result = {}
    for row in rows:
        if row["suite"] not in ["quality", "realistic", "context", "realistic_quality"]:
            continue
        key = (row["suite"], row["id"])
        if key in result:
            raise ValueError(f"duplicate primary row {key}")
        result[key] = row
    return result


def quality(rows, specs):
    out = []
    for spec in specs:
        row = rows.get(("quality", spec["id"]))
        result = {"id": spec["id"], "passed": False}
        if row is None:
            result["reason"] = "missing"
        elif row.get("eos") is not True:
            result["reason"] = "not a natural completed answer"
        elif not isinstance(row.get("final_text"), str):
            result["reason"] = "missing final_text"
        else:
            checks = spec["checks"]
            answer = row["final_text"].strip()
            try:
                if "json_equal" in checks:
                    parsed = json.loads(
                        answer,
                        object_pairs_hook=unique_object,
                        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
                    )
                    result["passed"] = exact_json(parsed, checks["json_equal"])
                else:
                    result["passed"] = answer == checks["exact_text_after_strip"]
                if not result["passed"]:
                    result["reason"] = "content or JSON type mismatch"
            except (ValueError, TypeError) as exc:
                result["reason"] = f"invalid JSON: {exc}"
        out.append(result)
    return out


def compare(first, second):
    out = []
    for key in sorted(first.keys() | second.keys()):
        a, b = first.get(key), second.get(key)
        item = {"suite": key[0], "id": key[1], "passed": False}
        if a is None or b is None:
            item["reason"] = "missing primary row in one process"
        else:
            item["input_ids_exact"] = a["input_ids"] == b["input_ids"]
            item["output_ids_exact"] = a["output_ids"] == b["output_ids"]
            item["generation_contract_exact"] = all(
                a.get(k) == b.get(k) for k in ["eos", "max_new_tokens"]
            )
            item["passed"] = all(
                item[k]
                for k in [
                    "input_ids_exact",
                    "output_ids_exact",
                    "generation_contract_exact",
                ]
            )
        out.append(item)
    return out


def repeated(rows, prim):
    out = []
    for key, base in sorted(prim.items()):
        if key[0] == "realistic_quality":
            continue  # Extended quality streams are checked across fresh processes.
        matches = [
            r for r in rows if r["suite"] == "repeat" and r.get("repeat_of") == key[1]
        ]
        out.append(
            {
                "id": key[1],
                "suite": key[0],
                "repeat_count": len(matches),
                "passed": len(matches) > 0
                and all(
                    r["input_ids"] == base["input_ids"]
                    and r["output_ids"] == base["output_ids"]
                    and r.get("eos") == base.get("eos")
                    and r.get("max_new_tokens") == base.get("max_new_tokens")
                    for r in matches
                ),
            }
        )
    return out


def oracles(rows, prim, quality_specs):
    out = []
    for spec in quality_specs:
        base = prim.get(("quality", spec["id"]))
        matches = [
            r
            for r in rows
            if r["suite"] == "oracle" and r.get("oracle_of") == spec["id"]
        ]
        passed = bool(base) and bool(matches)
        for row in matches:
            passed = (
                passed
                and row["input_ids"] == base["input_ids"]
                and len(row["output_ids"]) >= 8
                and row["output_ids"][:8] == base["output_ids"][:8]
            )
        out.append(
            {
                "id": spec["id"],
                "rows": len(matches),
                "first_eight_tokens_exact": bool(passed),
                "logit_parity": "not inferred from token IDs; inspect recorded logit diagnostics separately",
            }
        )
    return out


def timing(prim, specs):
    rows, groups = [], {}
    for spec in specs:
        row = prim.get(("realistic", spec["id"]))
        item = {"id": spec["id"], "class": spec["class"], "primary_valid": False}
        if row is None:
            item["reason"] = "missing"
        else:
            ts = row.get("token_timestamps_seconds", [])
            valid = (
                isinstance(ts, list)
                and len(ts) == len(row["output_ids"])
                and all(
                    type(t) in [float, int] and math.isfinite(t) and t >= 0 for t in ts
                )
                and all(b > a for a, b in zip(ts, ts[1:]))
            )
            duration = row.get("generation_seconds")
            item["generated_tokens"] = len(row["output_ids"])
            item["natural_completion"] = row.get("eos") is True
            item["fresh_prompt"] = (
                type(row.get("cached_tokens")) is int and row["cached_tokens"] == 0
            )
            item["full512_cap"] = row.get("max_new_tokens") == 512
            if valid and ts:
                item["ttft_seconds"] = ts[0]
                if (
                    type(duration) in [float, int]
                    and math.isfinite(duration)
                    and duration >= ts[-1]
                    and duration > 0
                ):
                    item["wall_tok_s"] = len(ts) / duration
                    if item["natural_completion"]:
                        item["natural_completion_wall_tok_s"] = len(ts) / duration
                if len(ts) > 1:
                    item["full_after_ttft_tok_s"] = (len(ts) - 1) / (ts[-1] - ts[0])
            if (
                valid
                and len(ts) >= 100
                and item["fresh_prompt"]
                and item["full512_cap"]
            ):
                item["primary_valid"] = True
                item["tok_s_1_100"] = 99 / (ts[99] - ts[0])
                groups.setdefault(spec["class"], []).append(item["tok_s_1_100"])
            else:
                item["reason"] = (
                    "missing/invalid per-token timestamps, fewer than100 tokens, cache reuse, or wrong cap"
                )
        rows.append(item)
    complete = len(rows) == len(specs) and all(r["primary_valid"] for r in rows)
    result = {
        "rows": rows,
        "full_suite_primary_available": complete,
        "metric": "99/(t100-t1), native thinking-inclusive generated-token rate",
    }
    if complete:
        rates = [r["tok_s_1_100"] for r in rows]
        medians = {c: statistics.median(v) for c, v in groups.items()}
        ordered = sorted(rates)
        rank = (len(ordered) - 1) * 0.1
        low = math.floor(rank)
        result.update(
            class_medians=medians,
            primary_tok_s=statistics.median(medians.values()),
            all_prompt_median=statistics.median(rates),
            mean=statistics.mean(rates),
            p10=ordered[low]
            + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (rank - low),
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    a, b = read_rows(args.first), read_rows(args.second)
    pa, pb = primary(a), primary(b)
    qspec = json.loads((ROOT / "quality-canaries-v1.json").read_text())["prompts"]
    rspec = json.loads((ROOT / "realistic-suite-v1.json").read_text())["prompts"]
    qa, qb, fresh = quality(pa, qspec), quality(pb, qspec), compare(pa, pb)
    repeats = repeated(a, pa)
    oracle = oracles(a, pa, qspec)
    required = {("quality", p["id"]) for p in qspec} | {
        ("realistic", p["id"]) for p in rspec
    }
    coverage = required <= pa.keys() and required <= pb.keys()
    summary = {
        "schema": "minicpm5-native-baseline-analysis-v1",
        "first": str(args.first),
        "second": str(args.second),
        "required_coverage_passed": coverage,
        "quality_first": qa,
        "quality_second": qb,
        "fresh_process_exact": fresh,
        "same_process_repeats": repeats,
        "cache_no_cache": oracle,
        "timing_first": timing(pa, rspec),
        "timing_second_support_only": timing(pb, rspec),
        "manual_realistic_rubric": {"status": "pending", "passed": None},
        "baseline_qualified": False,
        "qualification_note": "Manual semantic rubric and runtime/model identity review remain mandatory; exact repeats do not prove correctness or universal losslessness.",
    }
    summary["automated_gates_passed"] = bool(
        coverage
        and all(x["passed"] for x in qa + qb + fresh + repeats)
        and all(x["first_eight_tokens_exact"] for x in oracle)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "automated_gates_passed",
                    "baseline_qualified",
                    "manual_realistic_rubric",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
