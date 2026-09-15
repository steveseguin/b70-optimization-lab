#!/usr/bin/env python3
"""W8A16 GEMM repeatability under input-pointer alignment and allocator state.

Operator diagnostic only. A one-card MTP0 server returned a different 128-token
continuation for the same 2,048-token prompt when that prompt ran later in the
session. This asks whether fp8_gemm_w8a16 gives bitwise-identical rows for the
same values when (a) the input starts at a different byte offset inside its
allocation, or (b) other allocations have shifted the caching allocator, for row
counts on both sides of the fixed-K limit (512), at one-card and TP2 shapes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

BLOCK = 128
SHAPES = {
    "tp1_gdn_in_proj_qkvz": (5120, 16384),
    "tp1_attn_o_proj": (6144, 5120),
    "tp1_mlp_gate_up_proj": (5120, 34816),
    "tp1_mlp_down_proj": (17408, 5120),
    "tp2_mlp_gate_up_proj": (5120, 17408),
    "tp2_mlp_down_proj": (8704, 5120),
}
ROWS = [1, 6, 128, 512, 513, 1024, 2048, 4096]
OFFSETS = [1, 2, 3, 7, 8, 16, 33]


def gemm(a, w, s):
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, w.t(), s, None)


def shifted(a, offset):
    flat = torch.empty(a.numel() + offset, dtype=a.dtype, device=a.device)
    view = flat[offset:].view(a.shape)
    view.copy_(a)
    return view


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20260915)
    args = ap.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    dev = torch.device("xpu:0")
    gen = torch.Generator().manual_seed(args.seed)
    report = {"schema": "neural.download.qwen38-fp8-gemm-alignment-census.v1",
              "classification": "operator-diagnostic-only", "torch": torch.__version__, "shapes": {}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for name, (k, n) in SHAPES.items():
        w = (torch.randn((n, k), generator=gen) * 0.05).to(torch.float8_e4m3fn).to(dev)
        s = (torch.rand((k // BLOCK, n // BLOCK), generator=gen) * 0.02 + 0.005).to(dev).contiguous()
        entry = {}
        for m in ROWS:
            a = torch.randn((m, k), generator=gen).to(torch.float16).to(dev)
            ref = gemm(a, w, s).clone()
            same_repeat = all(torch.equal(gemm(a, w, s), ref) for _ in range(3))
            offset_equal = {}
            for off in OFFSETS:
                offset_equal[off] = bool(torch.equal(gemm(shifted(a, off), w, s), ref))
            churn = []
            for i in range(6):
                junk = [torch.empty(int(x), dtype=torch.float16, device=dev) for x in (37 * (i + 1), 4099 * (i + 3), m * k // 3 + i)]
                churn.append(bool(torch.equal(gemm(a.clone(), w, s), ref)))
                del junk
            bad = [o for o, ok in offset_equal.items() if not ok]
            entry[m] = {"repeat_equal": same_repeat, "offset_equal": offset_equal,
                        "allocator_churn_equal": churn,
                        "all_equal": same_repeat and not bad and all(churn)}
            del a, ref
        torch.xpu.empty_cache()
        report["shapes"][name] = entry
        args.out.write_text(json.dumps(report, indent=1))
        print(name, {m: ("ok" if v["all_equal"] else
                         f"DIFF rep={v['repeat_equal']} offs={[o for o, ok in v['offset_equal'].items() if not ok]} churn={v['allocator_churn_equal']}")
                     for m, v in entry.items()}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
