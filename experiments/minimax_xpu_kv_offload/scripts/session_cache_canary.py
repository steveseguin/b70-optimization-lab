#!/usr/bin/env python3
"""Run deterministic OpenAI-compatible completion canaries for KV offload tests.

The script is intentionally stdlib-only so it can run on a freshly installed
Ubuntu box without adding another Python dependency.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


STRICT_WORDS = {
    "A": "red",
    "B": "blue",
    "C": "green",
    "D": "yellow",
    "E": "purple",
    "F": "silver",
    "G": "orange",
    "H": "white",
}
STRICT_WORD_PROMPT_VERSION = "strict-word-answer-space-v2"


def fetch_model(base_url: str) -> str:
    with urllib.request.urlopen(f"{base_url}/v1/models", timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["data"][0]["id"]


def build_checklist_prompt(label: str, lines: int) -> str:
    body = "\n".join(
        f"Session {label} line {i:04d}: CPU KV offload exact session-cache "
        f"validation text with marker {label}-{i:04d}."
        for i in range(lines)
    )
    return (
        f"{body}\n\n"
        f"Final task for Session {label}: write a deterministic six item "
        "checklist about preserving exact KV cache quality. Use plain English, "
        "number the items, and do not mention this instruction."
    )


def build_strict_word_prompt(label: str, lines: int) -> tuple[str, str]:
    expected = STRICT_WORDS.get(label.upper())
    if expected is None:
        expected = f"word{label.lower()}"
    body = "\n".join(
        f"Context row {i:04d} for lane {label}: preserve exact key value cache "
        f"bytes, page order, token positions, and session marker {label}-{i:04d}."
        for i in range(lines)
    )
    prompt = (
        f"{body}\n\n"
        "Task: copy the final target word exactly. Return one word only. "
        "No punctuation. No explanation.\n\n"
        "Example 1\n"
        "TARGET_WORD: red\n"
        "ANSWER: red\n\n"
        "Example 2\n"
        "TARGET_WORD: blue\n"
        "ANSWER: blue\n\n"
        "Example 3\n"
        "TARGET_WORD: green\n"
        "ANSWER: green\n\n"
        f"Final target\n"
        f"TARGET_WORD: {expected}\n"
        "ANSWER: "
    )
    return prompt, expected


def build_prompt(label: str, lines: int, prompt_mode: str) -> tuple[str, str | None]:
    if prompt_mode == "checklist":
        return build_checklist_prompt(label, lines), None
    if prompt_mode == "strict-word":
        return build_strict_word_prompt(label, lines)
    raise ValueError(f"unknown prompt mode: {prompt_mode}")


def first_word(text: str) -> str:
    match = re.search(r"[A-Za-z0-9_]+", text)
    if match is None:
        return ""
    return match.group(0).lower()


def post_stream_completion(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    seed: int,
    timeout: int,
    stop: list[str] | None,
) -> dict[str, Any]:
    request_payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": 1.0,
        "seed": seed,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if stop:
        request_payload["stop"] = stop
    data = json.dumps(request_payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    first_text_at: float | None = None
    chunks = 0
    text_parts: list[str] = []
    usage: dict[str, Any] | None = None

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload_text = line[5:].strip()
                if payload_text == "[DONE]":
                    break
                payload = json.loads(payload_text)
                if payload.get("usage"):
                    usage = payload["usage"]
                for choice in payload.get("choices", []):
                    delta = choice.get("text") or ""
                    if delta and first_text_at is None:
                        first_text_at = time.perf_counter()
                    if delta:
                        chunks += 1
                        text_parts.append(delta)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc

    ended = time.perf_counter()
    text = "".join(text_parts)
    completion_tokens = usage.get("completion_tokens") if usage else None
    prompt_tokens = usage.get("prompt_tokens") if usage else None
    total_tokens = usage.get("total_tokens") if usage else None
    elapsed_s = ended - started
    ttft_s = None if first_text_at is None else first_text_at - started
    post_ttft_s = None if first_text_at is None else ended - first_text_at
    tok_s_out_wall = None
    tok_s_out_after_ttft = None
    if isinstance(completion_tokens, int) and completion_tokens > 0:
        tok_s_out_wall = completion_tokens / elapsed_s
        if post_ttft_s and post_ttft_s > 0:
            tok_s_out_after_ttft = completion_tokens / post_ttft_s

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "elapsed_s": elapsed_s,
        "ttft_s": ttft_s,
        "post_ttft_s": post_ttft_s,
        "tok_s_out_wall": tok_s_out_wall,
        "tok_s_out_after_ttft": tok_s_out_after_ttft,
        "stream_text_chunks": chunks,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text": text,
        "usage": usage,
    }


def run_one(
    base_url: str,
    model: str,
    label: str,
    lines: int,
    max_tokens: int,
    temperature: float,
    seed: int,
    timeout: int,
    prompt_mode: str,
    stop: list[str] | None,
) -> dict[str, Any]:
    prompt, expected_word = build_prompt(label, lines, prompt_mode)
    result = post_stream_completion(
        base_url=base_url,
        model=model,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        seed=seed,
        timeout=timeout,
        stop=stop,
    )
    observed_word = first_word(result["text"])
    result.update(
        {
            "label": label,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_mode": prompt_mode,
            "prompt_version": (
                STRICT_WORD_PROMPT_VERSION
                if prompt_mode == "strict-word"
                else "checklist-v1"
            ),
            "prompt_lines": lines,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "seed": seed,
            "expected_word": expected_word,
            "observed_word": observed_word,
            "expected_word_match": (
                None if expected_word is None else observed_word == expected_word
            ),
        }
    )
    return result


def compare_results(
    baseline_path: Path | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    labels = sorted({item["label"] for item in current["results"]})
    for label in labels:
        pass_items = [
            item for item in current["results"] if item["label"] == label
        ]
        pass_items.sort(key=lambda item: item["pass_index"])
        if len(pass_items) > 1:
            first_hash = pass_items[0]["sha256"]
            first_word_value = pass_items[0]["observed_word"]
            comparisons[f"{label}_same_across_passes"] = all(
                item["sha256"] == first_hash for item in pass_items[1:]
            )
            comparisons[f"{label}_same_word_across_passes"] = all(
                item["observed_word"] == first_word_value for item in pass_items[1:]
            )
            if pass_items[0]["expected_word"] is not None:
                comparisons[f"{label}_expected_word_all_passes"] = all(
                    item["expected_word_match"] for item in pass_items
                )

    if baseline_path:
        baseline = json.loads(baseline_path.read_text())
        baseline_by_label = {
            item["label"]: item for item in baseline.get("results", [])
        }
        for item in current["results"]:
            base_item = baseline_by_label.get(item["label"])
            if not base_item:
                continue
            key = f"{item['label']}_pass{item['pass_index']}_matches_baseline"
            comparisons[key] = item["sha256"] == base_item["sha256"]
            word_key = (
                f"{item['label']}_pass{item['pass_index']}_word_matches_baseline"
            )
            comparisons[word_key] = (
                item["observed_word"] == base_item.get("observed_word")
            )

    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=None)
    parser.add_argument("--labels", default="A,B")
    parser.add_argument(
        "--prompt-mode",
        choices=["checklist", "strict-word"],
        default="checklist",
    )
    parser.add_argument("--prompt-lines", type=int, default=700)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--stop-newline",
        action="store_true",
        help="Stop generation at a newline. Useful for strict-word mode.",
    )
    parser.add_argument("--baseline-json", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    if not labels:
        raise SystemExit("at least one label is required")

    model = args.model or fetch_model(args.base_url)
    output: dict[str, Any] = {
        "started_at_unix": time.time(),
        "base_url": args.base_url,
        "model": model,
        "prompt_mode": args.prompt_mode,
        "prompt_version": (
            STRICT_WORD_PROMPT_VERSION
            if args.prompt_mode == "strict-word"
            else "checklist-v1"
        ),
        "prompt_lines": args.prompt_lines,
        "max_tokens": args.max_tokens,
        "passes": args.passes,
        "concurrency": args.concurrency,
        "temperature": args.temperature,
        "seed": args.seed,
        "stop": ["\n"] if args.stop_newline else None,
        "results": [],
    }

    for pass_index in range(1, args.passes + 1):
        print(f"pass {pass_index}/{args.passes}", flush=True)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.concurrency
        ) as executor:
            future_to_label = {
                executor.submit(
                    run_one,
                    args.base_url,
                    model,
                    label,
                    args.prompt_lines,
                    args.max_tokens,
                    args.temperature,
                    args.seed,
                    args.timeout,
                    args.prompt_mode,
                    output["stop"],
                ): label
                for label in labels
            }
            for future in concurrent.futures.as_completed(future_to_label):
                label = future_to_label[future]
                item = future.result()
                item["pass_index"] = pass_index
                output["results"].append(item)
                print(
                    json.dumps(
                        {
                            "label": label,
                            "pass_index": pass_index,
                            "prompt_tokens": item["prompt_tokens"],
                            "completion_tokens": item["completion_tokens"],
                            "elapsed_s": round(item["elapsed_s"], 3),
                            "ttft_s": (
                                None
                                if item["ttft_s"] is None
                                else round(item["ttft_s"], 3)
                            ),
                            "tok_s_out_after_ttft": (
                                None
                                if item["tok_s_out_after_ttft"] is None
                                else round(item["tok_s_out_after_ttft"], 2)
                            ),
                            "expected_word": item["expected_word"],
                            "observed_word": item["observed_word"],
                            "expected_word_match": item["expected_word_match"],
                            "sha256": item["sha256"][:16],
                        }
                    ),
                    flush=True,
                )

    output["finished_at_unix"] = time.time()
    output["comparisons"] = compare_results(args.baseline_json, output)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2, sort_keys=True))
    print(f"wrote {args.output_json}", flush=True)
    if output["comparisons"]:
        print(json.dumps(output["comparisons"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
