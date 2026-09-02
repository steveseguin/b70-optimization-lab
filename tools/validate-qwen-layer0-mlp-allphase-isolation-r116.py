#!/usr/bin/env python3
"""Fail-closed semantic gate for Qwen layer-0 all-phase MLP isolation."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


def one_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise SystemExit(f"expected one {name} function, found {len(matches)}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    tree = ast.parse(source, args.source)

    helper = ast.unparse(
        one_function(tree, "_request_isolated_qwen_layer0_mlp_prefill_xpu")
    )
    required = (
        "num_non_spec = metadata.num_prefills + metadata.num_decodes",
        "num_spec = metadata.num_spec_decodes",
        "num_requests = num_non_spec + num_spec",
        "metadata.spec_query_start_loc",
        "metadata.non_spec_query_start_loc",
        "metadata.prefill_query_start_loc",
        "metadata.spec_sequence_masks",
        "sum((bool(value) for value in mask_values)) != num_spec",
        "boundaries[-1] != hidden_states.shape[0]",
        "R116 layer-0 MLP multi-prefill treatment executed",
        "R116 layer-0 MLP multi-request decode-or-mixed treatment executed",
        "mlp(hidden_states[start:stop])",
    )
    for fragment in required:
        if fragment not in helper:
            raise SystemExit(f"R116 helper is missing: {fragment}")
    forbidden = (
        "cache-c000",
        "index-c001",
        "metadata.num_prefills == 2",
        "if not pure_prefill or metadata.num_prefills == 1",
    )
    for fragment in forbidden:
        if fragment in helper:
            raise SystemExit(f"R116 helper contains forbidden policy: {fragment}")

    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Qwen3NextDecoderLayer"
    ]
    if len(classes) != 1:
        raise SystemExit(
            f"expected one Qwen3NextDecoderLayer, found {len(classes)}"
        )
    forwards = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "forward"
    ]
    if len(forwards) != 1:
        raise SystemExit(f"expected one decoder forward, found {len(forwards)}")
    forward = ast.unparse(forwards[0])
    for fragment in (
        "VLLM_XPU_ISOLATE_LAYER0_MLP_PREFILL_REQUESTS",
        "self.layer_idx == 0",
        "self.layer_type == 'linear_attention'",
        "torch.ops.vllm.qwen_layer0_mlp_prefill_isolated_xpu",
    ):
        if fragment not in forward:
            raise SystemExit(f"decoder call site is missing: {fragment}")

    print("qwen_layer0_mlp_allphase_isolation_r116=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
