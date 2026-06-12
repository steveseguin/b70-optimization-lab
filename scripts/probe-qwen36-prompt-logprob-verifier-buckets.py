#!/usr/bin/env python3
"""Probe prompt-logprob verifier windows for Qwen3.6 sidecar speculation.

This is a correctness-first sidecar verifier proxy. It does not use vLLM's
speculative scheduler. Instead, it teacher-forces prompt + draft tokens through
the accepted verifier model via ``/v1/completions`` with ``prompt_logprobs=1``.
For greedy decoding, a draft token is accepted when the verifier reports that
the teacher-forced token is rank 1 at its prompt position.

This is not a KV-resident verifier benchmark. Each request re-prefills the
prompt prefix, so latency is intentionally conservative. The value is that it
proves the semantic verification rule outside the scheduler path that currently
widens live attention slot mappings.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return {
            "status": resp.status,
            "json": json.loads(resp.read().decode("utf-8")),
        }


def parse_csv_ints(raw: str) -> list[int]:
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value <= 0:
            raise ValueError("window sizes must be positive")
        out.append(value)
    if not out:
        raise ValueError("no window sizes provided")
    return out


def summarize(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
        }
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


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


def top_entry(entry: dict[str, Any]) -> tuple[int | None, dict[str, Any] | None]:
    best_token: int | None = None
    best_value: dict[str, Any] | None = None
    best_rank = 10**18
    for token_text, value in entry.items():
        if not isinstance(value, dict):
            continue
        rank = value.get("rank")
        if rank is None:
            continue
        rank_int = int(rank)
        if rank_int < best_rank:
            best_rank = rank_int
            best_token = int(token_text)
            best_value = value
    return best_token, best_value


def mutate_token(token_id: int) -> int:
    # Keep mutation simple and deterministic; the tokenizer/model vocab is far
    # larger than this offset. The negative control only needs "not the same".
    return token_id + 1 if token_id < 150000 else token_id - 1


def verify_window(
    *,
    base_url: str,
    model: str,
    prompt_ids: list[int],
    prefix_output_ids: list[int],
    draft_ids: list[int],
    timeout: int,
    request_id: str,
) -> dict[str, Any]:
    verifier_prompt = prompt_ids + prefix_output_ids + draft_ids
    payload = {
        "model": model,
        "prompt": verifier_prompt,
        "max_tokens": 1,
        "temperature": 0,
        "top_p": 1.0,
        "prompt_logprobs": 1,
        "return_token_ids": True,
        "add_special_tokens": False,
        "request_id": request_id,
    }
    started = time.perf_counter()
    response = post_json(
        f"{base_url.rstrip('/')}/v1/completions",
        payload,
        timeout,
    )
    elapsed_s = time.perf_counter() - started
    choice = response["json"]["choices"][0]
    prompt_logprobs = choice.get("prompt_logprobs") or []
    offset = len(prompt_ids) + len(prefix_output_ids)
    token_results: list[dict[str, Any]] = []
    accepted_prefix = 0
    still_accepting = True
    for index, token_id in enumerate(draft_ids):
        position = offset + index
        entry = (
            prompt_logprobs[position]
            if 0 <= position < len(prompt_logprobs)
            and isinstance(prompt_logprobs[position], dict)
            else {}
        )
        token_entry = entry.get(str(token_id)) if isinstance(entry, dict) else None
        rank = (
            int(token_entry["rank"])
            if isinstance(token_entry, dict) and token_entry.get("rank") is not None
            else None
        )
        top_token_id, top_value = top_entry(entry)
        is_rank1 = rank == 1
        if still_accepting and is_rank1:
            accepted_prefix += 1
        else:
            still_accepting = False
        token_results.append(
            {
                "index": index,
                "position": position,
                "token_id": token_id,
                "rank": rank,
                "is_rank1": is_rank1,
                "logprob": (
                    float(token_entry["logprob"])
                    if isinstance(token_entry, dict)
                    and token_entry.get("logprob") is not None
                    else None
                ),
                "decoded_token": (
                    token_entry.get("decoded_token")
                    if isinstance(token_entry, dict)
                    else None
                ),
                "top_token_id": top_token_id,
                "top_rank": (
                    int(top_value["rank"])
                    if isinstance(top_value, dict)
                    and top_value.get("rank") is not None
                    else None
                ),
                "top_logprob": (
                    float(top_value["logprob"])
                    if isinstance(top_value, dict)
                    and top_value.get("logprob") is not None
                    else None
                ),
                "top_decoded_token": (
                    top_value.get("decoded_token")
                    if isinstance(top_value, dict)
                    else None
                ),
            }
        )
    return {
        "status": response["status"],
        "response_id": response["json"].get("id"),
        "elapsed_s": elapsed_s,
        "elapsed_ms": elapsed_s * 1000.0,
        "usage": response["json"].get("usage"),
        "prompt_tokens": len(verifier_prompt),
        "base_prompt_tokens": len(prompt_ids),
        "prefix_output_tokens": len(prefix_output_ids),
        "draft_tokens": len(draft_ids),
        "accepted_prefix_tokens": accepted_prefix,
        "all_rank1": accepted_prefix == len(draft_ids),
        "generated_token_ids": choice.get("token_ids") or [],
        "token_results": token_results,
    }


def build_windows(
    output_ids: list[int],
    *,
    window_size: int,
    max_windows: int,
) -> list[tuple[int, list[int]]]:
    windows: list[tuple[int, list[int]]] = []
    prefix_len = 0
    while prefix_len + window_size <= len(output_ids):
        windows.append((prefix_len, output_ids[prefix_len:prefix_len + window_size]))
        if len(windows) >= max_windows:
            break
        prefix_len += window_size
    return windows


def case_records(
    *,
    base_url: str,
    model: str,
    case: dict[str, Any],
    window_size: int,
    max_windows: int,
    timeout: int,
    include_negative_control: bool,
) -> list[dict[str, Any]]:
    prompt_ids = [int(value) for value in case["prompt_token_ids"]]
    output_ids = [int(value) for value in case["output_token_ids"]]
    rows: list[dict[str, Any]] = []
    for window_index, (prefix_len, draft_ids) in enumerate(
        build_windows(output_ids, window_size=window_size, max_windows=max_windows)
    ):
        result = verify_window(
            base_url=base_url,
            model=model,
            prompt_ids=prompt_ids,
            prefix_output_ids=output_ids[:prefix_len],
            draft_ids=draft_ids,
            timeout=timeout,
            request_id=(
                "prompt-logprob-verifier-"
                f"{case['name']}-w{window_size}-{window_index}"
            ),
        )
        result.update(
            {
                "case_name": case["name"],
                "window_size": window_size,
                "window_index": window_index,
                "prefix_output_start": prefix_len,
                "control": "perfect_draft",
            }
        )
        rows.append(result)

        if include_negative_control and window_index == 0:
            bad_draft = list(draft_ids)
            bad_draft[0] = mutate_token(bad_draft[0])
            bad = verify_window(
                base_url=base_url,
                model=model,
                prompt_ids=prompt_ids,
                prefix_output_ids=output_ids[:prefix_len],
                draft_ids=bad_draft,
                timeout=timeout,
                request_id=(
                    "prompt-logprob-verifier-negative-"
                    f"{case['name']}-w{window_size}"
                ),
            )
            bad.update(
                {
                    "case_name": case["name"],
                    "window_size": window_size,
                    "window_index": window_index,
                    "prefix_output_start": prefix_len,
                    "control": "mutated_first_token",
                    "expected_accept_prefix_tokens": 0,
                    "original_first_token_id": draft_ids[0],
                    "mutated_first_token_id": bad_draft[0],
                }
            )
            rows.append(bad)
    return rows


def summarize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in records:
        key = (row["case_name"], int(row["window_size"]), row["control"])
        groups.setdefault(key, []).append(row)

    summary = []
    for (case_name, window_size, control), rows in sorted(groups.items()):
        elapsed = [float(row["elapsed_ms"]) for row in rows]
        accepted = [int(row["accepted_prefix_tokens"]) for row in rows]
        draft_tokens = [int(row["draft_tokens"]) for row in rows]
        total_drafts = sum(draft_tokens)
        total_accepted = sum(accepted)
        mean_elapsed = statistics.fmean(elapsed) if elapsed else None
        summary.append(
            {
                "case_name": case_name,
                "window_size": window_size,
                "control": control,
                "request_count": len(rows),
                "all_rank1_count": sum(1 for row in rows if row["all_rank1"]),
                "total_draft_tokens": total_drafts,
                "total_accepted_prefix_tokens": total_accepted,
                "accepted_prefix_fraction": (
                    total_accepted / total_drafts if total_drafts else None
                ),
                "elapsed_ms": summarize(elapsed),
                "p90_elapsed_ms": percentile(elapsed, 0.90),
                "verifier_prompt_tokens": summarize(
                    [float(row["prompt_tokens"]) for row in rows]
                ),
                "sidecar_request_tok_s": (
                    (1000.0 * window_size / mean_elapsed)
                    if mean_elapsed and mean_elapsed > 0
                    else None
                ),
            }
        )
    return summary


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_markdown(path: Path, output: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 Prompt-Logprob Verifier Bucket Probe",
        "",
        "This is a sidecar verifier proxy. It uses the accepted Quark INT8 model",
        "through `/v1/completions` with token-id prompts and `prompt_logprobs=1`.",
        "It does not use vLLM speculative scheduling and does not reuse KV.",
        "",
        f"- base URL: `{output['base_url']}`",
        f"- baseline JSON: `{output['baseline_json']}`",
        f"- cases: `{len(output['case_names'])}`",
        f"- window sizes: `{output['window_sizes']}`",
        "",
        "| Case | Window | Control | Requests | All rank-1 | Accepted / draft | Mean ms | p90 ms | Sidecar request tok/s |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in output["summary"]:
        elapsed = row.get("elapsed_ms") or {}
        accepted = row.get("total_accepted_prefix_tokens")
        total = row.get("total_draft_tokens")
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['case_name']}`",
                    str(row["window_size"]),
                    f"`{row['control']}`",
                    str(row["request_count"]),
                    str(row["all_rank1_count"]),
                    f"{accepted}/{total}",
                    fmt(elapsed.get("mean"), 2),
                    fmt(row.get("p90_elapsed_ms"), 2),
                    fmt(row.get("sidecar_request_tok_s"), 2),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "- `perfect_draft` rows should be all rank-1. If not, the teacher-forced",
            "  sidecar verifier is not semantically aligned with accepted greedy decode.",
            "- `mutated_first_token` rows should accept zero prefix tokens. If not, the",
            "  rejection rule is broken.",
            "- `sidecar_request_tok_s` is conservative because every request re-prefills",
            "  the prefix. It is not the final KV-resident target speed.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="qwen36-35b-a3b-fp8")
    parser.add_argument("--baseline-json", type=Path, required=True)
    parser.add_argument("--window-sizes", default="1,2,4,8,16,32")
    parser.add_argument("--max-windows-per-case", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--no-negative-control", action="store_true")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    baseline = json.loads(args.baseline_json.read_text())
    window_sizes = parse_csv_ints(args.window_sizes)
    cases = baseline.get("cases") or []
    if not cases:
        raise SystemExit("baseline JSON has no cases")

    records: list[dict[str, Any]] = []
    for case in cases:
        if not case.get("prompt_token_ids") or not case.get("output_token_ids"):
            continue
        for window_size in window_sizes:
            records.extend(
                case_records(
                    base_url=args.base_url,
                    model=args.model,
                    case=case,
                    window_size=window_size,
                    max_windows=args.max_windows_per_case,
                    timeout=args.timeout,
                    include_negative_control=not args.no_negative_control,
                )
            )

    summary = summarize_records(records)
    perfect_rows = [row for row in records if row["control"] == "perfect_draft"]
    negative_rows = [
        row for row in records if row["control"] == "mutated_first_token"
    ]
    output = {
        "method_caveat": (
            "Teacher-forced prompt-logprob verifier proxy. Does not use vLLM "
            "speculative scheduling and does not reuse KV."
        ),
        "base_url": args.base_url.rstrip("/"),
        "model": args.model,
        "baseline_json": str(args.baseline_json),
        "window_sizes": window_sizes,
        "max_windows_per_case": args.max_windows_per_case,
        "case_names": [case.get("name") for case in cases],
        "perfect_draft_all_rank1": all(row["all_rank1"] for row in perfect_rows),
        "negative_control_all_reject_first": all(
            int(row["accepted_prefix_tokens"]) == 0 for row in negative_rows
        ),
        "summary": summary,
        "records": records,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(args.output_md, output)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "records": len(records),
                "perfect_draft_all_rank1": output["perfect_draft_all_rank1"],
                "negative_control_all_reject_first": output[
                    "negative_control_all_reject_first"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
