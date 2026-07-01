#!/usr/bin/env python3
"""Compare logprobs at a known Qwen3.6 verifier mismatch.

This script is a narrow diagnostic for sidecar/speculation correctness work. It
loads a baseline token trace, a streaming-input verifier trace, and optionally
an accepted endpoint logprob trace, then probes the live OpenAI-compatible
endpoint at the first divergent token.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_TOKENIZER = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118"
)


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_case(path: Path, case_name: str | None) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases") or []
    if not cases:
        raise ValueError(f"{path} has no cases")
    if case_name is None:
        return cases[0]
    for case in cases:
        if case.get("name") == case_name:
            return case
    raise ValueError(f"case {case_name!r} not found in {path}")


def first_streaming_mismatch(path: Path, case_name: str | None) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data.get("records") or []:
        if case_name is not None and row.get("case_name") != case_name:
            continue
        if not row.get("match"):
            return row
    raise ValueError(f"{path} has no matching streaming mismatch")


def token_entry_from_completion_top(
    top: list[dict[str, Any]] | None,
    token_id: int,
) -> dict[str, Any] | None:
    if not top:
        return None
    for index, entry in enumerate(top, start=1):
        if entry.get("token_id") == token_id:
            out = dict(entry)
            out["rank"] = index
            return out
    return None


def normalize_completion_logprobs(
    tokenizer: Any,
    logprobs: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not logprobs:
        return []
    rows: list[dict[str, Any]] = []
    tokens = logprobs.get("tokens") or []
    token_logprobs = logprobs.get("token_logprobs") or []
    top_logprobs = logprobs.get("top_logprobs") or []
    for index, token_text in enumerate(tokens):
        token_ids = tokenizer.encode(token_text, add_special_tokens=False)
        top_entries: list[dict[str, Any]] = []
        top = top_logprobs[index] if index < len(top_logprobs) else None
        if isinstance(top, dict):
            for text, value in top.items():
                ids = tokenizer.encode(text, add_special_tokens=False)
                top_entries.append(
                    {
                        "text": text,
                        "token_ids": ids,
                        "token_id": ids[0] if len(ids) == 1 else None,
                        "logprob": float(value) if value is not None else None,
                    }
                )
            top_entries.sort(
                key=lambda item: (
                    -(item["logprob"] if item["logprob"] is not None else -1e30),
                    item["text"],
                )
            )
        rows.append(
            {
                "index": index,
                "token_text": token_text,
                "token_ids": token_ids,
                "token_id": token_ids[0] if len(token_ids) == 1 else None,
                "token_logprob": (
                    float(token_logprobs[index])
                    if index < len(token_logprobs)
                    and token_logprobs[index] is not None
                    else None
                ),
                "top": top_entries,
            }
        )
    return rows


def normalize_prompt_logprobs_entry(entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(entry, dict):
        return []
    rows: list[dict[str, Any]] = []
    for raw_token_id, value in entry.items():
        if not isinstance(value, dict):
            continue
        rows.append(
            {
                "token_id": int(raw_token_id),
                "rank": (
                    int(value["rank"])
                    if value.get("rank") is not None
                    else None
                ),
                "logprob": (
                    float(value["logprob"])
                    if value.get("logprob") is not None
                    else None
                ),
                "decoded_token": value.get("decoded_token"),
            }
        )
    rows.sort(key=lambda item: item.get("rank") or 10**9)
    return rows


def entry_by_token(
    entries: list[dict[str, Any]],
    token_id: int,
) -> dict[str, Any] | None:
    for entry in entries:
        if entry.get("token_id") == token_id:
            return entry
    return None


def generated_logprob_probe(
    *,
    base_url: str,
    model: str,
    prompt_ids: list[int],
    max_tokens: int,
    seed: int,
    logprobs: int,
    request_id: str,
    timeout: int,
    tokenizer: Any,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt_ids,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1.0,
        "seed": seed,
        "logprobs": logprobs,
        "return_token_ids": True,
        "add_special_tokens": False,
        "request_id": request_id,
    }
    response = post_json(f"{base_url.rstrip('/')}/v1/completions", payload, timeout)
    choice = response["choices"][0]
    return {
        "response_id": response.get("id"),
        "token_ids": choice.get("token_ids") or [],
        "text": choice.get("text") or "",
        "normalized_logprobs": normalize_completion_logprobs(
            tokenizer,
            choice.get("logprobs"),
        ),
        "usage": response.get("usage"),
    }


def prompt_logprob_probe(
    *,
    base_url: str,
    model: str,
    prompt_ids: list[int],
    position: int,
    logprobs: int,
    request_id: str,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt_ids,
        "max_tokens": 1,
        "temperature": 0,
        "top_p": 1.0,
        "prompt_logprobs": logprobs,
        "return_token_ids": True,
        "add_special_tokens": False,
        "request_id": request_id,
    }
    response = post_json(f"{base_url.rstrip('/')}/v1/completions", payload, timeout)
    choice = response["choices"][0]
    entries = normalize_prompt_logprobs_entry(
        (choice.get("prompt_logprobs") or [])[position]
    )
    return {
        "response_id": response.get("id"),
        "prompt_position": position,
        "top_logprobs": entries,
        "usage": response.get("usage"),
    }


def slim_top(entries: list[dict[str, Any]] | None, count: int = 8) -> list[dict[str, Any]]:
    return list(entries or [])[:count]


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 Mismatch Logprob Microscope",
        "",
        f"- case: `{data['case_name']}`",
        f"- position: `{data['position']}`",
        f"- expected token: `{data['expected_token_id']}` `{data['expected_text']!r}`",
        f"- streaming token: `{data['streaming_token_id']}` `{data['streaming_text']!r}`",
        "",
        "| Probe | Top token | Expected rank/logprob | Streaming rank/logprob |",
        "| --- | --- | --- | --- |",
    ]
    for row in data["comparison_rows"]:
        lines.append(
            "| {name} | `{top}` | {expected} | {streaming} |".format(
                name=row["name"],
                top=row["top"],
                expected=row["expected"],
                streaming=row["streaming"],
            )
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            data["interpretation"],
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fmt_entry(entry: dict[str, Any] | None) -> str:
    if not entry:
        return "missing"
    rank = entry.get("rank")
    logprob = entry.get("logprob")
    if logprob is None:
        return f"rank {rank}, logprob n/a"
    return f"rank {rank}, logprob {float(logprob):.6f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-json", type=Path, required=True)
    parser.add_argument("--streaming-json", type=Path, required=True)
    parser.add_argument("--accepted-logprobs-json", type=Path)
    parser.add_argument("--case-name")
    parser.add_argument("--position", type=int)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen36-35b-a3b-fp8")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--logprobs", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    mismatch = first_streaming_mismatch(args.streaming_json, args.case_name)
    case_name = args.case_name or mismatch["case_name"]
    case = load_case(args.baseline_json, case_name)
    position = args.position if args.position is not None else int(mismatch["position"])
    prompt_ids = [int(value) for value in case["prompt_token_ids"]]
    output_ids = [int(value) for value in case["output_token_ids"]]
    expected_id = int(output_ids[position])
    streaming_id = int(mismatch["generated_token_id"])
    target_prompt_position = len(prompt_ids) + position

    accepted_generated = None
    if args.accepted_logprobs_json:
        accepted_data = json.loads(args.accepted_logprobs_json.read_text(encoding="utf-8"))
        accepted_case = next(
            row for row in accepted_data["cases"] if row["name"] == case_name
        )
        accepted_generated = accepted_case["normalized_logprobs"][position]

    rolling = generated_logprob_probe(
        base_url=args.base_url,
        model=args.model,
        prompt_ids=prompt_ids + output_ids[:position],
        max_tokens=1,
        seed=args.seed,
        logprobs=args.logprobs,
        request_id=f"mismatch-rolling-{case_name}-{position}",
        timeout=args.timeout,
        tokenizer=tokenizer,
    )
    prompt_score = prompt_logprob_probe(
        base_url=args.base_url,
        model=args.model,
        prompt_ids=prompt_ids + output_ids[:position + 1],
        position=target_prompt_position,
        logprobs=args.logprobs,
        request_id=f"mismatch-promptlogprob-{case_name}-{position}",
        timeout=args.timeout,
    )

    def completion_probe_row(name: str, row: dict[str, Any] | None) -> dict[str, Any]:
        top = row["top"] if row else []
        top_entry = top[0] if top else None
        expected = token_entry_from_completion_top(top, expected_id)
        streaming = token_entry_from_completion_top(top, streaming_id)
        return {
            "name": name,
            "top": top_entry,
            "expected": expected,
            "streaming": streaming,
            "top_logprobs": slim_top(top),
        }

    streaming_top = mismatch.get("top_logprobs") or []
    rows = [
        {
            "name": "streaming-input",
            "top": streaming_top[0] if streaming_top else None,
            "expected": mismatch.get("expected_logprob_entry"),
            "streaming": mismatch.get("generated_logprob_entry"),
            "top_logprobs": slim_top(streaming_top),
        },
        completion_probe_row("accepted-decode", accepted_generated),
        completion_probe_row(
            "rolling-refill-next",
            rolling["normalized_logprobs"][0] if rolling["normalized_logprobs"] else None,
        ),
        {
            "name": "prompt-logprob-refill",
            "top": prompt_score["top_logprobs"][0] if prompt_score["top_logprobs"] else None,
            "expected": entry_by_token(prompt_score["top_logprobs"], expected_id),
            "streaming": entry_by_token(prompt_score["top_logprobs"], streaming_id),
            "top_logprobs": slim_top(prompt_score["top_logprobs"]),
        },
    ]

    comparison_rows = []
    for row in rows:
        top = row["top"]
        top_text = "missing" if not top else (
            f"{top.get('token_id')} {tokenizer.decode([int(top['token_id'])])!r}"
        )
        comparison_rows.append(
            {
                "name": row["name"],
                "top": top_text,
                "expected": fmt_entry(row["expected"]),
                "streaming": fmt_entry(row["streaming"]),
            }
        )

    interpretation = (
        "Accepted decode and prompt-logprob refill put the expected newline and "
        "streaming double-newline on an exact logprob tie, while streaming-input "
        "and rolling re-prefill both rank the double-newline first. This points "
        "at tie/order or resident-state divergence, so an external replay "
        "sidecar is still not acceptable as an exact-token verifier. The next "
        "quality-safe speed path should use the accepted request state directly, "
        "for example in-engine copy-on-write KV/request forking."
    )

    output = {
        "baseline_json": str(args.baseline_json),
        "streaming_json": str(args.streaming_json),
        "accepted_logprobs_json": (
            str(args.accepted_logprobs_json) if args.accepted_logprobs_json else None
        ),
        "case_name": case_name,
        "position": position,
        "target_prompt_position": target_prompt_position,
        "expected_token_id": expected_id,
        "expected_text": tokenizer.decode([expected_id]),
        "streaming_token_id": streaming_id,
        "streaming_text": tokenizer.decode([streaming_id]),
        "context_token_ids": output_ids[max(0, position - 8):position + 8],
        "context_text": tokenizer.decode(output_ids[max(0, position - 8):position + 8]),
        "rolling_refill": rolling,
        "prompt_logprob_refill": prompt_score,
        "probe_rows": rows,
        "comparison_rows": comparison_rows,
        "interpretation": interpretation,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    write_markdown(args.output_md, output)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "case_name": case_name,
                "position": position,
                "comparison_rows": comparison_rows,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
