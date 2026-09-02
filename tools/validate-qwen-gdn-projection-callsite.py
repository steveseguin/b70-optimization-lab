#!/usr/bin/env python3
"""Fail unless the Qwen GDN XPU projection treatment is wired live."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


CLASS_NAME = "QwenGatedDeltaNetAttention"
FUNCTION_NAME = "forward_xpu"
CUSTOM_OP = "torch.ops.vllm.qwen_gdn_projection_prefill_isolated_xpu"
ENV_GATE = "VLLM_XPU_GDN_ISOLATE_PROJECTION_PREFILL_REQUESTS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    tree = ast.parse(args.source.read_text(encoding="utf-8"), args.source)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == CLASS_NAME
    ]
    if len(classes) != 1:
        raise SystemExit(f"expected one {CLASS_NAME}, found {len(classes)}")
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == FUNCTION_NAME
    ]
    if len(methods) != 1:
        raise SystemExit(f"expected one {FUNCTION_NAME}, found {len(methods)}")

    body = ast.unparse(methods[0])
    if body.count(CUSTOM_OP) != 1:
        raise SystemExit(
            f"{FUNCTION_NAME} must contain exactly one live {CUSTOM_OP} call"
        )
    if ENV_GATE not in body:
        raise SystemExit(f"{FUNCTION_NAME} is missing environment gate {ENV_GATE}")

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
                and keyword.value.value
                == "qwen_gdn_projection_prefill_isolated_xpu"
            ):
                registrations += 1
    if registrations != 1:
        raise SystemExit(
            "expected exactly one qwen_gdn_projection_prefill_isolated_xpu "
            f"registration, found {registrations}"
        )

    print("qwen_gdn_projection_callsite=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
