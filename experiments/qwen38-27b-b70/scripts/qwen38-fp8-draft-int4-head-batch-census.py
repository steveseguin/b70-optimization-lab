#!/usr/bin/env python3
"""Batch-invariance census of the R62 draft INT4 vocabulary head (R159):
torch.ops._xpu_C.int4_gemm_w4a16 with the exact packing the R62 patch uses
(group 128, bf16 scales, zero point 8), per-rank shape K=5120, N=124160.
The draft only proposes tokens, so what matters is whether a row's logits
(and its argmax) depend on how many rows share the call."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import torch
import vllm_xpu_kernels._xpu_C  # noqa

DEV = torch.device("xpu:0"); DT = torch.float16
K, N, G = 5120, 124160, 128
MS = [1, 2, 3, 4, 8, 16, 24, 31, 32, 33, 48, 64, 96, 128]


def pack(weight: torch.Tensor):
    num_groups = K // G; packed_k = K // 8
    w = weight.float(); grouped = w.view(N, num_groups, G)
    scales = (grouped.abs().amax(dim=2).clamp_min(1e-10) / 7.0)  # [N, groups]
    q = (torch.round(grouped / scales.unsqueeze(-1)).clamp(-8, 7).to(torch.int32) + 8).view(N, packed_k, 8)
    factors = (1 << (4 * torch.arange(8, device=weight.device, dtype=torch.int32)))
    packed = (q * factors).sum(dim=2).to(torch.int32)  # [N, packed_k]
    return packed.t(), scales.t().to(torch.bfloat16).contiguous(), torch.tensor([8], dtype=torch.int8, device=weight.device)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, required=True); a = ap.parse_args()
    torch.manual_seed(20260903)
    w = (torch.randn((N, K), device=DEV) * 0.02).to(DT)
    qw, sc, zp = pack(w)
    x = torch.randn((128, K), dtype=DT, device=DEV)
    def gemm(t): return torch.ops._xpu_C.int4_gemm_w4a16(t.contiguous(), qw, None, sc, zp, G, None)
    single = torch.cat([gemm(x[i:i + 1]) for i in range(128)]); torch.xpu.synchronize()
    single_arg = single.argmax(dim=-1)
    rows = []
    for M in MS:
        o = gemm(x[:M]); o2 = gemm(x[:M]); perm = torch.randperm(M, device=DEV); o3 = gemm(x[:M][perm]); torch.xpu.synchronize()
        rows.append({"M": M, "equal_single": bool(torch.equal(o, single[:M])), "argmax_equal_single": bool(torch.equal(o.argmax(dim=-1), single_arg[:M])),
                     "repeat_equal": bool(torch.equal(o, o2)), "permuted_equal_single": bool(torch.equal(o3, single[:M][perm])),
                     "max_abs_diff": float((o.float() - single[:M].float()).abs().max())})
        print("int4-head", rows[-1], flush=True)
    res = {"rows": rows, "all_batch_invariant": all(r["equal_single"] and r["permuted_equal_single"] for r in rows), "all_argmax_invariant": all(r["argmax_equal_single"] for r in rows),
           "all_repeat_exact": all(r["repeat_equal"] for r in rows), "first_failing_M": next((r["M"] for r in rows if not r["equal_single"]), None)}
    a.out.write_text(json.dumps(res, indent=1)); print({k: res[k] for k in ("all_batch_invariant", "all_argmax_invariant", "all_repeat_exact", "first_failing_M")})


if __name__ == "__main__":
    main()
