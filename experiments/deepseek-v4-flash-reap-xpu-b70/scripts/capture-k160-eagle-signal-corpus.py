#!/usr/bin/env python3
"""Drive one-active-generation K160 feature capture from a prompt manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

CATEGORY_SHARES = {
    "prose": 0.45,
    "code": 0.15,
    "math": 0.15,
    "extraction": 0.15,
    "low-locality": 0.10,
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def request_key(request_id: str) -> int:
    digest = hashlib.sha256(request_id.encode()).digest()
    return int.from_bytes(digest[:8], "little") & ((1 << 63) - 1)


def metrics(base_url: str, timeout: int) -> dict[str, float]:
    with urllib.request.urlopen(
        f"{base_url.rstrip('/')}/metrics", timeout=timeout
    ) as r:
        text = r.read().decode()
    result = {"running": 0.0, "waiting": 0.0}
    names = {
        "vllm:num_requests_running": "running",
        "vllm:num_requests_waiting": "waiting",
    }
    for line in text.splitlines():
        for metric_name, key in names.items():
            if line.startswith(metric_name + "{") or line.startswith(metric_name + " "):
                result[key] += float(line.rsplit(" ", 1)[-1])
    return result


def post(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    request_id: str,
    timeout: int,
) -> dict[str, Any]:
    cache_salt = str(uuid.uuid4())
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "stream": False,
        "return_token_ids": True,
        "cache_salt": cache_salt,
        "request_id": request_id,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    elapsed = time.perf_counter() - started
    choice = raw["choices"][0]
    message = choice.get("message") or {}
    usage = raw.get("usage") or {}
    output_text = message.get("content") or ""
    token_ids = (
        choice.get("token_ids")
        or message.get("token_ids")
        or raw.get("token_ids")
        or []
    )
    return {
        "response_id": raw["id"],
        "response_prompt_token_ids": raw.get("prompt_token_ids"),
        "elapsed_s": elapsed,
        "finish_reason": choice.get("finish_reason"),
        "usage": usage,
        "cached_tokens": (usage.get("prompt_tokens_details") or {}).get(
            "cached_tokens"
        ),
        "output_text": output_text,
        "output_sha256": sha(output_text),
        "output_token_ids": token_ids,
        "cache_salt_sha256": sha(cache_salt),
    }


def render_prompt(
    base_url: str,
    model: str,
    prompt: str,
    request_id: str,
    timeout: int,
) -> list[int]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0,
        "request_id": request_id,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions/render",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    return [int(token_id) for token_id in raw["token_ids"]]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="deepseek-v4-flash-k160")
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "dev", "smoke"), required=True)
    parser.add_argument("--target-tokens", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm-file", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-prompt-tokens", type=int, default=500)
    parser.add_argument("--skip-manifest", type=Path)
    parser.add_argument("--runtime-skip-prompt-id", action="append", default=[])
    args = parser.parse_args()

    prompts = load_jsonl(args.prompts)
    if not prompts:
        raise RuntimeError("prompt manifest is empty")
    if args.arm_file is not None:
        raise ValueError("teacher generation cannot arm feature capture")
    for item in prompts:
        if sha(item["prompt"]) != item["prompt_sha256"]:
            raise RuntimeError(f"prompt hash mismatch: {item['prompt_id']}")
    if args.split in {"train", "dev"} and any(
        item["split"] != args.split for item in prompts
    ):
        raise RuntimeError("prompt manifest split does not match requested split")
    quotas = {
        category: int(args.target_tokens * share)
        for category, share in CATEGORY_SHARES.items()
    }
    quotas["prose"] += args.target_tokens - sum(quotas.values())
    if args.split == "smoke":
        quotas = {name: 0 for name in CATEGORY_SHARES}
        quotas["prose"] = args.target_tokens

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and not args.resume:
        raise FileExistsError(args.output)
    prior_rows = load_jsonl(args.output) if args.output.exists() else []
    skip_manifest = args.skip_manifest or args.output.with_suffix(".skips.jsonl")
    if skip_manifest.exists() and not args.resume:
        raise FileExistsError(skip_manifest)
    skipped_rows = load_jsonl(skip_manifest) if skip_manifest.exists() else []
    prompt_by_id = {item["prompt_id"]: item for item in prompts}
    existing_skipped_ids = {row["prompt_id"] for row in skipped_rows}
    for prompt_id in args.runtime_skip_prompt_id:
        if prompt_id in existing_skipped_ids:
            raise RuntimeError(f"runtime skip prompt already recorded: {prompt_id}")
        item = prompt_by_id.get(prompt_id)
        if item is None:
            raise RuntimeError(f"runtime skip prompt is not in source: {prompt_id}")
        prompt_token_ids = render_prompt(
            args.base_url,
            args.model,
            item["prompt"],
            f"runtime-skip-audit-{item['prompt_sha256'][:12]}",
            args.timeout,
        )
        skip_manifest.parent.mkdir(parents=True, exist_ok=True)
        skip_row = {
            "schema_version": "k160-eagle-prompt-skip-v1",
            "prompt_id": prompt_id,
            "prompt_sha256": item["prompt_sha256"],
            "category": item["category"],
            "prompt_tokens": len(prompt_token_ids),
            "reason": "operator_audited_runtime_hang",
            "max_prompt_tokens": args.max_prompt_tokens,
        }
        with skip_manifest.open("a" if skip_manifest.exists() else "x") as stream:
            stream.write(json.dumps(skip_row) + "\n")
        skipped_rows.append(skip_row)
        existing_skipped_ids.add(prompt_id)
    if any(row["split"] != args.split for row in prior_rows):
        raise RuntimeError("resume manifest split does not match requested split")
    prompt_queues = {
        category: [item for item in prompts if item["category"] == category]
        for category in CATEGORY_SHARES
    }
    counts = {
        category: sum(
            int(row["response"]["usage"].get("completion_tokens") or 0)
            for row in prior_rows
            if row["category"] == category
        )
        for category in CATEGORY_SHARES
    }
    historical_skipped_ids = {row["prompt_id"] for row in skipped_rows}
    if len(historical_skipped_ids) != len(skipped_rows):
        raise RuntimeError("skip manifest contains duplicate prompt IDs")
    used_prompt_ids = {row["prompt_id"] for row in prior_rows}
    if len(used_prompt_ids) != len(prior_rows):
        raise RuntimeError("resume manifest contains duplicate prompt IDs")
    used_request_ids = {row["request_id"] for row in prior_rows}
    if len(used_request_ids) != len(prior_rows):
        raise RuntimeError("resume manifest contains duplicate request IDs")
    prior_by_prompt_id = {row["prompt_id"]: row for row in prior_rows}
    for prompt_id in historical_skipped_ids & used_prompt_ids:
        if not prior_by_prompt_id[prompt_id].get("historical_skip_reactivated"):
            raise RuntimeError("unmarked prompt appears in corpus and skip manifests")
    for row in skipped_rows:
        item = prompt_by_id.get(row["prompt_id"])
        if (
            item is None
            or row["category"] != item["category"]
            or row["prompt_sha256"] != item["prompt_sha256"]
        ):
            raise RuntimeError("skip manifest does not match prompt source")
    active_skipped_ids = {
        row["prompt_id"]
        for row in skipped_rows
        if int(row["prompt_tokens"]) > args.max_prompt_tokens
        or row.get("reason")
        in {
            "operator_audited_runtime_hang",
            "runtime_request_timeout",
            "runtime_request_http_5xx",
        }
    } - used_prompt_ids
    indices = {}
    for category, queue in prompt_queues.items():
        index = 0
        while index < len(queue) and queue[index]["prompt_id"] in (
            used_prompt_ids | active_skipped_ids
        ):
            index += 1
        indices[category] = index
    seen = {category: 0 for category in CATEGORY_SHARES}
    for expected_index, row in enumerate(prior_rows):
        category = row["category"]
        queue = prompt_queues[category]
        while queue[seen[category]]["prompt_id"] in active_skipped_ids:
            seen[category] += 1
        expected_prompt = queue[seen[category]]
        if (
            int(row["request_index"]) != expected_index
            or row["prompt_id"] != expected_prompt["prompt_id"]
        ):
            raise RuntimeError("resume manifest is not a valid deterministic prefix")
        seen[category] += 1
    namespace = {"train": "eagletrain", "dev": "eagledev", "smoke": "eaglesmoke"}[
        args.split
    ]
    started = time.time()
    with (
        args.output.open("a" if args.output.exists() else "x") as stream,
        skip_manifest.open("a" if skip_manifest.exists() else "x") as skip_stream,
    ):
        request_index = len(prior_rows)
        while any(counts[name] < quotas[name] for name in quotas):
            category = max(quotas, key=lambda name: quotas[name] - counts[name])
            if counts[category] >= quotas[category]:
                continue
            queue = prompt_queues[category]
            index = indices[category]
            while (
                index < len(queue) and queue[index]["prompt_id"] in active_skipped_ids
            ):
                index += 1
            if index >= len(queue):
                raise RuntimeError(f"exhausted unique {category} prompts")
            item = queue[index]
            # ``index`` can be ahead of the saved cursor after walking prompts
            # excluded by the stability guard.  Advance from the selected
            # position, not merely from the old cursor, or a resumed run can
            # select the same reactivated prompt more than once.
            indices[category] = index + 1
            remaining = quotas[category] - counts[category]
            max_tokens = min(args.max_tokens, remaining)
            request_id = f"{namespace}-{request_index:06d}-{item['prompt_sha256'][:12]}"
            if request_id in used_request_ids:
                raise RuntimeError(f"request ID collision on resume: {request_id}")
            prompt_token_ids = render_prompt(
                args.base_url,
                args.model,
                item["prompt"],
                request_id,
                args.timeout,
            )
            if len(prompt_token_ids) > args.max_prompt_tokens:
                skip_stream.write(
                    json.dumps(
                        {
                            "schema_version": "k160-eagle-prompt-skip-v1",
                            "prompt_id": item["prompt_id"],
                            "prompt_sha256": item["prompt_sha256"],
                            "category": category,
                            "prompt_tokens": len(prompt_token_ids),
                            "reason": "prefill_runtime_stability_guard",
                            "max_prompt_tokens": args.max_prompt_tokens,
                        }
                    )
                    + "\n"
                )
                skip_stream.flush()
                active_skipped_ids.add(item["prompt_id"])
                continue
            max_tokens = min(max_tokens, 2048 - len(prompt_token_ids) - 1)
            if max_tokens <= 0:
                raise RuntimeError(
                    f"rendered prompt leaves no replay-safe context: {request_id}"
                )
            before = metrics(args.base_url, args.timeout)
            if before["running"] != 0 or before["waiting"] != 0:
                raise RuntimeError(f"endpoint busy before {request_id}: {before}")
            try:
                response = post(
                    args.base_url,
                    args.model,
                    item["prompt"],
                    max_tokens,
                    request_id,
                    args.timeout,
                )
            except (TimeoutError, urllib.error.HTTPError) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code < 500:
                    raise
                reason = (
                    "runtime_request_http_5xx"
                    if isinstance(error, urllib.error.HTTPError)
                    else "runtime_request_timeout"
                )
                skip_stream.write(
                    json.dumps(
                        {
                            "schema_version": "k160-eagle-prompt-skip-v1",
                            "prompt_id": item["prompt_id"],
                            "prompt_sha256": item["prompt_sha256"],
                            "category": category,
                            "prompt_tokens": len(prompt_token_ids),
                            "reason": reason,
                            "max_prompt_tokens": args.max_prompt_tokens,
                            "request_id": request_id,
                            "timeout_s": args.timeout,
                            "http_status": getattr(error, "code", None),
                        }
                    )
                    + "\n"
                )
                skip_stream.flush()
                raise
            after = metrics(args.base_url, args.timeout)
            if after["running"] != 0 or after["waiting"] != 0:
                raise RuntimeError(f"endpoint not idle after {request_id}: {after}")
            cached = response["cached_tokens"]
            if cached not in (0, None):
                raise RuntimeError(f"cached tokens were nonzero for {request_id}")
            completion_tokens = int(response["usage"].get("completion_tokens") or 0)
            if completion_tokens <= 0:
                raise RuntimeError(f"no completion tokens for {request_id}")
            if len(response["output_token_ids"]) != completion_tokens:
                raise RuntimeError(f"output token count mismatch for {request_id}")
            prompt_usage = int(response["usage"].get("prompt_tokens") or 0)
            if len(prompt_token_ids) != prompt_usage:
                raise RuntimeError(f"prompt token count mismatch for {request_id}")
            response_prompt_ids = response["response_prompt_token_ids"]
            if (
                response_prompt_ids is not None
                and [int(token_id) for token_id in response_prompt_ids]
                != prompt_token_ids
            ):
                raise RuntimeError(
                    f"render/response prompt IDs differ for {request_id}"
                )
            if len(prompt_token_ids) + completion_tokens + 1 > 2048:
                raise RuntimeError(
                    f"trajectory exceeds replay context for {request_id}"
                )
            counts[category] += completion_tokens
            row = {
                "schema_version": "k160-eagle-capture-request-v1",
                "split": args.split,
                "category": category,
                "request_index": request_index,
                "request_id": request_id,
                "request_key": request_key(response["response_id"]),
                "prompt_id": item["prompt_id"],
                "prompt_sha256": item["prompt_sha256"],
                "historical_skip_reactivated": (
                    item["prompt_id"] in historical_skipped_ids
                ),
                "generation_max_prompt_tokens": args.max_prompt_tokens,
                "source_id": item["source_id"],
                "source_revision": item["source_revision"],
                "prompt_token_ids": prompt_token_ids,
                "max_tokens": max_tokens,
                "response": response,
                "cumulative_category_tokens": counts[category],
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            used_prompt_ids.add(item["prompt_id"])
            used_request_ids.add(request_id)
            request_index += 1
            if request_index % 20 == 0:
                print(
                    json.dumps(
                        {
                            "requests": request_index,
                            "completion_tokens": sum(counts.values()),
                            "counts": counts,
                            "elapsed_s": time.time() - started,
                        }
                    ),
                    flush=True,
                )
    print(
        json.dumps(
            {
                "requests": request_index,
                "completion_tokens": sum(counts.values()),
                "counts": counts,
                "quotas": quotas,
                "elapsed_s": time.time() - started,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
