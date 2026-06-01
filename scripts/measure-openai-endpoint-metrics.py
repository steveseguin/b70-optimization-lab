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


def make_prompt(tokenizer: Any, target_tokens: int) -> str:
    seed = (
        "Local Intel XPU benchmark prompt. "
        "The assistant should continue with concise technical text. "
    )
    text = seed
    while len(tokenizer.encode(text, add_special_tokens=False)) < target_tokens + 8:
        text += seed
    ids = tokenizer.encode(text, add_special_tokens=False)[:target_tokens]
    return tokenizer.decode(ids, skip_special_tokens=True)


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


def stream_completion(base_url: str, model: str, prompt: str, max_tokens: int) -> dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
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
    with urllib.request.urlopen(req, timeout=max(120, max_tokens * 5)) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            event = json.loads(data)
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
        "text": "".join(chunks),
        "usage": usage,
        "elapsed_s": t1 - t0,
        "ttft_s": None if first is None else first - t0,
        "generation_wall_s_after_first_chunk": None if first is None else t1 - first,
        "first_chunk_text": first_chunk_text,
        "streamed_text_chunks": streamed_text_chunks,
    }


def summarize_repeats(records: list[dict[str, Any]]) -> dict[str, Any]:
    def vals(key: str) -> list[float]:
        return [float(r[key]) for r in records if r.get(key) is not None]

    summary: dict[str, Any] = {}
    for key in [
        "tok_s_out_client_after_first_chunk",
        "tok_s_out_client_after_first_chunk_corrected",
        "tok_s_total_client",
        "ttft_ms_client",
        "ttft_ms_vllm_metrics",
        "tok_s_prefill_lower_bound_from_ttft",
        "e2e_ms_vllm_metrics",
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
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--warmup-output-tokens", type=int, default=32)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    models = get_json(f"{args.base_url.rstrip('/')}/v1/models")
    model = args.model or models["data"][0]["id"]
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    prompt = make_prompt(tokenizer, args.prompt_tokens)
    prompt_tokens = len(tokenizer.encode(prompt, add_special_tokens=False))

    if args.warmup_output_tokens > 0:
        stream_completion(args.base_url, model, prompt, args.warmup_output_tokens)

    records: list[dict[str, Any]] = []
    vram_before = xpu_vram_mib()
    peak_vram = dict(vram_before)
    for i in range(args.repeats):
        metrics_before = parse_metric_sums(get_text(f"{args.base_url.rstrip('/')}/metrics"))
        vram_pre = xpu_vram_mib()
        result = stream_completion(args.base_url, model, prompt, args.output_tokens)
        vram_post = xpu_vram_mib()
        metrics_after = parse_metric_sums(get_text(f"{args.base_url.rstrip('/')}/metrics"))

        text = result["text"]
        output_tokens = (
            int(result["usage"]["completion_tokens"])
            if result.get("usage") and result["usage"].get("completion_tokens") is not None
            else len(tokenizer.encode(text, add_special_tokens=False))
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
        ttft_count = metric_delta(
            metrics_before, metrics_after, "vllm:time_to_first_token_seconds_count"
        )
        ttft_sum = metric_delta(metrics_before, metrics_after, "vllm:time_to_first_token_seconds_sum")
        e2e_count = metric_delta(metrics_before, metrics_after, "vllm:e2e_request_latency_seconds_count")
        e2e_sum = metric_delta(metrics_before, metrics_after, "vllm:e2e_request_latency_seconds_sum")

        for values in (vram_pre, vram_post):
            for key, value in values.items():
                if key not in peak_vram or value > peak_vram[key]:
                    peak_vram[key] = value

        records.append(
            {
                "repeat": i + 1,
                "prompt_tokens_client": prompt_tokens,
                "output_tokens_client": output_tokens,
                "elapsed_s_client": elapsed,
                "ttft_ms_client": None if ttft_s is None else ttft_s * 1000,
                "tok_s_out_client_after_first_chunk": None
                if not after_first or after_first <= 0
                else output_tokens / after_first,
                "tok_s_out_client_after_first_chunk_corrected": None
                if not after_first or after_first <= 0
                else max(0, output_tokens - first_chunk_tokens) / after_first,
                "tok_s_total_client": (prompt_tokens + output_tokens) / elapsed,
                "tok_s_prefill_lower_bound_from_ttft": None
                if not ttft_s or ttft_s <= 0
                else prompt_tokens / ttft_s,
                "vllm_metric_deltas": {
                    "prompt_tokens": prompt_delta,
                    "generation_tokens": gen_delta,
                    "ttft_count": ttft_count,
                    "ttft_sum_s": ttft_sum,
                    "e2e_count": e2e_count,
                    "e2e_sum_s": e2e_sum,
                },
                "ttft_ms_vllm_metrics": None
                if ttft_count <= 0
                else (ttft_sum / ttft_count) * 1000,
                "e2e_ms_vllm_metrics": None if e2e_count <= 0 else (e2e_sum / e2e_count) * 1000,
                "vram_mib_before": vram_pre,
                "vram_mib_after": vram_post,
                "first_chunk_tokens_client_estimate": first_chunk_tokens,
                "streamed_text_chunks": result.get("streamed_text_chunks"),
                "text_preview": text[:240],
            }
        )

    artifact = {
        "created_at_unix": time.time(),
        "base_url": args.base_url,
        "model": model,
        "tokenizer": args.tokenizer,
        "server_model_record": models["data"][0],
        "prompt_tokens_requested": args.prompt_tokens,
        "prompt_tokens_actual": prompt_tokens,
        "output_tokens_requested": args.output_tokens,
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
