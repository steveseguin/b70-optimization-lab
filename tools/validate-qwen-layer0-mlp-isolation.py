#!/usr/bin/env python3
"""Validate that the R111 layer-0 MLP treatment is live and metadata-driven."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


def functions_named(tree: ast.AST, name: str) -> list[ast.FunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


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
    forwards = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "forward"
    ]
    if len(forwards) != 1:
        raise SystemExit(f"expected one decoder forward, found {len(forwards)}")
    forward = ast.unparse(forwards[0])
    call = "torch.ops.vllm.qwen_layer0_mlp_prefill_isolated_xpu"
    required_forward = (
        call,
        "VLLM_XPU_ISOLATE_LAYER0_MLP_PREFILL_REQUESTS",
        "self.layer_idx == 0",
        "self.layer_type == 'linear_attention'",
    )
    for fragment in required_forward:
        if fragment not in forward:
            raise SystemExit(f"decoder forward is missing: {fragment}")
    if forward.count(call) != 1:
        raise SystemExit(f"expected one live MLP-isolation call, found {forward.count(call)}")

    helpers = functions_named(tree, "_request_isolated_qwen_layer0_mlp_prefill_xpu")
    if len(helpers) != 1:
        raise SystemExit(f"expected one treatment helper, found {len(helpers)}")
    helper = ast.unparse(helpers[0])
    for fragment in (
        "GDNAttentionMetadata",
        "metadata.num_prefills == 1",
        "metadata.prefill_query_start_loc",
        "mlp(hidden_states[start:stop])",
        "torch.cat",
    ):
        if fragment not in helper:
            raise SystemExit(f"treatment helper is missing: {fragment}")

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
                and keyword.value.value == "qwen_layer0_mlp_prefill_isolated_xpu"
            ):
                registrations += 1
    if registrations != 1:
        raise SystemExit(f"expected one treatment registration, found {registrations}")
    print("qwen_layer0_mlp_request_isolation_callsite=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
