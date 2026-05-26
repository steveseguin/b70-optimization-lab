#!/usr/bin/env python3
"""Small OpenAI-endpoint benchmark for the production c1 MiniMax service."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SCENARIOS = {
    "short_decode": {
        "prompt_lines": 12,
        "max_tokens": 512,
        "description": "short prompt, decode-heavy",
    },
    "prefill_16k": {
        "prompt_lines": 540,
        "max_tokens": 16,
        "description": "mid-context prompt, small output",
    },
    "near32k": {
        "prompt_lines": 1040,
        "max_tokens": 64,
        "description": "near-32K prompt with answer headroom",
    },
}


def fetch_model(base_url: str, timeout: int) -> tuple[str, int | None]:
    with urllib.request.urlopen(f"{base_url}/v1/models", timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    model = payload["data"][0]
    return model["id"], model.get("max_model_len")


def build_prompt(label: str, lines: int) -> str:
    body = "\n".join(
        f"Context row {i:04d} for production benchmark {label}: preserve exact "
        f"position, cache order, token accounting, and marker {label}-{i:04d}."
        for i in range(lines)
    )
    return (
        f"{body}\n\n"
        "Task: continue with the word benchmark separated by spaces. "
        "Keep going until the server stops generation.\n\n"
        "Answer: benchmark benchmark benchmark"
    )


def stream_completion(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    seed: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1.0,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "ignore_eos": True,
    }
    req = urllib.request.Request(
        f"{base_url}/v1/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    first_text_at: float | None = None
    usage: dict[str, Any] | None = None
    text_parts: list[str] = []
    chunks = 0

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices", []):
                    delta = choice.get("text") or ""
                    if delta:
                        chunks += 1
                        text_parts.append(delta)
                        if first_text_at is None:
                            first_text_at = time.perf_counter()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc

    ended = time.perf_counter()
    text = "".join(text_parts)
    usage = usage or {}
    completion_tokens = usage.get("completion_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    total_tokens = usage.get("total_tokens")
    elapsed_s = ended - started
    ttft_s = None if first_text_at is None else first_text_at - started
    post_ttft_s = None if first_text_at is None else ended - first_text_at

    tok_s_out_wall = None
    tok_s_out_after_ttft = None
    tok_s_total_wall = None
    tok_s_prefill_approx = None
    if isinstance(completion_tokens, int) and completion_tokens > 0:
        tok_s_out_wall = completion_tokens / elapsed_s
        if post_ttft_s and post_ttft_s > 0:
            tok_s_out_after_ttft = completion_tokens / post_ttft_s
    if isinstance(total_tokens, int) and total_tokens > 0:
        tok_s_total_wall = total_tokens / elapsed_s
    if isinstance(prompt_tokens, int) and ttft_s and ttft_s > 0:
        tok_s_prefill_approx = prompt_tokens / ttft_s

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "elapsed_s": elapsed_s,
        "ttft_s": ttft_s,
        "post_ttft_s": post_ttft_s,
        "tok_s_out_wall": tok_s_out_wall,
        "tok_s_out_after_ttft": tok_s_out_after_ttft,
        "tok_s_total_wall": tok_s_total_wall,
        "tok_s_prefill_approx": tok_s_prefill_approx,
        "stream_text_chunks": chunks,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_preview": text[:160],
    }


def round_float(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    return value


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in (
        "tok_s_out_wall",
        "tok_s_out_after_ttft",
        "tok_s_total_wall",
        "tok_s_prefill_approx",
        "ttft_s",
        "elapsed_s",
    ):
        values = [record[key] for record in records if isinstance(record.get(key), (int, float))]
        if values:
            summary[f"mean_{key}"] = statistics.fmean(values)
            summary[f"min_{key}"] = min(values)
            summary[f"max_{key}"] = max(values)
    return {key: round_float(value) for key, value in summary.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--scenario", action="append", choices=sorted(SCENARIOS))
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--seed", type=int, default=20260525)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    model, max_model_len = fetch_model(base_url, args.timeout)
    selected = args.scenario or ["short_decode", "prefill_16k", "near32k"]

    output: dict[str, Any] = {
        "base_url": base_url,
        "model": model,
        "reported_max_model_len": max_model_len,
        "warmups": args.warmups,
        "repeats": args.repeats,
        "scenarios": {},
    }

    for scenario_name in selected:
        scenario = SCENARIOS[scenario_name]
        prompt = build_prompt(scenario_name, scenario["prompt_lines"])
        warmup_records = []
        measured_records = []
        for index in range(args.warmups):
            warmup_records.append(
                stream_completion(
                    base_url,
                    model,
                    prompt,
                    scenario["max_tokens"],
                    args.timeout,
                    args.seed + index,
                )
            )
        for index in range(args.repeats):
            measured_records.append(
                stream_completion(
                    base_url,
                    model,
                    prompt,
                    scenario["max_tokens"],
                    args.timeout,
                    args.seed + 1000 + index,
                )
            )

        output["scenarios"][scenario_name] = {
            "description": scenario["description"],
            "prompt_lines": scenario["prompt_lines"],
            "requested_output_tokens": scenario["max_tokens"],
            "warmups": warmup_records,
            "records": measured_records,
            "summary": summarize(measured_records),
        }

        summary = output["scenarios"][scenario_name]["summary"]
        print(
            json.dumps(
                {
                    "scenario": scenario_name,
                    "prompt_tokens": measured_records[-1].get("prompt_tokens"),
                    "completion_tokens": measured_records[-1].get("completion_tokens"),
                    "mean_tok_s_out_after_ttft": summary.get(
                        "mean_tok_s_out_after_ttft"
                    ),
                    "mean_ttft_s": summary.get("mean_ttft_s"),
                }
            )
        )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n")
    print(f"wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
