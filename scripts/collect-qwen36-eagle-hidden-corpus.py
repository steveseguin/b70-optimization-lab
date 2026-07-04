#!/usr/bin/env python3
"""Drive a vLLM endpoint to create hidden-state dump rows for EAGLE training.

The endpoint must be launched separately with:

  VLLM_XPU_EAGLE_DATA_DUMP_DIR=<dump-dir>

This script sends deterministic completion or chat requests and records request
metadata. The vLLM worker hook writes the actual hidden-state shards.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


@dataclass(frozen=True)
class PromptSpec:
    family: str
    prefix: str
    filler: str
    suffix: str


PROMPTS: list[PromptSpec] = [
    PromptSpec(
        family="xpu-debug",
        prefix=(
            "You are diagnosing a local Intel XPU inference server. "
            "Give a direct engineering analysis.\n\n"
        ),
        filler=(
            "Observed data includes decode latency, graph capture behavior, "
            "MoE routing overhead, KV-cache residency, and exact token parity "
            "requirements. "
        ),
        suffix=(
            "\n\nWrite ordered findings, then concrete next experiments. "
            "Be specific about measurements and failure gates.\n"
        ),
    ),
    PromptSpec(
        family="code-review",
        prefix=(
            "Review this service code for latency and correctness bugs. "
            "Prioritize actionable findings.\n\n"
        ),
        filler=(
            "def serve(req, engine):\n"
            "    payload = normalize(req.json())\n"
            "    if payload.get('stream'):\n"
            "        for token in engine.generate(payload):\n"
            "            metrics.observe_token(token)\n"
            "            yield encode_sse(token)\n"
            "    else:\n"
            "        return engine.generate_once(payload)\n\n"
        ),
        suffix=(
            "\nReturn findings first, then a minimal patch plan and tests. "
            "Avoid unrelated refactors.\n"
        ),
    ),
    PromptSpec(
        family="structured-json",
        prefix=(
            "Return compact JSON only. The object must contain summary, risks, "
            "experiments, and promotion_gate.\n\n"
        ),
        filler=(
            "Input note: a benchmark candidate must preserve token-level output "
            "quality, record full run identity, and report both single-request "
            "decode speed and aggregate throughput. "
        ),
        suffix=(
            "\nInclude at least eight experiment objects with name, expected_gain, "
            "risk, and validation. No markdown.\n"
        ),
    ),
    PromptSpec(
        family="math-planning",
        prefix=(
            "Solve the planning calculation and explain the tradeoff briefly.\n\n"
        ),
        filler=(
            "A baseline produces 99 tokens per second. A target requires 150 "
            "tokens per second. Each speculative candidate has a verifier cost, "
            "draft cost, acceptance rate, and possible quality gate failure. "
        ),
        suffix=(
            "\nCompute the required percentage gain, then rank three optimization "
            "paths with formulas and assumptions.\n"
        ),
    ),
    PromptSpec(
        family="ops-runbook",
        prefix=(
            "Write a production runbook section for a local LLM endpoint.\n\n"
        ),
        filler=(
            "The service uses multiple XPUs, OpenAI-compatible HTTP routes, "
            "structured logs, benchmark artifacts, health checks, and quality "
            "canaries. "
        ),
        suffix=(
            "\nCover startup, readiness, rollback, benchmark validation, and "
            "incident triage in concise numbered steps.\n"
        ),
    ),
    PromptSpec(
        family="design-critique",
        prefix=(
            "Critique the proposed optimization design and identify hidden risks.\n\n"
        ),
        filler=(
            "The proposal combines graph replay, speculative decoding, draft "
            "training, scheduler changes, and exact output parity checks. "
        ),
        suffix=(
            "\nSeparate correctness risks from performance risks. End with a "
            "go/no-go checklist.\n"
        ),
    ),
    PromptSpec(
        family="debug-log",
        prefix=(
            "Analyze the following production incident log. Identify the most "
            "likely root cause and the next commands to run.\n\n"
        ),
        filler=(
            "worker=rank2 event=decode_step latency_ms=12.8 queue_depth=1 "
            "xpu_temp_c=71 ccl_wait_us=64 moe_us=5261 sampler_us=340 "
            "status=canary_mismatch retry=false "
        ),
        suffix=(
            "\nWrite a concise incident analysis with evidence, rejected "
            "hypotheses, and a rollback condition.\n"
        ),
    ),
    PromptSpec(
        family="python-patch",
        prefix=(
            "Patch this Python benchmark harness. Keep behavior unchanged "
            "except for the requested fix.\n\n"
        ),
        filler=(
            "def summarize(rows):\n"
            "    total = 0\n"
            "    for row in rows:\n"
            "        total += row['latency_us']\n"
            "    return {'mean_us': total / len(rows)}\n\n"
        ),
        suffix=(
            "\nAdd p50, p90, and max. Include a tiny self-test using plain "
            "assert statements.\n"
        ),
    ),
    PromptSpec(
        family="sql-analysis",
        prefix=(
            "Given this database schema and query workload, recommend indexes "
            "and explain tradeoffs.\n\n"
        ),
        filler=(
            "tables: benchmark_runs(id, model_id, hardware_id, tok_s_out, "
            "created_at), artifacts(run_id, path, kind), quality(run_id, "
            "suite, pass_all). Queries filter by model_id, date range, "
            "hardware_id, and pass_all. "
        ),
        suffix=(
            "\nReturn index DDL, expected read benefit, write cost, and one "
            "query plan risk.\n"
        ),
    ),
    PromptSpec(
        family="shell-runbook",
        prefix=(
            "Write a shell-oriented troubleshooting runbook for this failure.\n\n"
        ),
        filler=(
            "A multi-GPU job fails during distributed barrier with an out of "
            "resources error on one device. Single-device smoke passes on "
            "some devices and fails on one physical card. "
        ),
        suffix=(
            "\nInclude exact command examples, expected outputs, and when to "
            "stop and reboot.\n"
        ),
    ),
    PromptSpec(
        family="api-contract",
        prefix=(
            "Design an OpenAI-compatible API contract extension for benchmark "
            "metadata.\n\n"
        ),
        filler=(
            "The client submits prompt_tokens, output_tokens, tok_s_out, "
            "ttft_ms, peak_vram_gb, engine flags, quality suite results, and "
            "hardware identity. "
        ),
        suffix=(
            "\nReturn a JSON schema and three validation errors with clear "
            "messages.\n"
        ),
    ),
    PromptSpec(
        family="longform-summary",
        prefix=(
            "Summarize the following engineering notes for a teammate taking "
            "over the work.\n\n"
        ),
        filler=(
            "The latest accepted lane is faster only when benchmark identity "
            "matches exactly. Several local optimizations were exact but not "
            "repeatably faster. The next work should preserve quality and "
            "avoid stale graph-state conclusions. "
        ),
        suffix=(
            "\nOrganize the result into current state, blockers, known traps, "
            "next steps, and artifacts to inspect.\n"
        ),
    ),
    PromptSpec(
        family="test-plan",
        prefix=(
            "Create a reliability test plan for a local language-model "
            "inference endpoint.\n\n"
        ),
        filler=(
            "The endpoint supports greedy decoding, speculative decoding, "
            "structured JSON canaries, long-context prompts, and warm/cold "
            "startup modes. "
        ),
        suffix=(
            "\nInclude pass/fail gates, repeat counts, telemetry to capture, "
            "and how to compare against a baseline.\n"
        ),
    ),
    PromptSpec(
        family="algorithm",
        prefix=(
            "Explain and implement the algorithm requested below.\n\n"
        ),
        filler=(
            "Maintain a rolling median and p90 latency estimate for a stream "
            "of integer microsecond measurements. The implementation should "
            "handle duplicates, empty input, and reset. "
        ),
        suffix=(
            "\nReturn Python code first, then a short complexity analysis and "
            "edge-case tests.\n"
        ),
    ),
    PromptSpec(
        family="comparison",
        prefix=(
            "Compare two engineering approaches and choose one for immediate "
            "implementation.\n\n"
        ),
        filler=(
            "Approach A reduces per-token dispatch overhead but requires a "
            "new kernel. Approach B uses a learned draft model and needs "
            "training data plus verifier parity. Both must preserve exact "
            "output quality. "
        ),
        suffix=(
            "\nUse a decision matrix with expected gain, risk, validation, and "
            "fallback plan.\n"
        ),
    ),
    PromptSpec(
        family="user-support",
        prefix=(
            "Answer this user support request with calm, concrete guidance.\n\n"
        ),
        filler=(
            "The user reports that model output became slower after changing "
            "a launch script. They are unsure which environment variables "
            "changed and need a reproducible comparison. "
        ),
        suffix=(
            "\nAsk only for missing facts that cannot be discovered locally, "
            "then provide the immediate diagnostic steps.\n"
        ),
    ),
]


def fit_prompt(tokenizer: Any, spec: PromptSpec, target_tokens: int,
               variant: int) -> str:
    prefix = f"[case {variant:03d} / {spec.family}]\n" + spec.prefix
    filler = spec.filler
    if variant % 3 == 1:
        filler += " Use careful wording and avoid vague claims. "
    elif variant % 3 == 2:
        filler += " Include edge cases, counters, and a rollback condition. "
    suffix = spec.suffix

    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    suffix_ids = tokenizer.encode(suffix, add_special_tokens=False)
    filler_ids = tokenizer.encode(filler, add_special_tokens=False)
    if not filler_ids:
        raise ValueError("filler produced no tokens")
    budget = max(0, target_tokens - len(prefix_ids) - len(suffix_ids))
    body_ids = (filler_ids * ((budget + len(filler_ids) - 1) //
                              len(filler_ids)))[:budget]
    ids = prefix_ids + body_ids + suffix_ids
    return tokenizer.decode(ids[:target_tokens], skip_special_tokens=True)


def safe_request_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", value).strip("-")[:180]


def load_suite(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    suite = json.loads(path.read_text())
    if isinstance(suite, list):
        meta = {"suite_id": path.stem, "version": None}
        prompts = suite
    else:
        meta = {k: v for k, v in suite.items() if k != "prompts"}
        prompts = suite["prompts"]
    out: list[dict[str, Any]] = []
    for index, item in enumerate(prompts):
        if isinstance(item, dict):
            prompt_id = str(item.get("id", f"prompt-{index:02d}"))
            prompt = str(item.get("prompt", ""))
            messages = item.get("messages")
            family = str(item.get("family", item.get("category", prompt_id)))
            metadata = {k: v for k, v in item.items()
                        if k not in ("prompt", "messages")}
        else:
            prompt_id = f"prompt-{index:02d}"
            prompt = str(item)
            messages = None
            family = prompt_id
            metadata = {"id": prompt_id}
        if not prompt and not messages:
            raise ValueError(f"suite prompt {prompt_id!r} has no prompt/messages")
        out.append({
            "suite_index": index,
            "prompt_id": prompt_id,
            "family": family,
            "prompt": prompt,
            "messages": messages,
            "metadata": metadata,
        })
    return meta, out


def request_generation(
    base_url: str,
    model: str,
    *,
    api_mode: str,
    prompt: str,
    messages: list[dict[str, Any]] | None,
    max_tokens: int,
    seed: int,
    ignore_eos: bool,
    request_extra: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        "seed": seed,
        "stream": False,
    }
    if ignore_eos:
        payload["ignore_eos"] = True
    if api_mode == "chat":
        endpoint = "chat/completions"
        if messages is not None:
            payload["messages"] = messages
        else:
            payload["messages"] = [{"role": "user", "content": prompt}]
    else:
        endpoint = "completions"
        payload["prompt"] = prompt
    payload.update(request_extra)
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=max(120, max_tokens * 8)) as resp:
        response_x_request_id = resp.headers.get("X-Request-Id")
        data = json.loads(resp.read())
    elapsed = time.perf_counter() - t0
    choices = data.get("choices") or []
    text = ""
    if choices:
        if api_mode == "chat":
            message = choices[0].get("message") or {}
            text = message.get("content") or message.get("reasoning") or ""
        else:
            text = choices[0].get("text") or ""
    usage = data.get("usage") or {}
    return {
        "request_id": request_id,
        "response_id": data.get("id"),
        "response_x_request_id": response_x_request_id,
        "elapsed_s": elapsed,
        "text": text or "",
        "usage": usage,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--suite", default="")
    parser.add_argument("--api-mode", choices=("chat", "completions"),
                        default="completions")
    parser.add_argument("--request-extra-json", default="{}")
    parser.add_argument("--request-id-prefix", default="qwen27-eagle")
    parser.add_argument("--num-prompts", type=int, default=0)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--output-tokens", type=int, default=96)
    parser.add_argument("--prompt-token-sizes", default="96,128,192,256,384")
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--ignore-eos", action="store_true")
    args = parser.parse_args()

    try:
        request_extra = json.loads(args.request_extra_json)
    except Exception as exc:
        raise SystemExit(f"invalid --request-extra-json: {exc}") from exc
    if not isinstance(request_extra, dict):
        raise SystemExit("--request-extra-json must decode to a JSON object")

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True)
    sizes = [
        int(part.strip()) for part in args.prompt_token_sizes.split(",")
        if part.strip()
    ]
    if not sizes:
        raise ValueError("--prompt-token-sizes produced no sizes")

    suite_meta: dict[str, Any] | None = None
    suite_prompts: list[dict[str, Any]] = []
    if args.suite:
        suite_meta, suite_prompts = load_suite(Path(args.suite))
    num_prompts = args.num_prompts
    if num_prompts <= 0:
        num_prompts = len(suite_prompts) if suite_prompts else 48
    if num_prompts <= 0:
        raise ValueError("no prompts selected")

    records: list[dict[str, Any]] = []
    for offset in range(num_prompts):
        i = args.start_index + offset
        if suite_prompts:
            item = suite_prompts[i % len(suite_prompts)]
            family = str(item["family"])
            prompt_id = str(item["prompt_id"])
            prompt = str(item.get("prompt") or "")
            messages = item.get("messages")
            prompt_tokens_target = None
            suite_index = item["suite_index"]
            item_metadata = item["metadata"]
        else:
            spec = PROMPTS[i % len(PROMPTS)]
            family = spec.family
            prompt_id = f"{spec.family}-{i:04d}"
            prompt_tokens_target = sizes[i % len(sizes)]
            prompt = fit_prompt(tokenizer, spec, prompt_tokens_target, i)
            messages = None
            suite_index = None
            item_metadata = {"id": prompt_id, "family": family}
        prompt_for_hash = prompt
        if not prompt_for_hash and messages is not None:
            prompt_for_hash = json.dumps(messages, sort_keys=True)
        prompt_tokens_actual = len(
            tokenizer.encode(prompt_for_hash, add_special_tokens=False)
        )
        request_id = safe_request_id(
            f"{args.request_id_prefix}-{i:06d}-{prompt_id}")
        result = request_generation(
            args.base_url,
            args.model,
            api_mode=args.api_mode,
            prompt=prompt,
            messages=messages,
            max_tokens=args.output_tokens,
            seed=args.seed + i,
            ignore_eos=args.ignore_eos,
            request_extra=request_extra,
            request_id=request_id,
        )
        text = result["text"]
        usage = result.get("usage") or {}
        output_tokens = usage.get("completion_tokens")
        if output_tokens is None:
            output_tokens = len(tokenizer.encode(text, add_special_tokens=False))
        record = {
            "index": i,
            "offset": offset,
            "suite_index": suite_index,
            "prompt_id": prompt_id,
            "family": family,
            "request_id": result.get("request_id"),
            "response_id": result.get("response_id"),
            "response_x_request_id": result.get("response_x_request_id"),
            "prompt_tokens_target": prompt_tokens_target,
            "prompt_tokens_actual": prompt_tokens_actual,
            "output_tokens_requested": args.output_tokens,
            "output_tokens_actual": int(output_tokens),
            "elapsed_s": result["elapsed_s"],
            "tok_s_e2e": (float(output_tokens) / result["elapsed_s"]
                          if result["elapsed_s"] > 0 else None),
            "prompt_sha256": hashlib.sha256(
                prompt_for_hash.encode("utf-8")).hexdigest(),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text_preview": text[:160],
            "metadata": item_metadata,
        }
        records.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)

    summary = {
        "created_at_unix": time.time(),
        "base_url": args.base_url,
        "model": args.model,
        "tokenizer": args.tokenizer,
        "api_mode": args.api_mode,
        "suite": args.suite,
        "suite_meta": suite_meta,
        "request_extra_json": request_extra,
        "request_id_prefix": args.request_id_prefix,
        "num_prompts": num_prompts,
        "start_index": args.start_index,
        "output_tokens_requested": args.output_tokens,
        "prompt_token_sizes": sizes,
        "ignore_eos": args.ignore_eos,
        "records": records,
        "total_output_tokens_actual": sum(r["output_tokens_actual"]
                                          for r in records),
        "families": sorted({r["family"] for r in records}),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"wrote={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
