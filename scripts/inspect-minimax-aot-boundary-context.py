#!/usr/bin/env python3
"""Inspect MiniMax AOT collective boundary context.

This is a companion to ``census-minimax-aot-computation-graph.py``. The census
checks that the expected TP collectives are present; this script extracts the
operation window around each ``all_reduce -> wait_tensor`` pair so source-level
fusion work can target the real backend boundary without adding synchronized
runtime timers.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


ALLREDUCE_RE = re.compile(
    r"^\s*(?P<name>all_reduce(?:_(?P<idx>\d+))?): "
    r"\"(?P<shape>[^\"]+)\" = "
    r"(?P<op>torch\.ops\.(?:_c10d_functional|vllm)\.all_reduce)"
)
WAIT_RE = re.compile(
    r"^\s*(?P<name>wait_tensor(?:_(?P<idx>\d+))?): "
    r"\"(?P<shape>[^\"]+)\" = torch\.ops\._c10d_functional\.wait_tensor"
    r"\((?P<input>all_reduce(?:_\d+)?)\)"
)
ASSIGN_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*): \"(?P<shape>[^\"]+)\" = "
    r"(?P<expr>.*)$"
)


def category_for_index(idx: int | None, shape: str = "") -> str:
    # Newer promoted XPU graphs route collectives through torch.ops.vllm and
    # names may repeat inside generated submodules, so the all_reduce_N pattern
    # is not always available. Shape still separates Q/K variance from hidden
    # state collectives; the two hidden-state sites then need context review.
    compact_shape = shape.replace(" ", "")
    if compact_shape.endswith(",2]"):
        return "qk_rms_variance"
    if compact_shape.endswith(",3072]"):
        return "hidden_state_unknown"
    if idx is None:
        return "embedding_hidden"
    mod = idx % 3
    if mod == 1:
        return "qk_rms_variance"
    if mod == 2:
        return "attention_o_proj_hidden"
    return "moe_hidden"


def op_kind(expr: str) -> str:
    if "copy_" in expr:
        return "copy"
    if "torch.ops._C" in expr or "torch.ops.vllm" in expr:
        return "custom_op"
    if "rms" in expr.lower() or "norm" in expr.lower():
        return "norm"
    if "linear" in expr.lower() or "matmul" in expr.lower() or "mm(" in expr:
        return "linear"
    if "torch.ops" in expr:
        return "torch_op"
    if ".reshape" in expr or ".view" in expr:
        return "view"
    return "python_expr"


def find_graphs(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.glob("**/rank_*_0/backbone/computation_graph.py"))


def inspect_file(path: Path, window: int) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    waits_by_input: dict[str, tuple[int, str, str]] = {}
    for line_no, line in enumerate(lines, start=1):
        match = WAIT_RE.match(line)
        if match:
            waits_by_input[match.group("input")] = (
                line_no,
                match.group("name"),
                match.group("shape"),
            )

    entries: list[dict[str, object]] = []
    for line_no, line in enumerate(lines, start=1):
        match = ALLREDUCE_RE.match(line)
        if not match:
            continue
        idx_text = match.group("idx")
        idx = int(idx_text) if idx_text is not None else None
        allreduce_name = match.group("name")
        wait_line, wait_name, wait_shape = waits_by_input.get(
            allreduce_name, (None, None, None)
        )
        context: list[dict[str, object]] = []
        anchor_line = wait_line if wait_line is not None else line_no
        for ctx_line_no in range(
            anchor_line + 1, min(len(lines), anchor_line + window) + 1
        ):
            raw = lines[ctx_line_no - 1]
            if not raw.strip():
                continue
            assign = ASSIGN_RE.match(raw)
            if assign:
                expr = assign.group("expr")
                context.append(
                    {
                        "line": ctx_line_no,
                        "name": assign.group("name"),
                        "shape": assign.group("shape"),
                        "kind": op_kind(expr),
                        "expr": expr[:220],
                    }
                )
            else:
                stripped = raw.strip()
                context.append(
                    {
                        "line": ctx_line_no,
                        "kind": "other",
                        "expr": stripped[:220],
                    }
                )
        entries.append(
            {
                "allreduce": allreduce_name,
                "index": idx,
                "category": category_for_index(idx, match.group("shape")),
                "shape": match.group("shape"),
                "op": match.group("op"),
                "allreduce_line": line_no,
                "wait": wait_name,
                "wait_shape": wait_shape,
                "wait_line": wait_line,
                "first_context_kind": context[0]["kind"] if context else None,
                "context": context,
            }
        )

    category_counter = Counter(str(entry["category"]) for entry in entries)
    first_context_counter = Counter(
        f"{entry['category']} -> {entry['first_context_kind']}"
        for entry in entries
        if entry["first_context_kind"] is not None
    )
    return {
        "file": str(path),
        "allreduce_count": len(entries),
        "by_category": dict(sorted(category_counter.items())),
        "first_context_kind": dict(sorted(first_context_counter.items())),
        "examples": entries[:4] + entries[-4:] if len(entries) > 8 else entries,
        "entries": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Cache root or computation_graph.py")
    parser.add_argument("--window", type=int, default=12)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    files = find_graphs(args.path)
    results = [inspect_file(path, args.window) for path in files]
    aggregate_categories: Counter[str] = Counter()
    aggregate_first_kinds: Counter[str] = Counter()
    for result in results:
        aggregate_categories.update(result["by_category"])  # type: ignore[arg-type]
        aggregate_first_kinds.update(result["first_context_kind"])  # type: ignore[arg-type]

    output = {
        "path": str(args.path),
        "rank_file_count": len(results),
        "window": args.window,
        "aggregate": {
            "allreduce_count": sum(int(result["allreduce_count"]) for result in results),
            "by_category": dict(sorted(aggregate_categories.items())),
            "first_context_kind": dict(sorted(aggregate_first_kinds.items())),
        },
        "ranks": results,
    }
    text = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
