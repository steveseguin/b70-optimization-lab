#!/usr/bin/env python3
"""Validate that the R110 decoder trace is wired into the compiled forward."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    tree = ast.parse(args.source.read_text(encoding="utf-8"), args.source)

    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Qwen3NextDecoderLayer"
    ]
    if len(classes) != 1:
        raise SystemExit(f"expected one decoder class, found {len(classes)}")
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "forward"
    ]
    if len(methods) != 1:
        raise SystemExit(f"expected one decoder forward, found {len(methods)}")
    body = ast.unparse(methods[0])
    call = "torch.ops.vllm.qwen_decoder_boundary_trace_xpu"
    if body.count(call) != 8:
        raise SystemExit(f"expected eight live trace calls, found {body.count(call)}")
    if "VLLM_XPU_DECODER_BOUNDARY_TRACE_FILE" not in body:
        raise SystemExit("decoder forward is missing the R110 environment gate")

    registrations = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if ast.unparse(node.func) != "direct_register_custom_op":
            continue
        for keyword in node.keywords:
            if (
                keyword.arg == "op_name"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == "qwen_decoder_boundary_trace_xpu"
            ):
                registrations += 1
    if registrations != 1:
        raise SystemExit(f"expected one trace registration, found {registrations}")
    print("qwen_decoder_boundary_trace_callsite=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
