#!/usr/bin/env python3
"""Add every production Qwen3.8 TP2 W8A16 shape to the R123 screen."""

from __future__ import annotations

import importlib.util
from pathlib import Path


BASE = Path("/run/bench-pinned-jit-base.py")
spec = importlib.util.spec_from_file_location("r123_pinned_jit_base", BASE)
if spec is None or spec.loader is None:
    raise SystemExit(f"cannot load {BASE}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.SHAPES = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
}

raise SystemExit(module.main())
