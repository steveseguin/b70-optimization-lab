#!/usr/bin/env python3
"""Cross-digest and time a scheduling-only oneDNN strategy variant."""

from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path(__file__).with_name("bench-qwen38-fp8-w8a16-pinned-jit-strategy.py")
source = BASE.read_text()
needle = '''        {
            "row0_classes_by_m": sorted('''
replacement = '''        {
            "output_sha256_by_m": {
                str(m): digest(output) for m, output in outputs.items()
            },
            "row0_sha256_by_m": {
                str(m): digest(output[:1]) for m, output in outputs.items()
            },
            "row0_classes_by_m": sorted('''
if source.count(needle) != 1:
    raise RuntimeError(f"expected one report-update insertion point in {BASE}")
source = source.replace(needle, replacement)

spec = importlib.util.spec_from_loader("r136_scheduling_only_strategy", loader=None)
if spec is None:
    raise RuntimeError("cannot construct R136 benchmark module")
bench = importlib.util.module_from_spec(spec)
bench.__file__ = str(BASE)
exec(compile(source, str(BASE), "exec"), bench.__dict__)

bench.SHAPES = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
}
bench.TIMED_MS = [64, 128, 168, 256]


if __name__ == "__main__":
    raise SystemExit(bench.main())
