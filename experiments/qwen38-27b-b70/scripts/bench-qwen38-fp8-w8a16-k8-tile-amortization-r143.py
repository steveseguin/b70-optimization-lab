#!/usr/bin/env python3
"""Run the sealed R142 gate for one preregistered R143 geometry."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


BASE = Path(__file__).with_name(
    "bench-qwen38-fp8-w8a16-k8-split-reduction-r142.py"
)
source = BASE.read_text()
source = source.replace(
    '"schema": "neural.download.qwen38-fp8-w8a16-k8-split-r142.v1"',
    '"schema": "neural.download.qwen38-fp8-w8a16-k8-tile-r143.v1"',
)
old_candidate = '''        "candidate": {
            "tile_mnk": [16, 64, 512],
            "subgroup_layout_mnk": [1, 4, 8],
            "k_interleave": 64,
            "reduction_order": "ascending",
            "weight_layout": "production NT view [1,K,N], strides [*,1,K]",
        },'''
new_candidate = '''        "candidate": {
            "geometry": os.environ["R143_GEOMETRY"],
            **R143_GEOMETRIES[os.environ["R143_GEOMETRY"]],
            "k_interleave": 64,
            "reduction_order": "ascending",
            "weight_layout": "production NT view [1,K,N], strides [*,1,K]",
        },'''
if source.count(old_candidate) != 1:
    raise RuntimeError(f"expected one candidate block in sealed harness {BASE}")
source = source.replace(old_candidate, new_candidate)

spec = importlib.util.spec_from_loader("r143_k8_tile_bench", loader=None)
if spec is None:
    raise RuntimeError("cannot construct R143 benchmark module")
bench = importlib.util.module_from_spec(spec)
bench.__file__ = str(BASE)
bench.os = os
bench.R143_GEOMETRIES = {
    "m16_n128_sg1x2x8": {
        "tile_mnk": [16, 128, 512],
        "subgroup_layout_mnk": [1, 2, 8],
        "work_items": 256,
    },
    "m32_n64_sg1x2x8": {
        "tile_mnk": [32, 64, 512],
        "subgroup_layout_mnk": [1, 2, 8],
        "work_items": 256,
    },
    "m64_n64_sg2x2x8": {
        "tile_mnk": [64, 64, 512],
        "subgroup_layout_mnk": [2, 2, 8],
        "work_items": 512,
    },
    "m64_n128_sg2x2x8": {
        "tile_mnk": [64, 128, 512],
        "subgroup_layout_mnk": [2, 2, 8],
        "work_items": 512,
    },
}
geometry = os.environ.get("R143_GEOMETRY")
if geometry not in bench.R143_GEOMETRIES:
    choices = ", ".join(bench.R143_GEOMETRIES)
    raise RuntimeError(f"R143_GEOMETRY must be one of: {choices}")
exec(compile(source, str(BASE), "exec"), bench.__dict__)


if __name__ == "__main__":
    raise SystemExit(bench.main())
