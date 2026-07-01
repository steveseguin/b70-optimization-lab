#!/usr/bin/env python3
"""Probe vLLM streaming-input continuation as a resident verifier path.

The prior rolling verifier probe re-prefilled every accepted output prefix and
found drift versus the accepted incremental decoder. This script tests the next
candidate: a single vLLM streaming-input session whose prompt is extended one
accepted token at a time. That should reuse resident prefix state instead of
rebuilding the full prefix through prefill for every checked token.

This is not a production server and not a speed benchmark. Run it only during a
controlled maintenance window or on isolated devices, because it starts its own
vLLM engine by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import time
from pathlib import Path
from typing import Any


DEFAULT_MODEL = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118"
)


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


def load_cases(path: Path, limit_cases: int | None) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path} has no non-empty cases list")
    selected = cases[:limit_cases] if limit_cases else cases
    for case in selected:
        if "prompt_token_ids" not in case or "output_token_ids" not in case:
            raise ValueError(
                "baseline cases must contain prompt_token_ids and output_token_ids"
            )
    return selected


def serialize_logprob_steps(logprobs: Any) -> list[list[dict[str, Any]] | None] | None:
    if logprobs is None:
        return None
    serialized: list[list[dict[str, Any]] | None] = []
    for step in logprobs:
        if step is None:
            serialized.append(None)
            continue
        entries: list[dict[str, Any]] = []
        for token_id, item in step.items():
            record: dict[str, Any] = {"token_id": int(token_id)}
            for attr in ("logprob", "rank", "decoded_token"):
                if not hasattr(item, attr):
                    continue
                value = getattr(item, attr)
                if attr == "logprob" and value is not None:
                    value = float(value)
                    if not math.isfinite(value):
                        record["logprob_nonfinite"] = str(value)
                        value = None
                record[attr] = value
            entries.append(record)
        entries.sort(key=lambda entry: entry.get("rank") or 10**9)
        serialized.append(entries)
    return serialized


def logprob_entry(
    entries: list[dict[str, Any]] | None,
    token_id: int,
) -> dict[str, Any] | None:
    if not entries:
        return None
    for entry in entries:
        if int(entry.get("token_id", -1)) == int(token_id):
            return entry
    return None


async def streaming_chunks(
    *,
    initial_prompt_ids: list[int],
    feed_queue: "asyncio.Queue[list[int] | None]",
    sampling_params: Any,
) -> Any:
    from vllm.engine.protocol import StreamingInput
    from vllm.inputs import TokensPrompt

    yield StreamingInput(
        prompt=TokensPrompt(prompt_token_ids=initial_prompt_ids),
        sampling_params=sampling_params,
    )

    while True:
        chunk = await feed_queue.get()
        if chunk is None:
            return
        yield StreamingInput(
            prompt=TokensPrompt(prompt_token_ids=chunk),
            sampling_params=sampling_params,
        )


async def probe_case(
    *,
    engine: Any,
    case: dict[str, Any],
    max_tokens: int,
    seed: int,
    request_id_prefix: str,
    sampling_params: Any,
    stop_on_first_mismatch: bool,
) -> dict[str, Any]:
    feed_queue: asyncio.Queue[list[int] | None] = asyncio.Queue()
    prompt_ids = [int(value) for value in case["prompt_token_ids"]]
    output_ids = [int(value) for value in case["output_token_ids"]]
    limit = min(max_tokens, len(output_ids))
    case_name = str(case.get("name") or "unnamed_case")
    request_id = f"{request_id_prefix}-{case_name}".replace("_", "-").replace(" ", "-")

    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    position = 0
    result_gen = engine.generate(
        prompt=streaming_chunks(
            initial_prompt_ids=prompt_ids,
            feed_queue=feed_queue,
            sampling_params=sampling_params,
        ),
        sampling_params=sampling_params,
        request_id=request_id,
    )

    try:
        async for output in result_gen:
            outputs = getattr(output, "outputs", None)
            if not outputs:
                if getattr(output, "finished", False):
                    break
                continue
            token_ids = list(getattr(outputs[0], "token_ids", []) or [])
            if not token_ids:
                if getattr(output, "finished", False):
                    break
                continue

            serialized_logprobs = serialize_logprob_steps(
                getattr(outputs[0], "logprobs", None)
            )

            for token_index, generated_token_id in enumerate(token_ids):
                if position >= limit:
                    await feed_queue.put(None)
                    break

                expected_token_id = int(output_ids[position])
                now = time.perf_counter()
                match = int(generated_token_id) == expected_token_id
                step_logprobs = (
                    serialized_logprobs[token_index]
                    if serialized_logprobs is not None
                    and token_index < len(serialized_logprobs)
                    else None
                )
                record: dict[str, Any] = {
                    "case_name": case_name,
                    "request_id": request_id,
                    "position": position,
                    "expected_token_id": expected_token_id,
                    "generated_token_id": int(generated_token_id),
                    "match": match,
                    "elapsed_ms_since_case_start": (now - started) * 1000.0,
                }
                if step_logprobs is not None:
                    record["top_logprobs"] = step_logprobs
                    record["expected_logprob_entry"] = logprob_entry(
                        step_logprobs,
                        expected_token_id,
                    )
                    record["generated_logprob_entry"] = logprob_entry(
                        step_logprobs,
                        int(generated_token_id),
                    )
                    record["top_logprob_entry"] = (
                        step_logprobs[0] if step_logprobs else None
                    )
                records.append(record)

                position += 1
                if position >= limit or (not match and stop_on_first_mismatch):
                    await feed_queue.put(None)
                    break

                # Feed the accepted baseline token, not the generated token.
                # The streaming-input session discards the final sampled token
                # from the previous chunk and then appends this prompt chunk.
                await feed_queue.put([expected_token_id])

            if position >= limit or (
                records and not records[-1]["match"] and stop_on_first_mismatch
            ):
                break
    finally:
        await feed_queue.put(None)
        close = getattr(result_gen, "aclose", None)
        if close is not None:
            await close()

    elapsed_s = time.perf_counter() - started
    checked = len(records)
    matched = sum(1 for row in records if row["match"])
    first_mismatch = next((row for row in records if not row["match"]), None)
    elapsed_ms = [float(row["elapsed_ms_since_case_start"]) for row in records]
    return {
        "case_name": case_name,
        "seed": seed,
        "checked_tokens": checked,
        "matched_tokens": matched,
        "all_matched": checked == matched,
        "elapsed_s": elapsed_s,
        "streaming_session_tok_s": checked / elapsed_s if elapsed_s > 0 else None,
        "elapsed_ms_since_case_start": summarize(elapsed_ms),
        "p90_elapsed_ms_since_case_start": percentile(elapsed_ms, 0.9),
        "first_mismatch": first_mismatch,
        "records": records,
    }


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Qwen3.6 Streaming-Input Verifier Probe")
    lines.append("")
    lines.append(
        "This probe starts an internal vLLM streaming-input session and feeds "
        "accepted baseline tokens back one at a time."
    )
    lines.append("")
    lines.append(f"- baseline JSON: `{data['baseline_json']}`")
    lines.append(f"- model: `{data['model']}`")
    lines.append(f"- tensor parallel size: `{data['engine_args']['tensor_parallel_size']}`")
    lines.append(f"- max model len: `{data['engine_args']['max_model_len']}`")
    lines.append(f"- prefix caching: `{data['engine_args']['enable_prefix_caching']}`")
    lines.append(f"- seed: `{data['seed']}`")
    lines.append(f"- generated-token logprobs: `{data.get('logprobs')}`")
    lines.append(f"- max tokens per case: `{data['max_tokens_per_case']}`")
    lines.append(f"- preflight only: `{data['preflight_only']}`")
    lines.append(f"- all matched: `{data.get('all_matched')}`")
    lines.append("")
    if data["preflight_only"]:
        lines.append("Preflight only: no vLLM engine was started.")
        lines.append("")
    else:
        lines.append("| Case | Checked | Matched | First mismatch | Session tok/s |")
        lines.append("| --- | ---: | ---: | --- | ---: |")
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
            tok_s = row.get("streaming_session_tok_s")
            tok_s_text = "n/a" if tok_s is None else f"{tok_s:.2f}"
            lines.append(
                f"| `{row['case_name']}` | {row['checked_tokens']} | "
                f"{row['matched_tokens']} | {first_text} | {tok_s_text} |"
            )
        lines.append("")
    lines.append("Interpretation:")
    lines.append("")
    lines.append(
        "- If this aligns while re-prefill drifted, a resident-KV sidecar "
        "remains a credible verifier design."
    )
    lines.append(
        "- If this drifts too, move directly to in-engine copy-on-write "
        "request/KV forking."
    )
    lines.append(
        "- Throughput here includes harness overhead and should not be used as "
        "a production speed claim."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    cases = load_cases(args.baseline_json, args.limit_cases)

    engine_args_payload = {
        "model": args.model,
        "tokenizer": args.tokenizer or args.model,
        "trust_remote_code": True,
        "dtype": args.dtype,
        "kv_cache_dtype": args.kv_cache_dtype,
        "quantization": args.quantization,
        "tensor_parallel_size": args.tensor_parallel_size,
        "distributed_executor_backend": args.distributed_executor_backend,
        "max_model_len": args.max_model_len,
        "max_num_batched_tokens": args.max_num_batched_tokens,
        "max_num_seqs": args.max_num_seqs,
        "gpu_memory_utilization": args.gpu_memory_utilization,
        "enable_prefix_caching": args.enable_prefix_caching,
        "language_model_only": args.language_model_only,
        "generation_config": args.generation_config,
        "disable_log_stats": True,
        "enforce_eager": args.enforce_eager,
        "compilation_config": json.loads(args.compilation_config_json),
    }

    output: dict[str, Any] = {
        "baseline_json": str(args.baseline_json),
        "model": args.model,
        "seed": args.seed,
        "logprobs": args.logprobs,
        "max_tokens_per_case": args.max_tokens_per_case,
        "limit_cases": args.limit_cases,
        "preflight_only": args.preflight_only,
        "engine_args": engine_args_payload,
        "environment": {
            key: os.environ.get(key)
            for key in (
                "ONEAPI_DEVICE_SELECTOR",
                "ZE_AFFINITY_MASK",
                "CCL_ATL_TRANSPORT",
                "CCL_TOPO_P2P_ACCESS",
                "VLLM_XPU_ENABLE_XPU_GRAPH",
                "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
                "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
            )
        },
        "cases_loaded": [
            {
                "name": case.get("name"),
                "prompt_tokens": len(case["prompt_token_ids"]),
                "output_tokens": len(case["output_token_ids"]),
            }
            for case in cases
        ],
        "summary": [],
        "records": [],
        "all_matched": None,
    }

    if args.preflight_only:
        return output

    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.sampling_params import RequestOutputKind, SamplingParams
    from vllm.v1.engine.async_llm import AsyncLLM

    engine_args = AsyncEngineArgs(**engine_args_payload)
    engine = AsyncLLM.from_engine_args(engine_args)
    sampling_params = SamplingParams(
        temperature=0,
        top_p=1.0,
        top_k=0,
        max_tokens=1,
        logprobs=args.logprobs,
        seed=args.seed,
        ignore_eos=args.ignore_eos,
        detokenize=False,
        output_kind=RequestOutputKind.DELTA,
        skip_clone=True,
    )

    try:
        for case in cases:
            result = await probe_case(
                engine=engine,
                case=case,
                max_tokens=args.max_tokens_per_case,
                seed=args.seed,
                request_id_prefix=args.request_id_prefix,
                sampling_params=sampling_params,
                stop_on_first_mismatch=args.stop_on_first_mismatch,
            )
            records = result.pop("records")
            output["summary"].append(result)
            output["records"].extend(records)
            if args.stop_on_first_mismatch and not result["all_matched"]:
                break
    finally:
        shutdown = getattr(engine, "shutdown", None)
        if shutdown is not None:
            shutdown()

    output["all_matched"] = all(row["all_matched"] for row in output["summary"])
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--tokenizer", default=None)
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--distributed-executor-backend", default="mp")
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--max-num-batched-tokens", type=int, default=8192)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.95)
    parser.add_argument("--dtype", default="auto")
    parser.add_argument("--kv-cache-dtype", default="auto")
    parser.add_argument("--quantization", default="quark")
    parser.add_argument("--generation-config", default="vllm")
    parser.add_argument(
        "--compilation-config-json",
        default='{"cudagraph_mode":"PIECEWISE"}',
    )
    parser.add_argument("--enable-prefix-caching", action="store_true")
    parser.add_argument("--no-language-model-only", dest="language_model_only",
                        action="store_false")
    parser.set_defaults(language_model_only=True)
    parser.add_argument("--enforce-eager", action="store_true")
    parser.add_argument("--ignore-eos", action="store_true")
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument(
        "--logprobs",
        type=int,
        default=None,
        help="Record generated-token top logprobs for mismatch diagnostics.",
    )
    parser.add_argument("--max-tokens-per-case", type=int, default=32)
    parser.add_argument("--limit-cases", type=int, default=None)
    parser.add_argument("--stop-on-first-mismatch", action="store_true")
    parser.add_argument("--request-id-prefix", default="qwen36-streamver")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate inputs/import-free config without starting a vLLM engine.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(run_probe(args))
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown(args.output_md, result)
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_md": str(args.output_md),
                "preflight_only": result["preflight_only"],
                "all_matched": result["all_matched"],
                "case_count": len(result["cases_loaded"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
