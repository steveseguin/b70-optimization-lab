#!/usr/bin/env python3
"""Census Qwen3.6 vLLM/XPU AOT op boundaries.

The Qwen3.6 Quark W8A8 path uses custom vLLM/XPU ops inside generated graph
code. Older c10d-focused analyzers miss the promoted `torch.ops.vllm.all_reduce`
route, so this script records the compiled op mix and representative local
neighborhoods for future exact fusion work.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


OP_PATTERNS: dict[str, str] = {
    "vllm_all_reduce": r"torch\.ops\.vllm\.all_reduce(?:\.default)?",
    "vllm_all_reduce_inplace": r"torch\.ops\.vllm\.all_reduce_inplace(?:\.default)?",
    "int8_gemm_w8a8": r"torch\.ops\._xpu_C\.int8_gemm_w8a8(?:\.default)?",
    "per_token_quant_int8": r"torch\.ops\._xpu_C\.per_token_quant_int8_xpu(?:\.default)?",
    "moe_forward": r"torch\.ops\.vllm\.moe_forward(?:\.default)?\(",
    "moe_forward_shared": r"torch\.ops\.vllm\.moe_forward_shared(?:\.default)?",
    "moe_shared_add_allreduce": r"torch\.ops\.vllm\.moe_shared_add_allreduce(?:\.default)?",
    "gdn_attention_core": r"torch\.ops\.vllm\.gdn_attention_core_xpu(?:\.default)?",
    "unified_attention": r"torch\.ops\.vllm\.unified_attention_with_output(?:\.default)?",
    "unified_kv_cache_update": r"torch\.ops\.vllm\.unified_kv_cache_update(?:\.default)?",
    "rms_norm": r"torch\.ops\.vllm_ir\.rms_norm(?:\.default)?",
    "fused_add_rms_norm": r"torch\.ops\._C\.fused_add_rms_norm(?:\.default)?",
}

ASSIGN_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::\s*\"(?P<shape>[^\"]+)\")?\s*=\s*(?P<expr>.*)$"
)
FX_COMMENT_RE = re.compile(
    r"^\s*#\s+%(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:Tensor\s*\"(?P<shape>[^\"]+)\".*)?"
    r"=\s*call_function\[target=(?P<target>[^\]]+)\]"
)
FILE_COMMENT_RE = re.compile(r"^\s*# File: (?P<file>.*), code: (?P<code>.*)$")


def compact_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def compact_file_comment(line: str) -> str:
    line = line.replace("/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/", "")
    line = line.replace("/home/steve/src/vllm/", "")
    return line


def iter_python_files(root: Path) -> Iterable[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def op_for_line(line: str, compiled: dict[str, re.Pattern[str]]) -> str | None:
    for name, pattern in compiled.items():
        if pattern.search(line):
            return name
    return None


def shape_from_line(line: str) -> str | None:
    if match := ASSIGN_RE.match(line):
        return match.group("shape")
    if match := FX_COMMENT_RE.match(line):
        return match.group("shape")
    return None


def previous_file_comment(lines: list[str], idx: int) -> str | None:
    for back in range(idx - 1, max(-1, idx - 28), -1):
        match = FILE_COMMENT_RE.match(lines[back])
        if match:
            return compact_file_comment(
                f"{match.group('file')}: {match.group('code').strip()}"
            )
    return None


def sample_window(lines: list[str], idx: int, before: int, after: int) -> list[str]:
    start = max(0, idx - before)
    stop = min(len(lines), idx + after + 1)
    out: list[str] = []
    for line_no, text in enumerate(lines[start:stop], start=start + 1):
        out.append(f"{line_no}: {text.rstrip()}")
    return out


def nearby_ops(
    lines: list[str],
    idx: int,
    compiled: dict[str, re.Pattern[str]],
    *,
    radius: int,
) -> list[str]:
    ops: list[str] = []
    start = max(0, idx - radius)
    stop = min(len(lines), idx + radius + 1)
    for other_idx in range(start, stop):
        name = op_for_line(lines[other_idx], compiled)
        if name:
            ops.append(f"{name}@{other_idx - idx:+d}")
    return ops


def infer_boundary(op_name: str, line: str, file_context: str | None, neighbors: list[str]) -> str:
    text = " ".join([line, file_context or "", " ".join(neighbors)])
    if op_name == "vllm_all_reduce":
        if "embedding" in text:
            return "embedding_hidden"
        if "moe_forward" in text:
            return "moe_hidden"
        if "unified_attention" in text or "o_proj" in text:
            return "attention_hidden"
        if "rms_norm" in text:
            return "hidden_to_rms"
        return "hidden_collective"
    if op_name == "int8_gemm_w8a8":
        if "qkvz" in text:
            return "gdn_in_proj_qkvz"
        if "in_proj_ba" in text:
            return "gdn_in_proj_ba"
        if "out_proj" in text:
            return "gdn_or_attention_out_proj"
        if "qkv_proj" in text:
            return "attention_qkv_proj"
        if "gate_up_proj" in text:
            return "mlp_gate_up_proj"
        if "down_proj" in text:
            return "mlp_down_proj"
        return "dense_int8_gemm"
    if op_name == "per_token_quant_int8":
        if "gdn_linear_attn.py" in text:
            return "gdn_quant"
        if "fused_moe" in text or "moe" in text:
            return "moe_quant"
        return "dense_quant"
    if op_name in {"moe_forward", "moe_forward_shared", "moe_shared_add_allreduce"}:
        return "moe_custom_op"
    if op_name == "gdn_attention_core":
        return "gdn_core"
    if op_name == "rms_norm":
        if "linear_attn" in text or "gdn" in text:
            return "gdn_rms"
        if "self_attn" in text:
            return "attention_qk_rms_or_layernorm"
        return "rms_norm"
    return op_name


def census(root: Path, *, sample_limit: int, window_before: int, window_after: int) -> dict[str, object]:
    compiled = {name: re.compile(pattern) for name, pattern in OP_PATTERNS.items()}
    op_counts: Counter[str] = Counter()
    op_counts_by_form: dict[str, Counter[str]] = {
        "actual_call": Counter(),
        "fx_comment": Counter(),
    }
    op_shape_counts: dict[str, Counter[str]] = defaultdict(Counter)
    op_boundary_counts: dict[str, Counter[str]] = defaultdict(Counter)
    files_with_ops: Counter[str] = Counter()
    samples: dict[str, list[dict[str, object]]] = defaultdict(list)
    actual_samples: dict[str, list[dict[str, object]]] = defaultdict(list)
    comment_samples: dict[str, list[dict[str, object]]] = defaultdict(list)
    sequences: Counter[str] = Counter()
    py_files = list(iter_python_files(root))

    for path in py_files:
        rel = compact_path(path, root)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        file_hit = False
        for idx, line in enumerate(lines):
            op_name = op_for_line(line, compiled)
            if not op_name:
                continue
            file_hit = True
            form = "fx_comment" if line.lstrip().startswith("#") else "actual_call"
            op_counts[op_name] += 1
            op_counts_by_form[form][op_name] += 1
            shape = shape_from_line(line) or "unknown"
            op_shape_counts[op_name][shape] += 1
            neighbors = nearby_ops(lines, idx, compiled, radius=10)
            sequence = " -> ".join(op.split("@", 1)[0] for op in neighbors)
            if sequence and form == "actual_call":
                sequences[sequence] += 1
            file_context = previous_file_comment(lines, idx)
            boundary = infer_boundary(op_name, line, file_context, neighbors)
            op_boundary_counts[op_name][boundary] += 1
            sample = {
                "file": rel,
                "line": idx + 1,
                "form": form,
                "shape": shape,
                "boundary": boundary,
                "fileContext": file_context,
                "nearbyOps": neighbors,
                "source": line.strip(),
                "window": sample_window(lines, idx, window_before, window_after),
            }
            if len(samples[op_name]) < sample_limit:
                samples[op_name].append(sample)
            if form == "actual_call" and len(actual_samples[op_name]) < sample_limit:
                actual_samples[op_name].append(sample)
            if form == "fx_comment" and len(comment_samples[op_name]) < sample_limit:
                comment_samples[op_name].append(sample)
        if file_hit:
            files_with_ops[rel] += 1

    return {
        "cache": str(root),
        "pythonFilesScanned": len(py_files),
        "opPatterns": OP_PATTERNS,
        "opCounts": dict(op_counts.most_common()),
        "opCountsByForm": {
            form: dict(counter.most_common())
            for form, counter in op_counts_by_form.items()
        },
        "opShapeCounts": {
            name: dict(counter.most_common(20))
            for name, counter in sorted(op_shape_counts.items())
        },
        "opBoundaryCounts": {
            name: dict(counter.most_common())
            for name, counter in sorted(op_boundary_counts.items())
        },
        "filesWithOps": dict(files_with_ops.most_common(50)),
        "nearbyOpSequences": dict(sequences.most_common(50)),
        "samples": dict(samples),
        "actualSamples": dict(actual_samples),
        "commentSamples": dict(comment_samples),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("--sample-limit", type=int, default=8)
    parser.add_argument("--window-before", type=int, default=5)
    parser.add_argument("--window-after", type=int, default=8)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if not args.cache.is_dir():
        raise SystemExit(f"cache directory not found: {args.cache}")
    result = census(
        args.cache,
        sample_limit=args.sample_limit,
        window_before=args.window_before,
        window_after=args.window_after,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
