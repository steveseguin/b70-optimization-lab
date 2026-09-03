#!/usr/bin/env python3
"""Fail-closed semantic gate for R149: env-gated (<=N-row) chunked lm_head apply,
default off, XPU only, inside LogitsProcessor._apply_head."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    tree = ast.parse(source, args.source)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    if "_xpu_lm_head_chunk_rows" not in names:
        raise SystemExit("R149 is missing _xpu_lm_head_chunk_rows")
    for fragment in (
        'os.environ.get("VLLM_XPU_LM_HEAD_CHUNK_ROWS", "0")',
        "return rows if rows > 0 else 0",
        'if chunk_rows > 0 and hidden_states.device.type == "xpu":',
        "if flat.shape[0] > chunk_rows:",
        "R149 lm_head chunked apply executed",
        "for i in range(0, flat.shape[0], chunk_rows)",
        "return torch.cat(parts, dim=0).reshape(",
    ):
        if fragment not in source:
            raise SystemExit(f"R149 source is missing: {fragment}")
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LogitsProcessor"]
    if len(classes) != 1:
        raise SystemExit("expected one LogitsProcessor")
    apply = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == "_apply_head"]
    if len(apply) != 1:
        raise SystemExit("expected one _apply_head")
    text = ast.unparse(apply[0])
    if text.count("_xpu_lm_head_chunk_rows()") != 1:
        raise SystemExit("R149 chunk gate must be read exactly once in _apply_head")
    print("R149 lm_head chunk-rows gate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
