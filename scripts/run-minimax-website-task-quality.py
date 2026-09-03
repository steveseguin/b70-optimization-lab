#!/usr/bin/env python3
"""Ask MiniMax to build small websites and validate task-level output.

This is a functional quality probe. It is intentionally stricter than token
diversity checks and less brittle than exact token hashes: the model must emit
usable single-file HTML/CSS/JS that satisfies task-specific requirements.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebsiteTask:
    task_id: str
    prompt: str
    required_tags: tuple[str, ...]
    required_patterns: tuple[tuple[str, str], ...]
    min_chars: int = 900


TASKS = [
    WebsiteTask(
        task_id="benchmark_dashboard",
        prompt=(
            "Build a complete single-file responsive website for a local AI "
            "benchmark dashboard named 'B70 MiniMax Lab'. Return only one "
            "valid HTML document, no markdown and no explanation. Requirements: "
            "use semantic HTML, include accessible navigation, metric cards for "
            "output tok/s, total tok/s, context length, and GPU count, include "
            "a comparison table, include a canvas chart with JavaScript that "
            "draws bars for three benchmark runs, include a theme toggle button, "
            "and include responsive CSS with a media query."
        ),
        required_tags=("html", "head", "body", "style", "script", "nav", "main", "table", "canvas", "button"),
        required_patterns=(
            ("brand", r"B70|MiniMax"),
            ("tok_s_metric", r"tok/s|tokens per second"),
            ("responsive_media_query", r"@media\s*\("),
            ("layout_css", r"display\s*:\s*(grid|flex)"),
            ("event_listener", r"addEventListener\s*\("),
            ("canvas_context", r"getContext\s*\("),
        ),
    ),
    WebsiteTask(
        task_id="task_tracker",
        prompt=(
            "Build a complete single-file responsive website for an offline "
            "experiment task tracker. Return only one valid HTML document, no "
            "markdown and no explanation. Requirements: include a form with a "
            "text input and submit button, render a task list, allow adding "
            "tasks, completing tasks, deleting tasks, filtering all/active/done, "
            "persist tasks with localStorage, include accessible labels, and "
            "include responsive CSS with a media query."
        ),
        required_tags=("html", "head", "body", "style", "script", "form", "input", "button", "ul"),
        required_patterns=(
            ("local_storage", r"localStorage"),
            ("event_listener", r"addEventListener\s*\("),
            ("filter_controls", r"active|completed|done"),
            ("delete_action", r"delete|remove"),
            ("responsive_media_query", r"@media\s*\("),
            ("accessible_label", r"<label|aria-label"),
        ),
    ),
    WebsiteTask(
        task_id="pricing_calculator",
        prompt=(
            "Build a complete single-file responsive website for a GPU rental "
            "cost calculator. Return only one valid HTML document, no markdown "
            "and no explanation. Requirements: include inputs for GPU count, "
            "hours, and dollars per hour, calculate total cost live in the page, "
            "include a summary section, include an accessible reset button, "
            "include clear validation for invalid numeric input, and include "
            "responsive CSS with a media query."
        ),
        required_tags=("html", "head", "body", "style", "script", "input", "button", "section"),
        required_patterns=(
            ("calculation", r"gpu|hour|total|cost"),
            ("event_listener", r"addEventListener\s*\("),
            ("number_parse", r"parseFloat|Number\s*\("),
            ("validation", r"invalid|error|isNaN|Number\.isFinite"),
            ("reset", r"reset"),
            ("responsive_media_query", r"@media\s*\("),
            ("accessible_label", r"<label|aria-label"),
        ),
    ),
]


class TagCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.start_attrs: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag.lower())
        self.start_attrs.append((tag.lower(), dict(attrs)))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)


def prepend_env_path(name: str, value: str) -> None:
    current = os.environ.get(name, "")
    parts = [part for part in current.split(":") if part]
    if value not in parts:
        os.environ[name] = ":".join([value, *parts])
    if name == "PYTHONPATH" and value not in sys.path:
        sys.path.insert(0, value)


def configure_env(mode: str, cache_root: str | None) -> None:
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
            os.path.expanduser("~/src/llm-scaler/vllm/custom-esimd-kernels-vllm/python"),
        ),
    )
    venv = os.environ.get("VENV") or os.path.expanduser("~/.venvs/vllm-xpu")
    prepend_env_path("LD_LIBRARY_PATH", f"{venv}/lib")
    prepend_env_path(
        "LD_LIBRARY_PATH",
        f"{venv}/lib/python3.12/site-packages/torch/lib",
    )
    if cache_root:
        os.environ["VLLM_CACHE_ROOT"] = cache_root

    os.environ.setdefault("VLLM_XPU_USE_LLM_SCALER_MOE", "1")
    os.environ.setdefault("VLLM_XPU_USE_LLM_SCALER_MOE_WS", "1")
    os.environ.setdefault("VLLM_XPU_USE_LLM_SCALER_MOE_MINIMAX_LOGITS_WS", "1")
    os.environ.setdefault("VLLM_MINIMAX_MOE_OUTPUT_ALLREDUCE_INSIDE_CUSTOM_OP", "1")
    os.environ.setdefault("VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP", "1")
    os.environ.setdefault("VLLM_MINIMAX_MOE_FULL_FORWARD_CUSTOM_OP_MAX_TOKENS", "4")
    os.environ.setdefault("VLLM_XPU_USE_CUSTOM_OP_COLLECTIVES", "0")

    if mode == "eager":
        os.environ["VLLM_XPU_ENABLE_XPU_GRAPH"] = "0"
        os.environ.pop("VLLM_XPU_FORCE_GRAPH_WITH_COMM", None)
        os.environ.pop("VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE", None)
    else:
        os.environ["VLLM_XPU_ENABLE_XPU_GRAPH"] = "1"
        os.environ["VLLM_XPU_FORCE_GRAPH_WITH_COMM"] = "1"
        os.environ["VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE"] = "1"


def extract_html(text: str) -> tuple[str, str]:
    fence = re.search(r"```(?:html)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        return fence.group(1).strip(), "html_fence"

    start_match = re.search(r"<!doctype\s+html|<html[\s>]", text, flags=re.IGNORECASE)
    if start_match:
        start = start_match.start()
        end_match = re.search(r"</html\s*>", text[start:], flags=re.IGNORECASE)
        if end_match:
            end = start + end_match.end()
            return text[start:end].strip(), "html_document"
        return text[start:].strip(), "html_start"

    return text.strip(), "full_text"


def blocks(html: str, tag: str) -> list[str]:
    return re.findall(
        rf"<{tag}\b[^>]*>(.*?)</{tag}\s*>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def balanced(text: str, pairs: tuple[tuple[str, str], ...]) -> bool:
    for left, right in pairs:
        if text.count(left) != text.count(right):
            return False
    return True


def node_check(script: str) -> tuple[bool, str]:
    if not script.strip():
        return True, ""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(script)
        path = handle.name
    try:
        proc = subprocess.run(
            ["node", "--check", path],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        return proc.returncode == 0, (proc.stderr or proc.stdout).strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def validate_site(html_text: str, task: WebsiteTask) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    lowered = html_text.lower()
    parser = TagCollector()
    try:
        parser.feed(html_text)
    except Exception as exc:
        failures.append(f"html_parse_exception:{type(exc).__name__}:{exc}")

    tag_set = set(parser.tags)
    missing_tags = [tag for tag in task.required_tags if tag not in tag_set]
    if missing_tags:
        failures.append("missing_tags:" + ",".join(missing_tags))
    if len(html_text) < task.min_chars:
        failures.append(f"too_short:{len(html_text)}")
    if "<html" not in lowered or "</html" not in lowered:
        failures.append("missing_complete_html_document")
    if "<body" not in lowered or "</body" not in lowered:
        failures.append("missing_complete_body")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", html_text):
        failures.append("control_characters")
    if "```" in html_text:
        warnings.append("markdown_fence_left_in_extracted_html")

    style_text = "\n".join(blocks(html_text, "style"))
    if style_text and not balanced(style_text, (("{", "}"), ("(", ")"))):
        failures.append("css_unbalanced_braces_or_parens")
    elif not style_text:
        failures.append("missing_inline_css")

    scripts = blocks(html_text, "script")
    if not scripts:
        failures.append("missing_inline_js")
    script_results = []
    for index, script in enumerate(scripts):
        ok, message = node_check(script)
        script_results.append({"index": index, "ok": ok, "message": message[:500]})
        if not ok:
            failures.append(f"script_{index}_node_check_failed")

    missing_patterns = []
    for name, pattern in task.required_patterns:
        if not re.search(pattern, html_text, flags=re.IGNORECASE):
            missing_patterns.append(name)
    if missing_patterns:
        failures.append("missing_patterns:" + ",".join(missing_patterns))

    duplicate_tag_ratio = 0.0
    if parser.tags:
        duplicate_tag_ratio = 1.0 - (len(set(parser.tags)) / len(parser.tags))

    return {
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "char_count": len(html_text),
        "sha256": hashlib.sha256(html_text.encode("utf-8", errors="replace")).hexdigest(),
        "tag_count": len(parser.tags),
        "unique_tags": sorted(tag_set),
        "duplicate_tag_ratio": duplicate_tag_ratio,
        "script_checks": script_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("graph", "cudagraph_none", "eager"), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sites-dir", required=True)
    parser.add_argument("--model", default="/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround")
    parser.add_argument("--task", action="append", choices=[task.task_id for task in TASKS])
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=-1)
    parser.add_argument("--tensor-parallel-size", type=int, default=4)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--max-model-len", type=int, default=4096)
    parser.add_argument("--max-num-batched-tokens", type=int, default=512)
    parser.add_argument("--max-num-seqs", type=int, default=1)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--cache-root", default=None)
    parser.add_argument("--disable-chunked-prefill", action="store_true")
    parser.add_argument("--prompt-format", choices=("chat", "raw"), default="chat")
    parser.add_argument(
        "--keep-thinking-prefix",
        action="store_true",
        help=(
            "Leave MiniMax's chat-template <think> generation prefix open. "
            "By default the harness closes it so the model emits final HTML."
        ),
    )
    parser.add_argument(
        "--no-stop-on-html-end",
        action="store_true",
        help="Do not stop generation at the first </html> tag.",
    )
    parser.add_argument(
        "--allow-control-chars",
        action="store_true",
        help="Allow generated control characters that would invalidate HTML/CSS/JS.",
    )
    parser.add_argument(
        "--system-prompt",
        default=(
            "You are a precise front-end coding assistant. For each task, "
            "return the requested complete HTML document as the final answer. "
            "Do not include prose outside the document."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_env(args.mode, args.cache_root)

    selected = [task for task in TASKS if not args.task or task.task_id in args.task]
    sites_dir = Path(args.sites_dir)
    sites_dir.mkdir(parents=True, exist_ok=True)

    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    cudagraph_mode = "PIECEWISE"
    if args.mode == "cudagraph_none":
        cudagraph_mode = "NONE"
    elif args.mode == "eager":
        cudagraph_mode = "NONE"

    compilation_config = {
        "use_inductor_graph_partition": True,
        "compile_sizes": [1],
        "compile_ranges_endpoints": [args.max_num_batched_tokens],
        "custom_ops": ["none"],
        "cudagraph_mode": cudagraph_mode,
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
        disable_custom_all_reduce=True,
        enable_chunked_prefill=not args.disable_chunked_prefill,
        enable_prefix_caching=False,
        compilation_config=compilation_config,
    )
    init_elapsed_s = time.perf_counter() - init_started

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    control_chars = [
        chr(code)
        for code in [*range(0x00, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20)]
    ]
    control_logit_bias = None
    if not args.allow_control_chars:
        candidates = []
        for char in control_chars:
            candidates.extend((char, " " + char))
        control_token_ids = set()
        for word in candidates:
            for token_id in tokenizer.encode(word, add_special_tokens=False):
                # Do not ban ordinary spaces from the space-prefixed probes.
                if token_id != 32:
                    control_token_ids.add(token_id)
        control_logit_bias = {token_id: -100.0 for token_id in control_token_ids}
    params = SamplingParams(
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        max_tokens=args.max_tokens,
        seed=0,
        stop=None if args.no_stop_on_html_end else ["</html>"],
        include_stop_str_in_output=not args.no_stop_on_html_end,
        stop_token_ids=[200020],
        logit_bias=control_logit_bias,
    )

    records = []
    for task in selected:
        rendered_prompt = task.prompt
        if args.prompt_format == "chat":
            rendered_prompt = tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": args.system_prompt},
                    {"role": "user", "content": task.prompt},
                ],
                tokenize=False,
                add_generation_prompt=True,
            )
            if not args.keep_thinking_prefix and rendered_prompt.endswith("<think>\n"):
                rendered_prompt += "</think>\n\n"
        started = time.perf_counter()
        outputs = llm.generate([rendered_prompt], params)
        elapsed_s = time.perf_counter() - started
        output = outputs[0].outputs[0]
        text = output.text
        html_text, extraction = extract_html(text)
        site_path = sites_dir / f"{args.mode}-{task.task_id}.html"
        raw_path = sites_dir / f"{args.mode}-{task.task_id}.raw.txt"
        site_path.write_text(html_text, encoding="utf-8")
        raw_path.write_text(text, encoding="utf-8")
        validation = validate_site(html_text, task)
        token_ids = list(output.token_ids)
        records.append(
            {
                "task_id": task.task_id,
                "elapsed_s": elapsed_s,
                "generated_tokens": len(token_ids),
                "output_toks_per_second": (
                    len(token_ids) / elapsed_s if elapsed_s > 0 else None
                ),
                "finish_reason": output.finish_reason,
                "token_sha256": hashlib.sha256(
                    ",".join(map(str, token_ids)).encode()
                ).hexdigest(),
                "raw_text_sha256": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
                "prompt_format": args.prompt_format,
                "keep_thinking_prefix": args.keep_thinking_prefix,
                "stop_on_html_end": not args.no_stop_on_html_end,
                "ban_control_chars": not args.allow_control_chars,
                "rendered_prompt_sha256": hashlib.sha256(
                    rendered_prompt.encode("utf-8", errors="replace")
                ).hexdigest(),
                "extraction": extraction,
                "site_path": str(site_path),
                "raw_path": str(raw_path),
                "validation": validation,
                "preview": text[:600],
            }
        )

    passed = all(record["validation"]["passed"] for record in records)
    result = {
        "mode": args.mode,
        "passed": passed,
        "model": args.model,
        "runtime": {
            "tensor_parallel_size": args.tensor_parallel_size,
            "dtype": args.dtype,
            "max_model_len": args.max_model_len,
            "max_num_batched_tokens": args.max_num_batched_tokens,
            "max_num_seqs": args.max_num_seqs,
            "block_size": args.block_size,
            "compilation_config": compilation_config,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "top_k": args.top_k,
            "prompt_format": args.prompt_format,
            "keep_thinking_prefix": args.keep_thinking_prefix,
            "stop_on_html_end": not args.no_stop_on_html_end,
            "ban_control_chars": not args.allow_control_chars,
        },
        "init_elapsed_s": init_elapsed_s,
        "tasks": records,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "mode": args.mode,
        "passed": passed,
        "out": args.out,
        "task_results": [
            {
                "task_id": record["task_id"],
                "passed": record["validation"]["passed"],
                "failures": record["validation"]["failures"],
                "output_toks_per_second": record["output_toks_per_second"],
                "site_path": record["site_path"],
            }
            for record in records
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
