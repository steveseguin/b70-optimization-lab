#!/usr/bin/env python3
"""Probe rolling one-token verifier parity for Qwen3.6.

This checks whether the accepted backend can reproduce an accepted completion
token-by-token when each output prefix is provided as part of the prompt and
the model is asked to generate exactly one next token.

The probe is intentionally slow because it re-prefills every prefix. It is not
a speed benchmark. It answers a narrower correctness question that matters for
sidecar speculation:

    Can a verifier with the same model state at prefix N select the accepted
    token at N+1?

If this fails, a re-prefill sidecar is not semantically aligned with accepted
incremental decode. If this passes while multi-token prompt-logprob verifier
windows fail, the next optimization target is a KV-resident rolling verifier
that avoids the re-prefill cost.
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


def extract_generated_token(choice: dict[str, Any]) -> int | None:
    token_ids = choice.get("token_ids")
    if isinstance(token_ids, list) and token_ids:
        return int(token_ids[0])
    # Some response shapes may nest generated token ids under logprobs.
    logprobs = choice.get("logprobs")
    if isinstance(logprobs, dict):
        nested = logprobs.get("token_ids")
        if isinstance(nested, list) and nested:
            return int(nested[0])
    return None


def probe_one_prefix(
    *,
    base_url: str,
    model: str,
    prompt_ids: list[int],
    expected_token_id: int,
    seed: int | None,
    timeout: int,
    request_id: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt_ids,
        "max_tokens": 1,
        "temperature": 0,
        "top_p": 1.0,
        "return_token_ids": True,
        "add_special_tokens": False,
        "request_id": request_id,
    }
    if seed is not None:
        payload["seed"] = seed
    started = time.perf_counter()
    response = post_json(
        f"{base_url.rstrip('/')}/v1/completions",
        payload,
        timeout,
    )
    elapsed_s = time.perf_counter() - started
    choice = response["json"]["choices"][0]
    generated_token_id = extract_generated_token(choice)
    return {
        "status": response["status"],
        "response_id": response["json"].get("id"),
        "elapsed_s": elapsed_s,
        "elapsed_ms": elapsed_s * 1000.0,
        "prompt_tokens": len(prompt_ids),
        "expected_token_id": expected_token_id,
        "generated_token_id": generated_token_id,
        "match": generated_token_id == expected_token_id,
        "finish_reason": choice.get("finish_reason"),
        "text": choice.get("text"),
        "usage": response["json"].get("usage"),
    }


def write_markdown(
    *,
    output_md: Path,
    data: dict[str, Any],
) -> None:
    lines: list[str] = []
    lines.append("# Qwen3.6 Rolling One-Token Verifier Probe")
    lines.append("")
    lines.append(
        "This re-prefills each accepted output prefix and asks the accepted "
        "backend to generate one next token."
    )
    lines.append("")
    lines.append(f"- base URL: `{data['base_url']}`")
    lines.append(f"- baseline JSON: `{data['baseline_json']}`")
    lines.append(f"- seed: `{data['seed']}`")
    lines.append(f"- max tokens per case: `{data['max_tokens_per_case']}`")
    lines.append(f"- all matched: `{data['all_matched']}`")
    lines.append("")
    lines.append(
        "| Case | Checked | Matched | First mismatch | Mean ms | p90 ms | "
        "Rolling request tok/s |"
    )
    lines.append("| --- | ---: | ---: | --- | ---: | ---: | ---: |")
    for row in data["summary"]:
        first = row.get("first_mismatch")
        if first is None:
            first_text = "none"
        else:
            first_text = (
                f"pos {first['position']} expected "
                f"`{first['expected_token_id']}` got "
                f"`{first['generated_token_id']}`"
            )
        lines.append(
            f"| `{row['case_name']}` | {row['checked_tokens']} | "
            f"{row['matched_tokens']} | {first_text} | "
            f"{row['elapsed_ms']['mean']:.2f} | "
            f"{row['p90_elapsed_ms']:.2f} | "
            f"{row['rolling_request_tok_s']:.2f} |"
        )
    lines.append("")
    lines.append("Interpretation:")
    lines.append("")
    lines.append(
        "- If this fails, full-prefix re-prefill verification is not aligned "
        "with accepted incremental decode."
    )
    lines.append(
        "- If this passes while prompt-logprob multi-token windows fail, the "
        "right next target is a rolling verifier with resident KV, not "
        "teacher-forced multi-token prefill."
    )
    lines.append(
        "- `rolling_request_tok_s` includes full re-prefill cost and is not a "
        "production target."
    )
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default=None)
    parser.add_argument("--baseline-json", required=True)
    parser.add_argument("--max-tokens-per-case", type=int, default=128)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--stop-on-first-mismatch", action="store_true")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    baseline_path = Path(args.baseline_json)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    model = args.model or baseline.get("model") or "qwen36-35b-a3b-fp8"
    seed = args.seed
    if seed is None and baseline.get("seed") is not None:
        seed = int(baseline["seed"])
    max_tokens = max(1, args.max_tokens_per_case)

    records: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    all_matched = True

    for case in baseline["cases"]:
        case_name = str(case.get("name") or f"case_{len(summary)}")
        prompt_ids = [int(value) for value in case["prompt_token_ids"]]
        output_ids = [int(value) for value in case["output_token_ids"]]
        limit = min(max_tokens, len(output_ids))
        case_records: list[dict[str, Any]] = []
        for position in range(limit):
            expected = int(output_ids[position])
            result = probe_one_prefix(
                base_url=args.base_url,
                model=model,
                prompt_ids=prompt_ids + output_ids[:position],
                expected_token_id=expected,
                seed=seed,
                timeout=args.timeout,
                request_id=(
                    f"qwen36-rollver-{case_name}-pos{position}"
                    .replace("_", "-")
                    .replace(" ", "-")
                ),
            )
            result.update(
                {
                    "case_name": case_name,
                    "position": position,
                    "prefix_output_tokens": position,
                }
            )
            case_records.append(result)
            records.append(result)
            if not result["match"]:
                all_matched = False
                if args.stop_on_first_mismatch:
                    break

        elapsed_ms = [float(row["elapsed_ms"]) for row in case_records]
        checked = len(case_records)
        matched = sum(1 for row in case_records if row["match"])
        first_mismatch = next(
            (row for row in case_records if not row["match"]),
            None,
        )
        summary.append(
            {
                "case_name": case_name,
                "checked_tokens": checked,
                "matched_tokens": matched,
                "all_matched": checked == matched,
                "first_mismatch": (
                    {
                        "position": first_mismatch["position"],
                        "expected_token_id": first_mismatch["expected_token_id"],
                        "generated_token_id": first_mismatch["generated_token_id"],
                        "text": first_mismatch.get("text"),
                    }
                    if first_mismatch
                    else None
                ),
                "elapsed_ms": summarize(elapsed_ms),
                "p90_elapsed_ms": percentile(elapsed_ms, 0.90),
                "rolling_request_tok_s": (
                    checked / sum(row["elapsed_s"] for row in case_records)
                    if case_records
                    else None
                ),
            }
        )

    output = {
        "base_url": args.base_url,
        "baseline_json": str(baseline_path),
        "model": model,
        "seed": seed,
        "max_tokens_per_case": max_tokens,
        "stop_on_first_mismatch": args.stop_on_first_mismatch,
        "all_matched": all_matched,
        "summary": summary,
        "records": records,
    }
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(output_md=output_md, data=output)
    print(
        json.dumps(
            {
                "all_matched": all_matched,
                "output_json": str(output_json),
                "output_md": str(output_md),
                "records": len(records),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
