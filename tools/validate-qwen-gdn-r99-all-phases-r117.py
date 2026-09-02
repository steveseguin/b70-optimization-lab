#!/usr/bin/env python3
"""Fail-closed semantic gate for R117: the Qwen GDN gated norm must run the
retained R99 lowering for every live request count (no R97 arm selection)."""

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
    tree = ast.parse(args.source.read_text(encoding="utf-8"), args.source)

    selector = one_function(tree, "_xpu_qwen_gdn_row_stable_rmsnorm_gated")
    calls = [
        node
        for node in ast.walk(selector)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl"
    ]
    if len(calls) != 2:
        raise SystemExit(f"expected two impl calls in the selector, found {len(calls)}")
    for call in calls:
        keywords = {kw.arg: kw.value for kw in call.keywords}
        value = keywords.get("multi_request")
        if not (isinstance(value, ast.Constant) and value.value is False):
            raise SystemExit("R117 requires multi_request=False on every impl call")
    text = ast.unparse(selector)
    for fragment in (
        "R117 Qwen GDN live-metadata multi-request R99 arm executed",
        "R117 Qwen GDN live-metadata single-request R99 arm executed",
        "R101 Qwen GDN metadata-free profile R99 arm executed",
        "request_count < 1",
    ):
        if fragment not in text:
            raise SystemExit(f"R117 selector is missing: {fragment}")
    for fragment in (
        "multi_request = request_count > 1",
        "R97 arm executed",
        "cache-c000",
        "index-c001",
    ):
        if fragment in text:
            raise SystemExit(f"R117 selector contains forbidden text: {fragment}")
    # The R97 implementation stays in the file but must be unreachable.
    impl = one_function(tree, "_xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl")
    if "if multi_request:" not in ast.unparse(impl):
        raise SystemExit("R117 expects the unchanged R100 impl body")
    print("qwen_gdn_r99_all_phases_r117=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
