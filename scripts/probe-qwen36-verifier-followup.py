#!/usr/bin/env python3
"""Probe verifier-only next-token preference for speculative trace mismatches.

The replay script can identify rows where a suppressed full-accept bonus token
is not replayed by the next scheduler row. This script reconstructs the exact
chat-template prompt, appends the visible emitted token prefix up to the
suppression point, and asks the accepted verifier endpoint which token it
prefers via /generative_scoring.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_TOKENIZER = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8"
    "/snapshots/cced56592e8c8935f8220836b4baa04dfd389118"
)


def load_trace_helpers() -> Any:
    helper_path = Path(__file__).with_name("qwen36-quality-token-trace.py")
    spec = importlib.util.spec_from_file_location("qwen36_quality_token_trace", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper module from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def score_first_label(
    base_url: str,
    model: str,
    prompt_token_ids: list[int],
    first_label: int,
    second_label: int,
    timeout: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    payload = {
        "model": model,
        "query": prompt_token_ids,
        "items": [[]],
        "label_token_ids": [first_label, second_label],
        "apply_softmax": True,
        "add_special_tokens": False,
    }
    data = post_json(f"{base_url.rstrip('/')}/generative_scoring", payload, timeout)
    elapsed = time.perf_counter() - started
    return {
        "label_token_ids": [first_label, second_label],
        "score": data["data"][0]["score"],
        "elapsed_s": elapsed,
        "usage": data.get("usage"),
        "response_id": data.get("id"),
    }


def chat_prompt_ids(tokenizer: Any, messages: list[dict[str, str]]) -> list[int]:
    encoded = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_dict=True,
    )
    ids = encoded["input_ids"]
    if not ids or not isinstance(ids[0], int):
        raise ValueError("Unexpected chat template input_ids shape")
    return list(ids)


def build_case_map(tokenizer: Any, long_context_tokens: int, helpers: Any) -> dict[str, dict[str, Any]]:
    return {
        case["name"]: case
        for case in helpers.make_cases(tokenizer, long_context_tokens)
    }


def int_list(value: Any) -> list[int]:
    if not value:
        return []
    return [int(item) for item in value]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen36-35b-a3b-fp8")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--replay-json", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--default-long-context-tokens", type=int, default=8192)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    helpers = load_trace_helpers()
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    replay = json.loads(args.replay_json.read_text())

    probes: list[dict[str, Any]] = []
    case_cache: dict[int, dict[str, dict[str, Any]]] = {}

    for request_summary in replay.get("request_summaries", []):
        token_case = request_summary.get("token_trace_case") or {}
        case_name = token_case.get("name")
        if not case_name:
            continue
        long_context_tokens = int(
            token_case.get("requested_context_tokens")
            or args.default_long_context_tokens
        )
        if long_context_tokens not in case_cache:
            case_cache[long_context_tokens] = build_case_map(
                tokenizer, long_context_tokens, helpers
            )
        case = case_cache[long_context_tokens].get(case_name)
        if case is None:
            continue
        prompt_ids = chat_prompt_ids(tokenizer, case["messages"])
        row_summaries = request_summary.get("row_summaries", [])
        visible_output_ids: list[int] = []
        if row_summaries:
            first_before = (
                (row_summaries[0].get("state_transition") or {}).get("before")
                or {}
            )
            visible_output_ids = int_list(first_before.get("last_output_token_ids"))

        for row in row_summaries:
            emitted = int_list(
                row.get("new_token_ids_after_stop_check")
                or row.get("emitted_token_ids")
            )
            visible_output_ids.extend(emitted)
            followup = row.get("followup_check")
            if not followup:
                continue
            suppressed = followup.get("suppressed_bonus_token_id")
            next_first = followup.get("next_generated_first_token_id")
            if suppressed is None or next_first is None or suppressed == next_first:
                continue

            suppressed = int(suppressed)
            next_first = int(next_first)
            probe_prompt_ids = prompt_ids + visible_output_ids
            suppressed_score = score_first_label(
                args.base_url,
                args.model,
                probe_prompt_ids,
                suppressed,
                next_first,
                args.timeout,
            )
            next_score = score_first_label(
                args.base_url,
                args.model,
                probe_prompt_ids,
                next_first,
                suppressed,
                args.timeout,
            )
            probes.append({
                "req_id": request_summary.get("req_id"),
                "case_name": case_name,
                "line_no": followup.get("line_no"),
                "next_line_no": followup.get("next_line_no"),
                "prompt_tokens": len(prompt_ids),
                "visible_output_tokens": len(visible_output_ids),
                "probe_prompt_tokens": len(probe_prompt_ids),
                "visible_output_text": tokenizer.decode(
                    visible_output_ids, skip_special_tokens=False
                ),
                "visible_output_tail_token_ids": visible_output_ids[-32:],
                "suppressed_bonus_token_id": suppressed,
                "suppressed_bonus_text": tokenizer.decode(
                    [suppressed], skip_special_tokens=False
                ),
                "next_generated_first_token_id": next_first,
                "next_generated_first_text": tokenizer.decode(
                    [next_first], skip_special_tokens=False
                ),
                "suppressed_vs_next": suppressed_score,
                "next_vs_suppressed": next_score,
                "verifier_prefers_suppressed": (
                    suppressed_score["score"] > next_score["score"]
                ),
            })

    output = {
        "base_url": args.base_url.rstrip("/"),
        "model": args.model,
        "tokenizer": args.tokenizer,
        "replay_json": str(args.replay_json),
        "probe_count": len(probes),
        "verifier_prefers_suppressed_count": sum(
            1 for probe in probes if probe.get("verifier_prefers_suppressed")
        ),
        "probes": probes,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({
        "output_json": str(args.output_json),
        "probe_count": output["probe_count"],
        "verifier_prefers_suppressed_count": output[
            "verifier_prefers_suppressed_count"
        ],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
