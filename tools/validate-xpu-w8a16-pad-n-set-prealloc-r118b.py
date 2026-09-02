#!/usr/bin/env python3
"""Fail-closed semantic gate for R118b: padded W8A16 GEMM restricted to an
explicit output-width set, using a persistent zero-initialised buffer."""

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
    for required in ("_w8a16_decode_pad_rows", "_w8a16_pad_n_set",
                     "_xpu_w8a16_padded_gemm", "_xpu_w8a16_padded_gemm_fake"):
        if required not in names:
            raise SystemExit(f"R118b is missing {required}")
    for fragment in (
        'os.environ.get("VLLM_XPU_W8A16_DECODE_PAD_ROWS", "0")',
        'os.environ.get("VLLM_XPU_W8A16_PAD_N_SET", "")',
        "selected = not _W8A16_PAD_N_SET or n in _W8A16_PAD_N_SET",
        "if selected and 0 < rows < pad_rows:",
        "buf = _W8A16_PAD_BUFFERS.get(key)",
        "buf[:rows].copy_(A)",
        "torch.ops._xpu_C.fp8_gemm_w8a16(buf, B_t, Bs_t, None)[:rows]",
        "R118 W8A16 padded GEMM executed",
        'op_name="xpu_w8a16_padded_gemm"',
        "torch.ops.vllm.xpu_w8a16_padded_gemm(",
        "self._decode_pad_rows = _w8a16_decode_pad_rows() if self._use_w8a16 else 0",
    ):
        if fragment not in source:
            raise SystemExit(f"R118b source is missing: {fragment}")
    if "padded = A.new_zeros((pad_rows, A.shape[1]))" in source:
        raise SystemExit("R118b must not allocate a pad buffer per call")
    print("xpu_w8a16_pad_n_set_prealloc_r118b=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
