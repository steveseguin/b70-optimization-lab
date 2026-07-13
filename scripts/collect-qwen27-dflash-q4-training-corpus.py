#!/usr/bin/env python3
"""Drive an exact-Q4 native DFlash target-feature capture session.

The native hook is intentionally outside this script.  Before sending any
request, the collector validates a server-written session manifest against the
prepared active-product plan.  A missing/mismatched hook therefore fails closed
without consuming prompts or producing mislabeled training data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Sequence


SESSION_SCHEMA = "qwen27_dflash_native_capture_session_v1"
TRACE_SCHEMA = "qwen27_dflash_native_target_trace_v1"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect no-thinking, linear greedy Q4 target features only after "
            "an exact native capture-session identity preflight."
        )
    )
    parser.add_argument("--plan", required=True)
    parser.add_argument("--session-manifest", required=True)
    parser.add_argument("--split", choices=("train", "heldout"), required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:19440")
    parser.add_argument("--model", default="qwen36-27b-mtp-gguf-q4_0")
    parser.add_argument("--max-tokens", type=int, default=160)
    parser.add_argument("--seed", type=int, default=20260713)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--trace-timeout-s", type=float, default=30.0)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_text(row: dict[str, Any]) -> str:
    if row.get("prompt"):
        return str(row["prompt"])
    return json.dumps(row.get("messages") or [], sort_keys=True)


def prompt_sha256(row: dict[str, Any]) -> str:
    return hashlib.sha256(prompt_text(row).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def validate_session(
    plan: dict[str, Any], session: dict[str, Any], session_path: Path
) -> Path:
    require_equal("session schema", session.get("schema"), SESSION_SCHEMA)
    active = plan["active_product"]
    runtime = active["runtime"]
    contract = plan["native_capture"]["required_server_contract"]
    require_equal(
        "target model sha256",
        session.get("target_model_sha256"),
        active["target_model_sha256"],
    )
    require_equal(
        "draft model sha256",
        session.get("draft_model_sha256"),
        active["draft_model_sha256"],
    )
    require_equal("runtime commit", session.get("runtime_commit"), runtime["commit"])
    require_equal(
        "runtime dirty patch sha256",
        session.get("runtime_dirty_patch_sha256"),
        runtime["dirty_patch_sha256"],
    )
    require_equal("reasoning", session.get("reasoning"), "off")
    require_equal("capture mode", session.get("capture_mode"), "linear_target_no_speculation")
    require_equal("spec draft n_max", session.get("spec_draft_n_max"), 0)
    require_equal("spec draft n_min", session.get("spec_draft_n_min"), 0)
    require_equal("spec draft p_min", session.get("spec_draft_p_min"), 0.0)
    require_equal("draft KV K", session.get("spec_draft_type_k"), "f16")
    require_equal("draft KV V", session.get("spec_draft_type_v"), "f16")
    require_equal(
        "target layer input IDs",
        session.get("target_layer_input_ids"),
        contract["target_layer_input_ids"],
    )
    if not session.get("capture_hook_active"):
        raise ValueError("native session says capture_hook_active is false")
    capture_dir = Path(str(session.get("capture_dir") or "")).expanduser()
    if not capture_dir.is_absolute():
        capture_dir = (session_path.parent / capture_dir).resolve()
    if not capture_dir.is_dir():
        raise FileNotFoundError(f"capture directory does not exist: {capture_dir}")
    return capture_dir


def load_selected_prompts(
    plan: dict[str, Any], split: str, limit: int
) -> list[dict[str, Any]]:
    suite_path = Path(plan["prompt_policy"]["suite"])
    suite = load_json(suite_path)
    rows = suite.get("prompts")
    if not isinstance(rows, list):
        raise ValueError(f"{suite_path}: missing prompts")
    split_hashes = set(
        plan["prompt_policy"]["split"][f"{split}_prompt_sha256s"]
    )
    selected = [row for row in rows if prompt_sha256(row) in split_hashes]
    if len(selected) != len(split_hashes):
        raise ValueError(
            f"{split}: selected {len(selected)} prompts for {len(split_hashes)} hashes"
        )
    if limit > 0:
        selected = selected[:limit]
    return selected


def request_generation(
    *,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    seed: int,
    request_id: str,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "seed": seed,
        "stream": False,
        "return_tokens": True,
        "cache_prompt": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=max(120, max_tokens * 8)) as response:
        response_payload = json.loads(response.read())
    elapsed = time.perf_counter() - started
    choices = response_payload.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    text = str(message.get("content") or message.get("reasoning_content") or "")
    token_ids = choice.get("token_ids")
    if not isinstance(token_ids, list):
        token_ids = choice.get("tokens")
    if not isinstance(token_ids, list):
        token_ids = []
    return {
        "response_id": response_payload.get("id"),
        "elapsed_s": elapsed,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_preview": text[:160],
        "response_token_ids": token_ids,
        "usage": response_payload.get("usage") or {},
    }


def wait_for_trace(
    capture_dir: Path, ordinal: int, timeout_s: float
) -> tuple[Path, dict[str, Any]]:
    trace_path = capture_dir / f"request-{ordinal:06d}.json"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if trace_path.is_file():
            try:
                trace = load_json(trace_path)
            except (json.JSONDecodeError, OSError):
                time.sleep(0.1)
                continue
            if trace.get("complete") is True:
                return trace_path, trace
        time.sleep(0.1)
    raise TimeoutError(f"native capture did not publish {trace_path}")


def validate_trace(
    *,
    trace: dict[str, Any],
    trace_path: Path,
    plan: dict[str, Any],
    prompt_hash: str,
) -> dict[str, Any]:
    active = plan["active_product"]
    require_equal("trace schema", trace.get("schema"), TRACE_SCHEMA)
    require_equal("trace prompt sha256", trace.get("prompt_sha256"), prompt_hash)
    require_equal(
        "trace target sha256",
        trace.get("target_model_sha256"),
        active["target_model_sha256"],
    )
    require_equal(
        "trace target layers",
        trace.get("target_layer_input_ids"),
        plan["native_capture"]["required_server_contract"][
            "target_layer_input_ids"
        ],
    )
    shape = trace.get("aux_hidden_states_shape")
    if not (
        isinstance(shape, list)
        and len(shape) == 3
        and shape[0] > 0
        and shape[1:] == [5, 5120]
    ):
        raise ValueError(f"invalid aux_hidden_states_shape: {shape!r}")
    row_count = int(shape[0])
    for key in ("input_token_ids", "sampled_next_token_ids", "positions"):
        values = trace.get(key)
        if not isinstance(values, list) or len(values) != row_count:
            raise ValueError(f"trace {key} does not align to {row_count} rows")
    payload_path = Path(str(trace.get("payload_path") or ""))
    if not payload_path.is_absolute():
        payload_path = (trace_path.parent / payload_path).resolve()
    if not payload_path.is_file():
        raise FileNotFoundError(f"missing trace payload: {payload_path}")
    actual_sha256 = sha256_file(payload_path)
    require_equal("trace payload sha256", actual_sha256, trace.get("payload_sha256"))
    return {
        "trace": str(trace_path.resolve()),
        "payload": str(payload_path),
        "payload_sha256": actual_sha256,
        "rows": row_count,
        "num_prompt_tokens": trace.get("num_prompt_tokens"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_tokens < 16:
        raise ValueError("--max-tokens must be at least 16")
    if args.limit < 0:
        raise ValueError("--limit must be non-negative")
    plan_path = Path(args.plan).expanduser().resolve()
    session_path = Path(args.session_manifest).expanduser().resolve()
    plan = load_json(plan_path)
    require_equal(
        "plan schema",
        plan.get("schema"),
        "qwen27_dflash_q4_adaptation_capture_plan_v1",
    )
    session = load_json(session_path)
    capture_dir = validate_session(plan, session, session_path)
    prompts = load_selected_prompts(plan, args.split, args.limit)
    records: list[dict[str, Any]] = []
    capture_start_ordinal = int(session.get("next_request_ordinal", 0))

    for offset, row in enumerate(prompts):
        ordinal = capture_start_ordinal + offset
        prompt_hash = prompt_sha256(row)
        prompt_id = str(row.get("id") or f"prompt-{offset:04d}")
        request_id = f"qwen27-dflash-q4-{args.split}-{ordinal:06d}-{prompt_id}"
        response = request_generation(
            base_url=args.base_url,
            model=args.model,
            prompt=prompt_text(row),
            max_tokens=args.max_tokens,
            seed=args.seed + ordinal,
            request_id=request_id,
        )
        trace_path, trace = wait_for_trace(
            capture_dir, ordinal, args.trace_timeout_s
        )
        trace_record = validate_trace(
            trace=trace,
            trace_path=trace_path,
            plan=plan,
            prompt_hash=prompt_hash,
        )
        record = {
            "ordinal": ordinal,
            "prompt_id": prompt_id,
            "family": row.get("family"),
            "task": row.get("task"),
            "variant": row.get("variant"),
            "prompt_sha256": prompt_hash,
            "request_id": request_id,
            **response,
            **trace_record,
        }
        records.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)

    result = {
        "schema": "qwen27_dflash_q4_native_collector_summary_v1",
        "classification": (
            "diagnostic_training_corpus_capture_not_endpoint_not_localmaxxing"
        ),
        "plan": str(plan_path),
        "session_manifest": str(session_path),
        "split": args.split,
        "base_url": args.base_url,
        "model": args.model,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "capture_start_ordinal": capture_start_ordinal,
        "requests": len(records),
        "records": records,
        "localmaxxing_eligible": False,
    }
    output_path = Path(args.out).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output_path.write_text(rendered, encoding="utf-8")
    print(f"wrote={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
