#!/usr/bin/env python3
"""Measure a live vLLM OpenAI-compatible endpoint.

This records endpoint-facing TTFT, output throughput, total throughput, vLLM
Prometheus metric deltas, and a conservative prefill lower-bound. It does not
change server settings and is intended for LocalMaxxing-quality reporting.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


METRIC_RE = re.compile(r"^([A-Za-z_:][A-Za-z0-9_:]*)(?:\{[^}]*\})?\s+([-+0-9.eE]+)$")


def get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_metric_sums(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        match = METRIC_RE.match(line)
        if not match:
            continue
        name, value = match.groups()
        out[name] = out.get(name, 0.0) + float(value)
    return out


def metric_delta(before: dict[str, float], after: dict[str, float], name: str) -> float:
    return after.get(name, 0.0) - before.get(name, 0.0)


def histogram_delta(
    before: dict[str, float], after: dict[str, float], name: str
) -> dict[str, float | None]:
    count = metric_delta(before, after, f"{name}_count")
    total = metric_delta(before, after, f"{name}_sum")
    return {
        "count": count,
        "sum": total,
        "mean": None if count <= 0 else total / count,
    }


def histogram_mean_ms(delta: dict[str, float | None]) -> float | None:
    mean = delta.get("mean")
    return None if mean is None else float(mean) * 1000.0


def make_text_prompt(tokenizer: Any, target_tokens: int) -> str:
    seed = (
        "Local Intel XPU benchmark prompt. "
        "The assistant should continue with concise technical text. "
    )
    text = seed
    while len(tokenizer.encode(text, add_special_tokens=False)) < target_tokens + 8:
        text += seed
    ids = tokenizer.encode(text, add_special_tokens=False)[:target_tokens]
    return tokenizer.decode(ids, skip_special_tokens=True)


def fit_prompt_to_tokens(
    tokenizer: Any,
    *,
    prefix: str,
    filler: str,
    suffix: str,
    target_tokens: int,
) -> str:
    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    suffix_ids = tokenizer.encode(suffix, add_special_tokens=False)
    filler_ids = tokenizer.encode(filler, add_special_tokens=False)
    if not filler_ids:
        raise ValueError("filler produced no tokens")

    body_budget = max(0, target_tokens - len(prefix_ids) - len(suffix_ids))
    body_ids = (filler_ids * ((body_budget + len(filler_ids) - 1) // len(filler_ids)))[:body_budget]
    ids = prefix_ids + body_ids + suffix_ids
    if len(ids) > target_tokens:
        ids = ids[:target_tokens]
    return tokenizer.decode(ids, skip_special_tokens=True)


def make_preset_prompt(tokenizer: Any, preset: str, target_tokens: int) -> str:
    if preset == "natural-chat":
        return fit_prompt_to_tokens(
            tokenizer,
            prefix=(
                "You are helping tune an Intel XPU inference server. "
                "Write a concise engineering analysis with concrete next steps.\n\n"
            ),
            filler=(
                "Recent observations include stable baseline decoding, prompt-sensitive "
                "speculative acceptance, graph capture bucket sensitivity, and the need "
                "to preserve exact output quality while improving single-request speed. "
            ),
            suffix=(
                "\n\nQuestion: summarize the likely bottlenecks and propose an ordered "
                "plan. Keep the answer technical and avoid marketing language. Write at "
                "least eight dense numbered paragraphs.\n"
            ),
            target_tokens=target_tokens,
        )
    if preset == "code":
        return fit_prompt_to_tokens(
            tokenizer,
            prefix=(
                "Review the following Python service code for latency bugs and reliability "
                "risks. Return specific findings first, then a short patch plan.\n\n"
            ),
            filler=(
                "def handle_request(req, backend):\n"
                "    start = time.perf_counter()\n"
                "    payload = normalize(req.json())\n"
                "    if payload.get('stream'):\n"
                "        for chunk in backend.generate(payload):\n"
                "            metrics.observe(time.perf_counter() - start)\n"
                "            yield encode_sse(chunk)\n"
                "    else:\n"
                "        result = backend.generate_once(payload)\n"
                "        metrics.observe(time.perf_counter() - start)\n"
                "        return result\n\n"
            ),
            suffix=(
                "\nFocus on request lifecycle overhead, streaming behavior, metrics "
                "placement, and failure handling. Do not rewrite unrelated code. Provide "
                "at least ten concrete findings and a detailed patch plan.\n"
            ),
            target_tokens=target_tokens,
        )
    if preset == "structured":
        return fit_prompt_to_tokens(
            tokenizer,
            prefix=(
                "Create compact JSON only. The JSON must contain keys summary, "
                "risks, experiments, and production_gate.\n\n"
            ),
            filler=(
                "Input note: n-gram speculation can improve repeated continuations but "
                "must be disabled if repeat canaries or structured-output hashes diverge. "
            ),
            suffix=(
                "\nReturn one valid JSON object. Include at least twelve experiment "
                "objects, each with name, expected_effect, risk, and quality_gate. Do "
                "not include markdown fences or prose.\n"
            ),
            target_tokens=target_tokens,
        )
    if preset == "math-reasoning":
        return fit_prompt_to_tokens(
            tokenizer,
            prefix=(
                "Solve the operational planning problem. Explain the calculation briefly, "
                "then give the final number.\n\n"
            ),
            filler=(
                "A server processes 48 independent client sessions. Each session reserves "
                "a 32K token cache window, but the active decode stream uses only one "
                "request at a time. Measurements should distinguish prefill, decode, "
                "and total throughput. "
            ),
            suffix=(
                "\nIf decode throughput is 99 tokens/s baseline and a candidate reports "
                "105 tokens/s, what is the percentage increase? Answer with the formula "
                "and the percentage, then discuss why that gain is not enough for a "
                "200 tokens/s target. Include a compact table of follow-up experiments.\n"
            ),
            target_tokens=target_tokens,
        )
    if preset == "repetitive":
        return make_text_prompt(tokenizer, target_tokens)
    raise ValueError(f"unknown prompt preset: {preset}")


def make_vllm_random_prompt(
    tokenizer: Any,
    target_tokens: int,
    output_tokens: int,
    *,
    seed: int,
    prefix_len: int,
) -> str:
    try:
        from vllm.benchmarks.datasets import RandomDataset
    except ImportError as exc:
        raise RuntimeError(
            "--prompt-kind vllm-random requires vLLM to be importable in this Python environment"
        ) from exc

    dataset = RandomDataset(random_seed=seed)
    sample = dataset.sample(
        tokenizer=tokenizer,
        num_requests=1,
        prefix_len=prefix_len,
        range_ratio=0.0,
        input_len=target_tokens,
        output_len=output_tokens,
    )[0]
    return sample.prompt


def make_prompt(
    tokenizer: Any,
    *,
    prompt_kind: str,
    prompt_preset: str,
    prompt_file: str | None,
    target_tokens: int,
    output_tokens: int,
    seed: int,
    random_prefix_len: int,
) -> str:
    if prompt_file:
        return Path(prompt_file).read_text()
    if prompt_kind == "text":
        return make_text_prompt(tokenizer, target_tokens)
    if prompt_kind == "preset":
        return make_preset_prompt(tokenizer, prompt_preset, target_tokens)
    if prompt_kind == "vllm-random":
        return make_vllm_random_prompt(
            tokenizer,
            target_tokens,
            output_tokens,
            seed=seed,
            prefix_len=random_prefix_len,
        )
    raise ValueError(f"unknown prompt kind: {prompt_kind}")


def xpu_vram_mib() -> dict[str, float]:
    values: dict[str, float] = {}
    for device in range(8):
        try:
            proc = subprocess.run(
                ["xpu-smi", "dump", "-d", str(device), "-m", "18", "-n", "1"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            break
        if proc.returncode != 0:
            if device == 0:
                values["error"] = float("nan")
            break
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        try:
            values[str(device)] = float(lines[-1].split(",")[-1].strip())
        except ValueError:
            continue
    return values


def request_completion(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    *,
    stream: bool,
    seed: int,
    ignore_eos: bool,
    request_extra: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": stream,
        "seed": seed,
    }
    if ignore_eos:
        payload["ignore_eos"] = True
    if stream:
        payload["stream_options"] = {"include_usage": True}
    payload.update(request_extra)
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[str] = []
    usage = None
    t0 = time.perf_counter()
    first = None
    first_chunk_text = ""
    streamed_text_chunks = 0
    request_id = None
    with urllib.request.urlopen(req, timeout=max(120, max_tokens * 5)) as resp:
        if not stream:
            data = json.loads(resp.read())
            choices = data.get("choices") or []
            text = choices[0].get("text") if choices else ""
            chunks.append(text or "")
            usage = data.get("usage")
            return {
                "request_id": data.get("id"),
                "text": "".join(chunks),
                "usage": usage,
                "elapsed_s": time.perf_counter() - t0,
                "ttft_s": None,
                "generation_wall_s_after_first_chunk": None,
                "first_chunk_text": "",
                "streamed_text_chunks": None,
            }
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("id"):
                request_id = event["id"]
            if event.get("usage"):
                usage = event["usage"]
            choices = event.get("choices") or []
            if choices:
                text = choices[0].get("text") or ""
                if text and first is None:
                    first = time.perf_counter()
                    first_chunk_text = text
                if text:
                    streamed_text_chunks += 1
                chunks.append(text)
    t1 = time.perf_counter()
    return {
        "request_id": request_id,
        "text": "".join(chunks),
        "usage": usage,
        "elapsed_s": t1 - t0,
        "ttft_s": None if first is None else first - t0,
        "generation_wall_s_after_first_chunk": None if first is None else t1 - first,
        "first_chunk_text": first_chunk_text,
        "streamed_text_chunks": streamed_text_chunks,
    }


def request_chat_completion(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    *,
    stream: bool,
    seed: int,
    ignore_eos: bool,
    request_extra: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": stream,
        "seed": seed,
    }
    if ignore_eos:
        payload["ignore_eos"] = True
    if stream:
        payload["stream_options"] = {"include_usage": True}
    payload.update(request_extra)
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chunks: list[str] = []
    usage = None
    t0 = time.perf_counter()
    first = None
    first_chunk_text = ""
    streamed_text_chunks = 0
    request_id = None
    with urllib.request.urlopen(req, timeout=max(120, max_tokens * 5)) as resp:
        if not stream:
            data = json.loads(resp.read())
            choices = data.get("choices") or []
            message = choices[0].get("message") if choices else {}
            text = (message or {}).get("content") or (message or {}).get("reasoning") or ""
            chunks.append(text)
            usage = data.get("usage")
            return {
                "request_id": data.get("id"),
                "text": "".join(chunks),
                "usage": usage,
                "elapsed_s": time.perf_counter() - t0,
                "ttft_s": None,
                "generation_wall_s_after_first_chunk": None,
                "first_chunk_text": "",
                "streamed_text_chunks": None,
            }
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            event = json.loads(data)
            if event.get("id"):
                request_id = event["id"]
            if event.get("usage"):
                usage = event["usage"]
            choices = event.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                text = delta.get("content") or delta.get("reasoning") or ""
                if text and first is None:
                    first = time.perf_counter()
                    first_chunk_text = text
                if text:
                    streamed_text_chunks += 1
                chunks.append(text)
    t1 = time.perf_counter()
    return {
        "request_id": request_id,
        "text": "".join(chunks),
        "usage": usage,
        "elapsed_s": t1 - t0,
        "ttft_s": None if first is None else first - t0,
        "generation_wall_s_after_first_chunk": None if first is None else t1 - first,
        "first_chunk_text": first_chunk_text,
        "streamed_text_chunks": streamed_text_chunks,
    }


def count_prompt_tokens(tokenizer: Any, prompt: str, endpoint: str) -> int:
    if endpoint == "chat":
        try:
            return len(
                tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    add_generation_prompt=True,
                    tokenize=True,
                )
            )
        except Exception:
            pass
    return len(tokenizer.encode(prompt, add_special_tokens=False))


def summarize_repeats(records: list[dict[str, Any]]) -> dict[str, Any]:
    def vals(key: str) -> list[float]:
        return [float(r[key]) for r in records if r.get(key) is not None]

    summary: dict[str, Any] = {}
    for key in [
        "tok_s_out_client_after_first_chunk",
        "tok_s_out_client_after_first_chunk_corrected",
        "tok_s_out_client_e2e",
        "tok_s_total_client",
        "ttft_ms_client",
        "ttft_ms_vllm_metrics",
        "tok_s_prefill_lower_bound_from_ttft",
        "e2e_ms_vllm_metrics",
        "queue_ms_vllm_histogram",
        "prefill_ms_vllm_histogram",
        "decode_ms_vllm_histogram",
        "decode_ms_per_generation_token_vllm_histogram",
        "inference_ms_vllm_histogram",
        "time_per_output_token_ms_vllm_histogram",
        "inter_token_ms_vllm_histogram",
        "iteration_tokens_per_step_vllm_histogram",
        "spec_decode_drafts",
        "spec_decode_draft_tokens",
        "spec_decode_accepted_tokens",
        "spec_decode_acceptance_fraction",
        "spec_decode_accepted_tokens_per_generation_token",
    ]:
        xs = vals(key)
        if xs:
            summary[key] = {
                "mean": statistics.mean(xs),
                "median": statistics.median(xs),
                "min": min(xs),
                "max": max(xs),
            }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=None, help="Served model name. Defaults to /v1/models[0].id.")
    parser.add_argument("--tokenizer", default="/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround")
    parser.add_argument("--prompt-tokens", type=int, default=510)
    parser.add_argument("--output-tokens", type=int, default=1536)
    parser.add_argument(
        "--prompt-kind",
        choices=["text", "preset", "vllm-random"],
        default="text",
        help="Prompt generator to use. vllm-random matches vLLM's random throughput dataset.",
    )
    parser.add_argument(
        "--prompt-preset",
        choices=["repetitive", "natural-chat", "code", "structured", "math-reasoning"],
        default="repetitive",
        help="Prompt preset used with --prompt-kind preset.",
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Use the exact contents of this file as the prompt, bypassing prompt generation.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--random-prefix-len", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--warmup-output-tokens", type=int, default=32)
    parser.add_argument(
        "--endpoint",
        choices=["completions", "chat"],
        default="completions",
        help="OpenAI-compatible endpoint to benchmark.",
    )
    parser.add_argument(
        "--mode",
        choices=["stream", "nonstream"],
        default="stream",
        help="Use SSE streaming or final-only /v1/completions responses.",
    )
    parser.add_argument(
        "--skip-vram",
        action="store_true",
        help="Skip xpu-smi VRAM sampling. Useful for tight profiling when xpu-smi dump is slow or wedged.",
    )
    parser.add_argument(
        "--include-full-text",
        action="store_true",
        help="Store the full generated text for output parity comparisons.",
    )
    parser.add_argument(
        "--ignore-eos",
        action="store_true",
        help="Force generation to the requested output token count for decode throughput measurements.",
    )
    parser.add_argument(
        "--request-extra-json",
        default="{}",
        help=(
            "JSON object merged into every request payload. Use for model-specific "
            "controls such as '{\"chat_template_kwargs\":{\"enable_thinking\":false}}'."
        ),
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    request_extra = json.loads(args.request_extra_json)
    if not isinstance(request_extra, dict):
        raise SystemExit("--request-extra-json must decode to a JSON object")

    models = get_json(f"{args.base_url.rstrip('/')}/v1/models")
    model = args.model or models["data"][0]["id"]
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    prompt = make_prompt(
        tokenizer,
        prompt_kind=args.prompt_kind,
        prompt_preset=args.prompt_preset,
        prompt_file=args.prompt_file,
        target_tokens=args.prompt_tokens,
        output_tokens=args.output_tokens,
        seed=args.seed,
        random_prefix_len=args.random_prefix_len,
    )
    prompt_tokens = count_prompt_tokens(tokenizer, prompt, args.endpoint)

    if args.warmup_output_tokens > 0:
        request_fn = request_chat_completion if args.endpoint == "chat" else request_completion
        request_fn(
            args.base_url,
            model,
            prompt,
            args.warmup_output_tokens,
            stream=args.mode == "stream",
            seed=args.seed - 1,
            ignore_eos=args.ignore_eos,
            request_extra=request_extra,
        )

    records: list[dict[str, Any]] = []
    vram_before = {} if args.skip_vram else xpu_vram_mib()
    peak_vram = dict(vram_before)
    for i in range(args.repeats):
        metrics_before = parse_metric_sums(get_text(f"{args.base_url.rstrip('/')}/metrics"))
        vram_pre = {} if args.skip_vram else xpu_vram_mib()
        request_fn = request_chat_completion if args.endpoint == "chat" else request_completion
        request_started_at_unix = time.time()
        result = request_fn(
            args.base_url,
            model,
            prompt,
            args.output_tokens,
            stream=args.mode == "stream",
            seed=args.seed,
            ignore_eos=args.ignore_eos,
            request_extra=request_extra,
        )
        request_finished_at_unix = time.time()
        vram_post = {} if args.skip_vram else xpu_vram_mib()
        metrics_after = parse_metric_sums(get_text(f"{args.base_url.rstrip('/')}/metrics"))

        text = result["text"]
        output_tokens = (
            int(result["usage"]["completion_tokens"])
            if result.get("usage") and result["usage"].get("completion_tokens") is not None
            else len(tokenizer.encode(text, add_special_tokens=False))
        )
        record_prompt_tokens = (
            int(result["usage"]["prompt_tokens"])
            if result.get("usage") and result["usage"].get("prompt_tokens") is not None
            else prompt_tokens
        )
        elapsed = float(result["elapsed_s"])
        after_first = result["generation_wall_s_after_first_chunk"]
        ttft_s = result["ttft_s"]
        first_chunk_tokens = (
            len(tokenizer.encode(result.get("first_chunk_text", ""), add_special_tokens=False))
            if result.get("first_chunk_text")
            else 0
        )

        prompt_delta = metric_delta(metrics_before, metrics_after, "vllm:prompt_tokens_total")
        gen_delta = metric_delta(metrics_before, metrics_after, "vllm:generation_tokens_total")
        spec_drafts_delta = metric_delta(
            metrics_before, metrics_after, "vllm:spec_decode_num_drafts_total"
        )
        spec_draft_tokens_delta = metric_delta(
            metrics_before, metrics_after, "vllm:spec_decode_num_draft_tokens_total"
        )
        spec_accepted_tokens_delta = metric_delta(
            metrics_before, metrics_after, "vllm:spec_decode_num_accepted_tokens_total"
        )
        ttft_count = metric_delta(
            metrics_before, metrics_after, "vllm:time_to_first_token_seconds_count"
        )
        ttft_sum = metric_delta(metrics_before, metrics_after, "vllm:time_to_first_token_seconds_sum")
        e2e_count = metric_delta(metrics_before, metrics_after, "vllm:e2e_request_latency_seconds_count")
        e2e_sum = metric_delta(metrics_before, metrics_after, "vllm:e2e_request_latency_seconds_sum")
        histogram_deltas = {
            name: histogram_delta(metrics_before, metrics_after, name)
            for name in [
                "vllm:request_queue_time_seconds",
                "vllm:request_prefill_time_seconds",
                "vllm:request_decode_time_seconds",
                "vllm:request_inference_time_seconds",
                "vllm:request_time_per_output_token_seconds",
                "vllm:inter_token_latency_seconds",
                "vllm:iteration_tokens_total",
            ]
        }
        decode_hist_sum = histogram_deltas["vllm:request_decode_time_seconds"].get("sum")

        for values in (vram_pre, vram_post):
            for key, value in values.items():
                if key not in peak_vram or value > peak_vram[key]:
                    peak_vram[key] = value

        record = {
                "repeat": i + 1,
                "request_id": result.get("request_id"),
                "request_started_at_unix": request_started_at_unix,
                "request_finished_at_unix": request_finished_at_unix,
                "prompt_tokens_client": record_prompt_tokens,
                "prompt_tokens_estimated_before_request": prompt_tokens,
                "output_tokens_client": output_tokens,
                "elapsed_s_client": elapsed,
                "ttft_ms_client": None if ttft_s is None else ttft_s * 1000,
                "tok_s_out_client_after_first_chunk": None
                if not after_first or after_first <= 0
                else output_tokens / after_first,
                "tok_s_out_client_after_first_chunk_corrected": None
                if not after_first or after_first <= 0
                else max(0, output_tokens - first_chunk_tokens) / after_first,
                "tok_s_out_client_e2e": output_tokens / elapsed,
                "tok_s_total_client": (record_prompt_tokens + output_tokens) / elapsed,
                "tok_s_prefill_lower_bound_from_ttft": None
                if not ttft_s or ttft_s <= 0
                else record_prompt_tokens / ttft_s,
                "vllm_metric_deltas": {
                    "prompt_tokens": prompt_delta,
                    "generation_tokens": gen_delta,
                    "spec_decode_drafts": spec_drafts_delta,
                    "spec_decode_draft_tokens": spec_draft_tokens_delta,
                    "spec_decode_accepted_tokens": spec_accepted_tokens_delta,
                    "ttft_count": ttft_count,
                    "ttft_sum_s": ttft_sum,
                    "e2e_count": e2e_count,
                    "e2e_sum_s": e2e_sum,
                },
                "vllm_histogram_deltas": histogram_deltas,
                "ttft_ms_vllm_metrics": None
                if ttft_count <= 0
                else (ttft_sum / ttft_count) * 1000,
                "e2e_ms_vllm_metrics": None if e2e_count <= 0 else (e2e_sum / e2e_count) * 1000,
                "queue_ms_vllm_histogram": histogram_mean_ms(
                    histogram_deltas["vllm:request_queue_time_seconds"]
                ),
                "prefill_ms_vllm_histogram": histogram_mean_ms(
                    histogram_deltas["vllm:request_prefill_time_seconds"]
                ),
                "decode_ms_vllm_histogram": histogram_mean_ms(
                    histogram_deltas["vllm:request_decode_time_seconds"]
                ),
                "decode_ms_per_generation_token_vllm_histogram": None
                if not decode_hist_sum or gen_delta <= 0
                else float(decode_hist_sum) * 1000.0 / gen_delta,
                "inference_ms_vllm_histogram": histogram_mean_ms(
                    histogram_deltas["vllm:request_inference_time_seconds"]
                ),
                "time_per_output_token_ms_vllm_histogram": histogram_mean_ms(
                    histogram_deltas["vllm:request_time_per_output_token_seconds"]
                ),
                "inter_token_ms_vllm_histogram": histogram_mean_ms(
                    histogram_deltas["vllm:inter_token_latency_seconds"]
                ),
                "iteration_tokens_per_step_vllm_histogram": (
                    histogram_deltas["vllm:iteration_tokens_total"].get("mean")
                ),
                "spec_decode_drafts": spec_drafts_delta,
                "spec_decode_draft_tokens": spec_draft_tokens_delta,
                "spec_decode_accepted_tokens": spec_accepted_tokens_delta,
                "spec_decode_acceptance_fraction": None
                if spec_draft_tokens_delta <= 0
                else spec_accepted_tokens_delta / spec_draft_tokens_delta,
                "spec_decode_accepted_tokens_per_generation_token": None
                if gen_delta <= 0
                else spec_accepted_tokens_delta / gen_delta,
                "vram_mib_before": vram_pre,
                "vram_mib_after": vram_post,
                "first_chunk_tokens_client_estimate": first_chunk_tokens,
                "streamed_text_chunks": result.get("streamed_text_chunks"),
                "text_preview": text[:240],
        }
        if args.include_full_text:
            record["text"] = text
        records.append(record)

    artifact = {
        "created_at_unix": time.time(),
        "base_url": args.base_url,
        "model": model,
        "tokenizer": args.tokenizer,
        "server_model_record": models["data"][0],
        "prompt_kind": args.prompt_kind,
        "prompt_preset": args.prompt_preset,
        "prompt_file": args.prompt_file,
        "endpoint": args.endpoint,
        "seed": args.seed,
        "random_prefix_len": args.random_prefix_len,
        "prompt_tokens_requested": args.prompt_tokens,
        "prompt_tokens_actual": prompt_tokens,
        "output_tokens_requested": args.output_tokens,
        "mode": args.mode,
        "ignore_eos": args.ignore_eos,
        "request_extra": request_extra,
        "skip_vram": args.skip_vram,
        "repeats": args.repeats,
        "measurement_notes": [
            "TTFT and e2e are measured both client-side and from vLLM Prometheus histogram deltas.",
            "tok_s_prefill_lower_bound_from_ttft is prompt_tokens / TTFT, so it is conservative and includes first-token scheduling/decode overhead.",
            "tok_s_out_client_after_first_chunk is generated-token-only throughput after the first streamed text chunk.",
            "tok_s_out_client_after_first_chunk_corrected subtracts the estimated first streamed chunk tokens from the numerator; this is more stable when --stream-interval > 1.",
        ],
        "vram_mib_before_all": vram_before,
        "peak_vram_mib_observed": peak_vram,
        "records": records,
        "summary": summarize_repeats(records),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    print(f"wrote={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
