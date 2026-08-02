#!/usr/bin/env python3
"""Exact-token long-context retrieval and decode gate for Laguna."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


PREFILL_TIME = "vllm:request_prefill_time_seconds"
PREFILL_TOKENS = "vllm:request_prefill_kv_computed_tokens"
DECODE_TIME = "vllm:request_decode_time_seconds"
SPEC_DRAFTS = "vllm:spec_decode_num_drafts_total"
SPEC_DRAFT_TOKENS = "vllm:spec_decode_num_draft_tokens_total"
SPEC_ACCEPTED = "vllm:spec_decode_num_accepted_tokens_total"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def token_hash(token_ids: list[int]) -> str:
    payload = ",".join(str(token_id) for token_id in token_ids).encode()
    return sha256_bytes(payload)


def as_ids(value: Any) -> list[int]:
    if isinstance(value, dict):
        value = value["input_ids"]
    elif hasattr(value, "input_ids"):
        value = value.input_ids
    if value and isinstance(value[0], list):
        value = value[0]
    return [int(token_id) for token_id in value]


def find_subsequence(haystack: list[int], needle: list[int]) -> int:
    matches = [
        index
        for index in range(len(haystack) - len(needle) + 1)
        if haystack[index:index + len(needle)] == needle
    ]
    if len(matches) != 1:
        raise ValueError(f"chat marker matches={matches}, expected exactly one")
    return matches[0]


def chat_frame(tokenizer: Any) -> tuple[list[int], list[int]]:
    marker = "LAGUNA_SPLIT_MARKER_7F0B"
    full = as_ids(
        tokenizer.apply_chat_template(
            [{"role": "user", "content": marker}],
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    )
    marker_ids = tokenizer.encode(marker, add_special_tokens=False)
    start = find_subsequence(full, marker_ids)
    return full[:start], full[start + len(marker_ids):]


def expected_json(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["id"],
        "project_code": case["project_code"],
        "answer_phrase": case["answer_phrase"],
        "sort_order": case["sort_order"],
        "arithmetic_result": int(case["arithmetic_result"]),
    }


def filler_ids(tokenizer: Any, case: dict[str, Any], count: int, salt: str) -> list[int]:
    if count <= 0:
        return []
    nonce = sha256_bytes(f"{case['id']}:{salt}".encode())[:12]
    text = (
        f" Archive distractor {nonce}. This record is not authoritative. "
        f"Its decoy project is DECOY-{nonce}, its decoy phrase is "
        f"IGNORE-{nonce}, its decoy arithmetic value is 0, and its decoy "
        "sort order is red, orange, green, blue. Continue scanning the "
        "archive until the explicitly authoritative fact block."
    )
    unit = tokenizer.encode(text, add_special_tokens=False)
    if not unit:
        raise ValueError("tokenizer produced an empty filler unit")
    return (unit * math.ceil(count / len(unit)))[:count]


def build_prompt_ids(
    tokenizer: Any,
    frame: tuple[list[int], list[int]],
    case: dict[str, Any],
) -> tuple[list[int], dict[str, Any]]:
    expected = expected_json(case)
    header = (
        "This is a long-context retrieval and sustained-decode test. Most "
        "records below are explicit distractors. Use only the block labeled "
        f"AUTHORITATIVE {case['id']}.\n"
    )
    fact = (
        f"\nBEGIN AUTHORITATIVE {case['id']}\n"
        f"case_id: {expected['case_id']}\n"
        f"project_code: {expected['project_code']}\n"
        f"answer_phrase: {expected['answer_phrase']}\n"
        f"sort_order: {expected['sort_order']}\n"
        f"arithmetic_result: {expected['arithmetic_result']}\n"
        f"END AUTHORITATIVE {case['id']}\n"
    )
    task = (
        "\nFirst output, from byte zero with no Markdown, one compact JSON "
        "object with keys case_id, project_code, answer_phrase, sort_order, "
        "and arithmetic_result, using the authoritative values. After the "
        "closing brace, continue with numbered prose about deterministic "
        "benchmark validation until the response limit."
    )
    prefix, suffix = frame
    header_ids = tokenizer.encode(header, add_special_tokens=False)
    fact_ids = tokenizer.encode(fact, add_special_tokens=False)
    task_ids = tokenizer.encode(task, add_special_tokens=False)
    fixed = prefix + header_ids + fact_ids + task_ids + suffix
    target = int(case["target_prompt_tokens"])
    if len(fixed) > target:
        raise ValueError(
            f"case {case['id']} fixed prompt {len(fixed)} exceeds target {target}"
        )
    fill_count = target - len(fixed)
    position = case["needle_position"]
    fractions = {"early": 0.10, "middle": 0.50, "late": 0.90}
    if position not in fractions:
        raise ValueError(f"unsupported needle position: {position}")
    before_count = int(fill_count * fractions[position])
    after_count = fill_count - before_count
    before = filler_ids(tokenizer, case, before_count, "before")
    after = filler_ids(tokenizer, case, after_count, "after")
    prompt_ids = prefix + header_ids + before + fact_ids + after + task_ids + suffix
    if len(prompt_ids) != target:
        raise AssertionError(
            f"case {case['id']} built {len(prompt_ids)} tokens, wanted {target}"
        )
    fact_start = len(prefix) + len(header_ids) + len(before)
    metadata = {
        "target_prompt_tokens": target,
        "actual_prompt_tokens": len(prompt_ids),
        "needle_position": position,
        "fact_start_token": fact_start,
        "fact_end_token": fact_start + len(fact_ids),
        "fact_start_fraction": fact_start / len(prompt_ids),
        "prompt_token_ids_sha256": token_hash(prompt_ids),
        "component_token_counts": {
            "chat_prefix": len(prefix),
            "header": len(header_ids),
            "filler_before": len(before),
            "fact": len(fact_ids),
            "filler_after": len(after),
            "task": len(task_ids),
            "chat_suffix": len(suffix),
        },
        "component_sha256": {
            "chat_prefix": token_hash(prefix),
            "header": token_hash(header_ids),
            "fact": token_hash(fact_ids),
            "task": token_hash(task_ids),
            "chat_suffix": token_hash(suffix),
        },
    }
    return prompt_ids, metadata


def build_sentinel_case(parent: dict[str, Any], index: int) -> dict[str, Any]:
    suffix = f"{index:02d}"
    return {
        "id": f"sentinel-after-{parent['id']}",
        "target_prompt_tokens": 256,
        "needle_position": "middle",
        "project_code": f"SENTINEL-{suffix}",
        "answer_phrase": f"LAGUNA-NEXT-REQUEST-OK-{suffix}",
        "arithmetic_result": 7000 + index,
        "sort_order": "blue, green, orange, red",
    }


def get_text(url: str, timeout: int) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def metric_value(metrics: str, name: str) -> float:
    pattern = re.compile(rf"^{re.escape(name)}(?:\{{[^}}]*\}})?\s+([^\s]+)$")
    values = []
    for line in metrics.splitlines():
        match = pattern.match(line)
        if match:
            values.append(float(match.group(1)))
    return sum(values)


def metric_snapshot(base_url: str, timeout: int) -> dict[str, float]:
    metrics = get_text(f"{base_url.rstrip('/')}/metrics", timeout)
    names = (
        f"{PREFILL_TIME}_sum",
        f"{PREFILL_TIME}_count",
        f"{PREFILL_TOKENS}_sum",
        f"{PREFILL_TOKENS}_count",
        f"{DECODE_TIME}_sum",
        f"{DECODE_TIME}_count",
        SPEC_DRAFTS,
        SPEC_DRAFT_TOKENS,
        SPEC_ACCEPTED,
    )
    return {name: metric_value(metrics, name) for name in names}


def metric_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    return {name: after[name] - before[name] for name in before}


def post_stream(
    *,
    base_url: str,
    model: str,
    prompt_ids: list[int],
    max_tokens: int,
    timeout: int,
    request_id: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt_ids,
        "add_special_tokens": False,
        "truncate_prompt_tokens": None,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "seed": 1,
        "ignore_eos": True,
        "stream": True,
        "stream_options": {"include_usage": True},
        "return_token_ids": True,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Request-Id": request_id,
        },
        method="POST",
    )
    started_epoch_s = time.time()
    started = time.perf_counter()
    first_at: float | None = None
    text_parts: list[str] = []
    token_ids: list[int] = []
    token_offsets: list[float] = []
    prompt_token_ids: list[int] | None = None
    usage: dict[str, Any] = {}
    per_request_metrics: dict[str, Any] = {}
    finish_reason: str | None = None
    response_request_id: str | None = None
    choice_events = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_request_id = response.headers.get("X-Request-Id")
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                event = json.loads(body)
                if event.get("usage"):
                    usage = event["usage"]
                if event.get("metrics"):
                    per_request_metrics = event["metrics"]
                for choice in event.get("choices", []):
                    choice_events += 1
                    if choice.get("finish_reason") is not None:
                        finish_reason = choice["finish_reason"]
                    returned_prompt = choice.get("prompt_token_ids")
                    if isinstance(returned_prompt, list):
                        prompt_token_ids = [int(value) for value in returned_prompt]
                    delta_ids = choice.get("token_ids")
                    if isinstance(delta_ids, list) and delta_ids:
                        now = time.perf_counter()
                        if first_at is None:
                            first_at = now
                        token_ids.extend(int(value) for value in delta_ids)
                        token_offsets.extend([now - started] * len(delta_ids))
                    text = choice.get("text") or ""
                    if text:
                        if first_at is None:
                            first_at = time.perf_counter()
                        text_parts.append(text)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body}") from error
    ended = time.perf_counter()
    text = "".join(text_parts)
    return {
        "request_id": request_id,
        "response_x_request_id": response_request_id,
        "request_started_epoch_s": started_epoch_s,
        "elapsed_s": ended - started,
        "client_ttft_s": None if first_at is None else first_at - started,
        "token_id_offsets_s": token_offsets,
        "token_ids": token_ids,
        "prompt_token_ids_returned": prompt_token_ids,
        "stream_token_id_count": len(token_ids),
        "choice_event_count": choice_events,
        "usage": usage,
        "per_request_metrics": per_request_metrics,
        "finish_reason": finish_reason,
        "text": text,
        "text_sha256": sha256_bytes(text.encode()),
        "text_preview": text[:500],
    }


def validate_json(text: str, expected: dict[str, Any]) -> dict[str, Any]:
    stripped = text.lstrip()
    prefix = text[:len(text) - len(stripped)]
    try:
        parsed, end = json.JSONDecoder().raw_decode(stripped)
    except json.JSONDecodeError as error:
        return {
            "passed": False,
            "error": str(error),
            "expected": expected,
            "parsed": None,
        }
    field_pass = {
        key: parsed.get(key) == value if isinstance(parsed, dict) else False
        for key, value in expected.items()
    }
    return {
        "passed": isinstance(parsed, dict) and all(field_pass.values()),
        "expected": expected,
        "parsed": parsed,
        "field_pass": field_pass,
        "leading_prefix_only_whitespace": not prefix.strip(),
        "json_end_character": len(prefix) + end,
        "continuation_characters": len(stripped) - end,
    }


def timing_metrics(row: dict[str, Any]) -> dict[str, Any]:
    offsets = row["token_id_offsets_s"]
    conventional = None
    historical = None
    full = None
    if len(offsets) >= 100 and offsets[99] > offsets[0]:
        conventional = 99 / (offsets[99] - offsets[0])
        historical = 100 / (offsets[99] - offsets[0])
    if len(offsets) >= 2 and offsets[-1] > offsets[0]:
        full = (len(offsets) - 1) / (offsets[-1] - offsets[0])
    server = row.get("per_request_metrics") or {}
    mean_itl_ms = server.get("mean_itl_ms")
    return {
        "conventional_99_interval_first_100_tok_s": conventional,
        "historical_100_event_first_100_tok_s": historical,
        "full_interval_tok_s": full,
        "server_decode_tok_s_from_mean_itl": (
            1000 / mean_itl_ms
            if isinstance(mean_itl_ms, (int, float)) and mean_itl_ms > 0
            else None
        ),
    }


def oracle_rows(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text())
    return {row["case_id"]: row for row in payload["rows"]}


def stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "count": len(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="laguna-s-2.1-int4")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--oracle", type=Path)
    parser.add_argument("--run-role", choices=("candidate", "teacher"), required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--case-id", action="append")
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text())
    cases = list(suite["cases"])
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if case["id"] in wanted]
    if not cases:
        raise SystemExit("no cases selected")

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path,
        local_files_only=True,
        fix_mistral_regex=True,
    )
    frame = chat_frame(tokenizer)
    prompts: list[tuple[dict[str, Any], list[int], dict[str, Any], int, str]] = []
    near_max_index = 0
    for case in cases:
        prompt_ids, metadata = build_prompt_ids(tokenizer, frame, case)
        prompts.append((case, prompt_ids, metadata, int(suite["max_output_tokens"]), "long"))
        if int(case["target_prompt_tokens"]) == 32640:
            near_max_index += 1
            sentinel = build_sentinel_case(case, near_max_index)
            sentinel_ids, sentinel_metadata = build_prompt_ids(
                tokenizer, frame, sentinel
            )
            prompts.append(
                (sentinel, sentinel_ids, sentinel_metadata, 128, "sentinel")
            )

    tokenizer_files = [
        args.model_path / "tokenizer.json",
        args.model_path / "tokenizer_config.json",
        args.model_path / "chat_template.jinja",
    ]
    tokenizer_hashes = {
        str(path): sha256_bytes(path.read_bytes())
        for path in tokenizer_files
        if path.is_file()
    }
    build_manifest = [
        {
            "case_id": case["id"],
            "row_kind": row_kind,
            "max_tokens": max_tokens,
            **metadata,
        }
        for case, _, metadata, max_tokens, row_kind in prompts
    ]
    base_result = {
        "schema": "laguna-long-context-gate-v1",
        "run_identity": {
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "run_role": args.run_role,
            "base_url": args.base_url,
            "model": args.model,
            "model_path": str(args.model_path),
            "suite": str(args.suite),
            "suite_sha256": sha256_bytes(args.suite.read_bytes()),
            "suite_id": suite["suite_id"],
            "oracle": None if args.oracle is None else str(args.oracle),
            "oracle_sha256": (
                None if args.oracle is None else sha256_bytes(args.oracle.read_bytes())
            ),
            "tokenizer_files_sha256": tokenizer_hashes,
            "api_mode": "completions-token-ids",
            "temperature": 0,
            "top_p": 1,
            "seed": 1,
            "ignore_eos": True,
            "add_special_tokens": False,
            "truncate_prompt_tokens": None,
            "return_token_ids": True,
        },
        "prompt_build_manifest": build_manifest,
    }
    if args.build_only:
        base_result.update({"status": "BUILD_ONLY", "rows": []})
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(base_result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": "BUILD_ONLY", "rows": len(prompts)}))
        return 0

    oracle = oracle_rows(args.oracle)
    rows: list[dict[str, Any]] = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {**base_result, "status": "RUNNING", "rows": rows},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    for index, (case, prompt_ids, metadata, max_tokens, row_kind) in enumerate(prompts):
        before = metric_snapshot(args.base_url, args.timeout)
        request_id = re.sub(r"[^A-Za-z0-9_.:-]", "-", f"laguna-lc-{index:02d}-{case['id']}")
        row = post_stream(
            base_url=args.base_url,
            model=args.model,
            prompt_ids=prompt_ids,
            max_tokens=max_tokens,
            timeout=args.timeout,
            request_id=request_id,
        )
        after = metric_snapshot(args.base_url, args.timeout)
        deltas = metric_delta(before, after)
        usage = row.get("usage") or {}
        details = usage.get("prompt_tokens_details") or {}
        expected = expected_json(case)
        row.update(
            {
                "case_id": case["id"],
                "row_kind": row_kind,
                "max_tokens": max_tokens,
                **metadata,
                "cached_tokens": details.get("cached_tokens"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "output_token_ids_sha256": token_hash(row["token_ids"]),
                "retrieval": validate_json(row["text"], expected),
                "prometheus_delta": deltas,
            }
        )
        prefill_s = deltas[f"{PREFILL_TIME}_sum"]
        prefill_tokens = deltas[f"{PREFILL_TOKENS}_sum"]
        row["prefill_tok_s_prometheus"] = (
            prefill_tokens / prefill_s if prefill_s > 0 else None
        )
        row["timing"] = timing_metrics(row)
        drafted = deltas[SPEC_DRAFT_TOKENS]
        accepted = deltas[SPEC_ACCEPTED]
        row["spec_decode"] = {
            "drafts": deltas[SPEC_DRAFTS],
            "draft_tokens": drafted,
            "accepted_tokens": accepted,
            "acceptance_rate": accepted / drafted if drafted > 0 else None,
        }
        oracle_row = oracle.get(case["id"])
        row["oracle"] = {
            "tested": oracle_row is not None,
            "prompt_hash_equal": (
                None
                if oracle_row is None
                else metadata["prompt_token_ids_sha256"]
                == oracle_row.get("prompt_token_ids_sha256")
            ),
            "token_ids_equal": (
                None if oracle_row is None else row["token_ids"] == oracle_row.get("token_ids")
            ),
            "text_hash_equal": (
                None
                if oracle_row is None
                else row["text_sha256"] == oracle_row.get("text_sha256")
            ),
        }
        row["checks"] = {
            "prompt_length_exact": usage.get("prompt_tokens") == len(prompt_ids),
            "returned_prompt_ids_exact": row["prompt_token_ids_returned"] == prompt_ids,
            "cache_zero": details.get("cached_tokens") == 0,
            "completion_length_exact": usage.get("completion_tokens") == max_tokens,
            "stream_token_ids_exact": len(row["token_ids"]) == max_tokens,
            "finish_reason_length": row["finish_reason"] == "length",
            "retrieval_pass": row["retrieval"]["passed"],
            "prefill_metric_count_one": deltas[f"{PREFILL_TIME}_count"] == 1,
            "prefill_token_metric_count_one": deltas[f"{PREFILL_TOKENS}_count"] == 1,
            "prefill_metric_tokens_exact": prefill_tokens == len(prompt_ids),
            "decode_metric_count_one": deltas[f"{DECODE_TIME}_count"] == 1,
            "first_100_timed": (
                row_kind == "sentinel"
                or row["timing"]["conventional_99_interval_first_100_tok_s"]
                is not None
            ),
            "oracle_exact_if_requested": (
                args.oracle is None
                or (
                    row["oracle"]["prompt_hash_equal"]
                    and row["oracle"]["token_ids_equal"]
                    and row["oracle"]["text_hash_equal"]
                )
            ),
        }
        row["passed"] = all(row["checks"].values())
        rows.append(row)
        args.out.write_text(
            json.dumps(
                {**base_result, "status": "RUNNING", "rows": rows},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        print(
            json.dumps(
                {
                    "case_id": case["id"],
                    "kind": row_kind,
                    "passed": row["passed"],
                    "prompt_tokens": row["prompt_tokens"],
                    "prefill_tok_s": row["prefill_tok_s_prometheus"],
                    "decode_tok_s": row["timing"][
                        "conventional_99_interval_first_100_tok_s"
                    ],
                    "acceptance_rate": row["spec_decode"]["acceptance_rate"],
                },
                sort_keys=True,
            ),
            flush=True,
        )

    long_rows = [row for row in rows if row["row_kind"] == "long"]
    summary = {
        "rows": len(rows),
        "long_rows": len(long_rows),
        "sentinel_rows": len(rows) - len(long_rows),
        "intrinsic_pass_all": all(row["passed"] for row in rows),
        "oracle_requested": args.oracle is not None,
        "oracle_exact_all": (
            args.oracle is not None
            and all(
                row["oracle"]["token_ids_equal"]
                and row["oracle"]["text_hash_equal"]
                for row in rows
            )
        ),
        "prefill_tok_s_prometheus": stats(
            [
                float(row["prefill_tok_s_prometheus"])
                for row in long_rows
                if isinstance(row.get("prefill_tok_s_prometheus"), (int, float))
            ]
        ),
        "decode_tok_s_99_interval_first_100": stats(
            [
                float(row["timing"]["conventional_99_interval_first_100_tok_s"])
                for row in long_rows
                if isinstance(
                    row["timing"].get(
                        "conventional_99_interval_first_100_tok_s"
                    ),
                    (int, float),
                )
            ]
        ),
        "cached_tokens_all_zero": all(row["cached_tokens"] == 0 for row in rows),
        "prompts_unique": len(
            {row["prompt_token_ids_sha256"] for row in rows}
        ) == len(rows),
    }
    status = (
        "PASS_ORACLE_EXACT"
        if summary["intrinsic_pass_all"] and summary["oracle_exact_all"]
        else "PASS_BASELINE_ORACLE_NOT_TESTED"
        if summary["intrinsic_pass_all"] and args.oracle is None
        else "FAIL"
    )
    result = {**base_result, "status": status, "summary": summary, "rows": rows}
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "summary": summary}, sort_keys=True))
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
