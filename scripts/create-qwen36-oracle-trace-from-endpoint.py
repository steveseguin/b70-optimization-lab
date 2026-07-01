#!/usr/bin/env python3
"""Create a proposer-compatible oracle trace from a live OpenAI endpoint.

This uses the same prompt construction as measure-openai-endpoint-metrics.py
so an oracle-spec server can be benchmarked on the exact standard prompt
instead of silently falling back to draftless generation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


DEFAULT_TOKENIZER = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8"
    "/snapshots/cced56592e8c8935f8220836b4baa04dfd389118"
)


def load_metrics_module() -> Any:
    path = Path(__file__).with_name("measure-openai-endpoint-metrics.py")
    spec = importlib.util.spec_from_file_location("measure_openai_endpoint_metrics", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
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
        return {
            "status": resp.status,
            "headers": {key.lower(): value for key, value in resp.headers.items()},
            "json": json.loads(resp.read().decode("utf-8")),
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def first_choice(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("completion response did not include choices")
    return choices[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18181")
    parser.add_argument("--model", default=None)
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--prompt-tokens", type=int, default=512)
    parser.add_argument("--output-tokens", type=int, default=512)
    parser.add_argument(
        "--prompt-kind",
        choices=["text", "preset", "vllm-random"],
        default="preset",
    )
    parser.add_argument(
        "--prompt-preset",
        choices=["repetitive", "natural-chat", "code", "structured", "math-reasoning"],
        default="natural-chat",
    )
    parser.add_argument("--prompt-file", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--random-prefix-len", type=int, default=0)
    parser.add_argument("--ignore-eos", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--request-id-prefix", default="qwen36-oracle-trace")
    parser.add_argument("--case-name", default=None)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    metrics = load_metrics_module()
    base_url = args.base_url.rstrip("/")
    models = metrics.get_json(f"{base_url}/v1/models")
    model = args.model or models["data"][0]["id"]
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    prompt = metrics.make_prompt(
        tokenizer,
        prompt_kind=args.prompt_kind,
        prompt_preset=args.prompt_preset,
        prompt_file=args.prompt_file,
        target_tokens=args.prompt_tokens,
        output_tokens=args.output_tokens,
        seed=args.seed,
        random_prefix_len=args.random_prefix_len,
    )
    prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)

    request_id = f"{args.request_id_prefix}-000000"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "max_tokens": args.output_tokens,
        "temperature": 0,
        "top_p": 1.0,
        "seed": args.seed,
        "return_token_ids": True,
        "request_id": request_id,
    }
    if args.ignore_eos:
        payload["ignore_eos"] = True

    started_unix = time.time()
    started = time.perf_counter()
    response = post_json(f"{base_url}/v1/completions", payload, args.timeout)
    elapsed = time.perf_counter() - started
    finished_unix = time.time()

    data = response["json"]
    choice = first_choice(data)
    text = choice.get("text") or ""
    api_output_ids = choice.get("token_ids")
    output_ids = (
        [int(value) for value in api_output_ids]
        if isinstance(api_output_ids, list)
        else tokenizer.encode(text, add_special_tokens=False)
    )
    api_prompt_ids = choice.get("prompt_token_ids")
    trace_prompt_ids = (
        [int(value) for value in api_prompt_ids]
        if isinstance(api_prompt_ids, list)
        else prompt_ids
    )

    case_name = args.case_name or (
        f"{args.prompt_kind}-{args.prompt_preset}-p{len(trace_prompt_ids)}-o{len(output_ids)}"
    )
    case = {
        "name": case_name,
        "seed": args.seed,
        "ignore_eos": args.ignore_eos,
        "max_tokens": args.output_tokens,
        "prompt_kind": args.prompt_kind,
        "prompt_preset": args.prompt_preset,
        "prompt_file": args.prompt_file,
        "prompt_sha256": sha256_text(prompt),
        "prompt": prompt,
        "prompt_token_count": len(trace_prompt_ids),
        "prompt_token_ids": trace_prompt_ids,
        "prompt_token_ids_head": trace_prompt_ids[:32],
        "prompt_token_ids_tail": trace_prompt_ids[-64:],
        "tokenizer_prompt_token_ids": prompt_ids,
        "api_prompt_token_ids_match_tokenizer": trace_prompt_ids == prompt_ids,
        "request_started_at_unix": started_unix,
        "request_finished_at_unix": finished_unix,
        "elapsed_s": elapsed,
        "response_status": response["status"],
        "response_id": data.get("id"),
        "response_created": data.get("created"),
        "response_model": data.get("model"),
        "request_id": request_id,
        "text": text,
        "text_sha256": sha256_text(text),
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
        "output_token_count": len(output_ids),
        "output_token_ids": output_ids,
        "output_token_ids_source": (
            "api_token_ids" if isinstance(api_output_ids, list) else "retokenized_text"
        ),
    }
    artifact = {
        "created_at_unix": time.time(),
        "base_url": base_url,
        "model": model,
        "tokenizer": args.tokenizer,
        "server_model_record": models["data"][0],
        "prompt_tokens_requested": args.prompt_tokens,
        "output_tokens_requested": args.output_tokens,
        "cases": [case],
        "notes": [
            "Oracle trace created from a live endpoint using the exact benchmark prompt constructor.",
            "For production quality gates, compare candidate outputs against the accepted no-spec baseline before promotion.",
        ],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output_json": str(args.output_json),
        "case_name": case_name,
        "prompt_token_count": len(trace_prompt_ids),
        "output_token_count": len(output_ids),
        "api_prompt_token_ids_match_tokenizer": trace_prompt_ids == prompt_ids,
        "elapsed_s": elapsed,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
