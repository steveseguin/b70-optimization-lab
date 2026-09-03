#!/usr/bin/env python3
"""Run the MiniMax M2.7 structured HTML skeleton quality/speed lane.

This is the compact public-repo runner for the 2026-05-22 regex2 result. It is
intentionally narrower than the local exploratory website harness: it validates
one constrained simple-HTML task and records rejected attempts against effective
throughput.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import os
import re
import sys
import time
from pathlib import Path


TASK_ID = "skeleton_status_html"
SYSTEM_PROMPT = (
    "You are a precise front-end coding assistant. Return the requested "
    "complete HTML document as the final answer. Do not include prose outside "
    "the document."
)
TASK_PROMPT = (
    "Build a tiny complete single-file static website for 'B70 MiniMax Lab "
    "Status'. Return only one valid HTML document, no markdown and no "
    "explanation. Requirements: ASCII text only, no JavaScript, no CSS, no "
    "forms, keep it under 520 characters. Use this exact page structure: "
    "doctype, html lang en, head with utf-8 meta and title, body, main, one "
    "section, h1, one short paragraph, one ul with exactly three li items, "
    "footer, then close every tag. Use these three list item labels: GPUs "
    "ready, Model loaded, Benchmarks passing. Use footer text: Updated: Ready."
)
ASSISTANT_PREFILL = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    "<title>B70 MiniMax Lab Status</title></head><body><main><section>"
    "<h1>B70 MiniMax Lab Status</h1><p>"
)
REGEX2_SUFFIX = (
    r"[A-Z][A-Za-z0-9,.-]{1,20}"
    r"(?: [A-Za-z0-9][A-Za-z0-9,.-]{0,20}){2,12}</p><ul>"
    r"<li>GPUs ready</li><li>Model loaded</li>"
    r"<li>Benchmarks passing</li></ul></section></main>"
    r"<footer>Updated: Ready</footer></body></html>"
)


class TagCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.end_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag.lower())

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.tags.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        self.end_tags.append(tag.lower())


def prepend_env_path(name: str, value: str) -> None:
    current = os.environ.get(name, "")
    parts = [part for part in current.split(":") if part]
    if value not in parts:
        os.environ[name] = ":".join([value, *parts])
    if name == "PYTHONPATH" and value not in sys.path:
        sys.path.insert(0, value)


def configure_env(args: argparse.Namespace) -> None:
    os.environ.setdefault("ONEAPI_DEVICE_SELECTOR", "level_zero:0,1,2,3")
    os.environ.setdefault("ZE_AFFINITY_MASK", "0,1,2,3")
    os.environ.setdefault("CCL_ATL_TRANSPORT", "ofi")
    os.environ.setdefault("CCL_TOPO_P2P_ACCESS", "1")
    os.environ.setdefault("HF_HOME", "/mnt/fast-ai/llm-cache/hf")
    os.environ.setdefault("TRANSFORMERS_CACHE", f"{os.environ['HF_HOME']}/transformers")
    prepend_env_path(
        "PYTHONPATH",
        os.environ.get(
            "LLM_SCALER_KERNELS",
            "/home/steve/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python",
        ),
    )
    venv = os.environ.get("VENV") or os.path.expanduser("~/.venvs/vllm-xpu")
    prepend_env_path("LD_LIBRARY_PATH", f"{venv}/lib")
    prepend_env_path(
        "LD_LIBRARY_PATH",
        f"{venv}/lib/python3.12/site-packages/torch/lib",
    )
    if args.cache_root:
        os.environ["VLLM_CACHE_ROOT"] = args.cache_root

    os.environ.setdefault("VLLM_XPU_USE_LLM_SCALER_MOE", "1")
    os.environ.setdefault("VLLM_XPU_USE_LLM_SCALER_MOE_WS", "1")
    os.environ.setdefault("VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS", "1")
    os.environ.setdefault("VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP", "1")
    os.environ.setdefault("VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP", "1")
    os.environ.setdefault("VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS", "4")
    os.environ.setdefault("VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES", "0")

    if args.mode == "eager":
        os.environ["VLLM_XPU_ENABLE_XPU_GRAPH"] = "0"
        os.environ.pop("VLLM_XPU_FORCE_GRAPH_WITH_COMM", None)
        os.environ.pop("VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE", None)
    else:
        os.environ["VLLM_XPU_ENABLE_XPU_GRAPH"] = "1"
        os.environ.setdefault("VLLM_XPU_FORCE_GRAPH_WITH_COMM", "1")
        os.environ.setdefault("VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE", "1")


def extract_html(text: str) -> tuple[str, str]:
    match = re.search(r"<!doctype\s+html|<html[\s>]", text, flags=re.IGNORECASE)
    if not match:
        return text.strip(), "full_text"
    start = match.start()
    end = re.search(r"</html\s*>", text[start:], flags=re.IGNORECASE)
    if not end:
        return text[start:].strip(), "html_start"
    return text[start : start + end.end()].strip(), "html_document"


def validate_html(html_text: str) -> dict[str, object]:
    failures: list[str] = []
    parser = TagCollector()
    try:
        parser.feed(html_text)
    except html.parser.HTMLParseError as exc:
        failures.append(f"parse:{exc}")

    lower = html_text.lower()
    for tag in ("html", "head", "body", "main", "section", "ul", "footer"):
        if tag not in parser.tags:
            failures.append(f"missing_tag:{tag}")
    for required in (
        "<li>GPUs ready</li>",
        "<li>Model loaded</li>",
        "<li>Benchmarks passing</li>",
        "Updated: Ready",
        "B70 MiniMax Lab Status",
    ):
        if required not in html_text:
            failures.append(f"missing_text:{required}")
    if lower.count("<li>") != 3:
        failures.append(f"li_count:{lower.count('<li>')}")
    if not lower.startswith("<!doctype html>"):
        failures.append("missing_doctype")
    if "</html>" not in lower:
        failures.append("missing_html_close")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", html_text):
        failures.append("control_chars")
    if re.search(r"[<>]{3,}|[\"']{8,}", html_text):
        failures.append("corruption_fragment")
    if len(html_text) > 650:
        failures.append(f"too_long:{len(html_text)}")

    return {
        "passed": not failures,
        "failures": failures,
        "sha256": hashlib.sha256(html_text.encode("utf-8", "replace")).hexdigest(),
        "chars": len(html_text),
    }


def build_prompt(tokenizer, args: argparse.Namespace) -> str:
    prompt = TASK_PROMPT + (
        "\n\nThe assistant response has already started with a valid HTML "
        "prefix. Continue directly from that prefix. Do not repeat doctype, "
        "html, head, body, main, section, h1, or the opening paragraph tag."
    )
    rendered = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": args.system_prompt},
            {"role": "user", "content": prompt},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    if rendered.endswith("<think>\n"):
        rendered += "</think>\n\n"
    return rendered + ASSISTANT_PREFILL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default=os.environ.get(
            "MINIMAX_M27_MODEL", "/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround"
        ),
    )
    parser.add_argument("--out", default="result.json")
    parser.add_argument("--sites-dir", default="sites")
    parser.add_argument("--mode", choices=("graph", "eager"), default="graph")
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-batched-tokens", type=int, default=512)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--retry-until-pass", type=int, default=5)
    parser.add_argument("--cache-root")
    parser.add_argument("--disable-prefix-caching", action="store_true")
    parser.add_argument("--disable-chunked-prefill", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=-1)
    parser.add_argument("--system-prompt", default=SYSTEM_PROMPT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_env(args)

    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    compilation_config = {
        "use_inductor_graph_partition": True,
        "compile_sizes": [1],
        "compile_ranges_endpoints": [args.max_num_batched_tokens],
        "custom_ops": ["none"],
        "cudagraph_mode": "NONE" if args.mode == "eager" else "PIECEWISE",
    }

    init_started = time.perf_counter()
    llm = LLM(
        model=args.model,
        tokenizer=args.model,
        trust_remote_code=True,
        dtype=args.dtype,
        tensor_parallel_size=args.tensor_parallel_size,
        distributed_executor_backend="mp",
        max_model_len=args.max_model_len,
        max_num_batched_tokens=args.max_num_batched_tokens,
        max_num_seqs=args.max_num_seqs,
        block_size=args.block_size,
        enforce_eager=args.mode == "eager",
        enable_chunked_prefill=not args.disable_chunked_prefill,
        enable_prefix_caching=not args.disable_prefix_caching,
        compilation_config=compilation_config,
    )
    init_elapsed_s = time.perf_counter() - init_started

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    rendered_prompt = build_prompt(tokenizer, args)
    params = SamplingParams(
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        max_tokens=args.max_tokens,
        seed=0,
        stop=["</html>"],
        include_stop_str_in_output=True,
        stop_token_ids=[200020],
        structured_outputs=StructuredOutputsParams(regex=REGEX2_SUFFIX),
    )

    sites_dir = Path(args.sites_dir)
    sites_dir.mkdir(parents=True, exist_ok=True)
    records = []
    schedule = [("warmup", i) for i in range(args.warmup_runs)] + [
        ("measured", i) for i in range(args.repeat)
    ]
    for phase, index in schedule:
        for attempt in range(args.retry_until_pass):
            started = time.perf_counter()
            output = llm.generate([rendered_prompt], params)[0].outputs[0]
            elapsed_s = time.perf_counter() - started
            candidate_text = ASSISTANT_PREFILL + output.text
            html_text, extraction = extract_html(candidate_text)
            validation = validate_html(html_text)
            suffix = f"{phase}-r{index}-a{attempt}"
            html_path = sites_dir / f"{TASK_ID}-{suffix}.html"
            raw_path = sites_dir / f"{TASK_ID}-{suffix}.raw.txt"
            html_path.write_text(html_text, encoding="utf-8")
            raw_path.write_text(candidate_text, encoding="utf-8")
            record = {
                "phase": phase,
                "repeat_index": index,
                "attempt_index": attempt,
                "elapsed_s": elapsed_s,
                "generated_tokens": len(output.token_ids),
                "tok_s": len(output.token_ids) / elapsed_s if elapsed_s > 0 else None,
                "finish_reason": output.finish_reason,
                "token_sha256": hashlib.sha256(
                    ",".join(map(str, output.token_ids)).encode()
                ).hexdigest(),
                "extraction": extraction,
                "html_path": str(html_path),
                "raw_path": str(raw_path),
                "validation": validation,
            }
            records.append(record)
            if validation["passed"]:
                break

    measured = [record for record in records if record["phase"] == "measured"]
    accepted = [record for record in measured if record["validation"]["passed"]]
    rejected = [record for record in measured if not record["validation"]["passed"]]
    accepted_tokens = sum(record["generated_tokens"] for record in accepted)
    attempt_tokens = sum(record["generated_tokens"] for record in measured)
    accepted_elapsed = sum(record["elapsed_s"] for record in accepted)
    attempt_elapsed = sum(record["elapsed_s"] for record in measured)
    result = {
        "passed": len(accepted) == args.repeat,
        "task": TASK_ID,
        "model": args.model,
        "runtime": {
            "mode": args.mode,
            "tensor_parallel_size": args.tensor_parallel_size,
            "dtype": args.dtype,
            "max_model_len": args.max_model_len,
            "max_num_batched_tokens": args.max_num_batched_tokens,
            "block_size": args.block_size,
            "prefix_caching": not args.disable_prefix_caching,
            "chunked_prefill": not args.disable_chunked_prefill,
            "env": {
                key: os.environ.get(key)
                for key in (
                    "VLLM_XPU_ENABLE_XPU_GRAPH",
                    "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
                    "VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE",
                    "VLLM_XPU_USE_LLM_SCALER_MOE",
                    "VLLM_XPU_USE_LLM_SCALER_MOE_WS",
                    "VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS",
                    "VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP",
                    "VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP",
                )
            },
        },
        "init_elapsed_s": init_elapsed_s,
        "metrics": {
            "expected_outputs": args.repeat,
            "accepted_outputs": len(accepted),
            "rejected_attempts": len(rejected),
            "first_attempt_passes": sum(
                1 for record in accepted if record["attempt_index"] == 0
            ),
            "first_attempt_pass_rate": (
                sum(1 for record in accepted if record["attempt_index"] == 0)
                / args.repeat
                if args.repeat
                else None
            ),
            "accepted_output_tokens": accepted_tokens,
            "all_attempt_tokens": attempt_tokens,
            "accepted_decode_elapsed_s": accepted_elapsed,
            "all_attempt_decode_elapsed_s": attempt_elapsed,
            "accepted_output_tok_s": (
                accepted_tokens / accepted_elapsed if accepted_elapsed > 0 else None
            ),
            "effective_accepted_output_tok_s": (
                accepted_tokens / attempt_elapsed if attempt_elapsed > 0 else None
            ),
        },
        "records": records,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"out": args.out, "metrics": result["metrics"]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
