#!/usr/bin/env python3
"""Fail-closed semantic gate for R118: opaque padded W8A16 GEMM behind an
integer env bucket, default off, used only on the W8A16 branch."""

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
    for required in ("_w8a16_decode_pad_rows", "_xpu_w8a16_padded_gemm",
                     "_xpu_w8a16_padded_gemm_fake"):
        if required not in names:
            raise SystemExit(f"R118 is missing {required}")
    for fragment in (
        'os.environ.get("VLLM_XPU_W8A16_DECODE_PAD_ROWS", "0")',
        "if 0 < rows < pad_rows:",
        "padded = A.new_zeros((pad_rows, A.shape[1]))",
        "torch.ops._xpu_C.fp8_gemm_w8a16(padded, B_t, Bs_t, None)[:rows]",
        'op_name="xpu_w8a16_padded_gemm"',
        "torch.ops.vllm.xpu_w8a16_padded_gemm(",
        "self._decode_pad_rows = _w8a16_decode_pad_rows() if self._use_w8a16 else 0",
    ):
        if fragment not in source:
            raise SystemExit(f"R118 source is missing: {fragment}")
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "XPUFp8BlockScaledMMKernel"]
    if len(classes) != 1:
        raise SystemExit("expected one XPUFp8BlockScaledMMKernel")
    apply = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == "apply_block_scaled_mm"]
    if len(apply) != 1:
        raise SystemExit("expected one apply_block_scaled_mm")
    text = ast.unparse(apply[0])
    if "if self._decode_pad_rows:" not in text or "fp8_gemm(" not in text:
        raise SystemExit("R118 apply_block_scaled_mm shape is wrong")
    print("xpu_w8a16_decode_pad_rows_r118=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
