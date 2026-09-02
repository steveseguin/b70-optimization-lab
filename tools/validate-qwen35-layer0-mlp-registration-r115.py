#!/usr/bin/env python3
"""Validate R115 registration inside the actual Qwen3.5 decoder class."""

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
        if isinstance(node, ast.ClassDef) and node.name == "Qwen3_5DecoderLayer"
    ]
    if len(classes) != 1:
        raise SystemExit(f"expected one Qwen3.5 decoder class, found {len(classes)}")
    inits = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    ]
    if len(inits) != 1:
        raise SystemExit(f"expected one Qwen3.5 decoder init, found {len(inits)}")
    init = ast.unparse(inits[0])
    for fragment in (
        "self.layer_idx == 0",
        "self.layer_type == 'linear_attention'",
        "mlp_context_prefix = f'{self.linear_attn.prefix}.r114_mlp'",
        "get_current_vllm_config().compilation_config.static_forward_context",
        "static_context[mlp_context_prefix] = self.mlp",
    ):
        if fragment not in init:
            raise SystemExit(f"Qwen3.5 decoder init is missing: {fragment}")
    if init.index("static_context[mlp_context_prefix] = self.mlp") < init.index(
        "self.mlp = Qwen3NextMLP"
    ):
        raise SystemExit("R115 registration precedes dense MLP construction")
    print("qwen35_layer0_mlp_registration_r115=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
