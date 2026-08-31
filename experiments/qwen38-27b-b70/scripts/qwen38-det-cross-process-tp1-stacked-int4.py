#!/usr/bin/env python3
"""Hash fixed TP1 stacked INT4 runtime-shape outputs across processes."""

import argparse
import hashlib
import json

import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401


SHAPES = {
    "gdn_qkvz_tp1": (5120, 16384),
    "gdn_out_tp1": (6144, 5120),
    "attention_qkv_gate_tp1": (5120, 14336),
    "attention_out_tp1": (6144, 5120),
    "mlp_gate_up_tp1": (5120, 34816),
    "mlp_down_tp1": (17408, 5120),
}


def nt_pack(value: torch.Tensor) -> torch.Tensor:
    return value.t().contiguous().t()


def digest(value: torch.Tensor) -> str:
    return hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--m", type=int, action="append", dest="m_values")
    parser.add_argument("--seed", type=int, default=20260831)
    args = parser.parse_args()
    m_values = args.m_values or [1]
    device = "xpu:0"
    torch.set_num_threads(1)
    rows = []
    for index, (name, (k, n)) in enumerate(SHAPES.items()):
        generator = torch.Generator(device="cpu").manual_seed(args.seed + index)
        qweight = nt_pack(torch.randint(-(2**31), 2**31 - 1, (k // 8, n), dtype=torch.int32, generator=generator)).to(device)
        scales = torch.randn(k // 128, n, dtype=torch.float16, generator=generator).abs().to(device)
        zero = torch.tensor([8], dtype=torch.int8, device=device)
        for m in m_values:
            xgen = torch.Generator(device="cpu").manual_seed(args.seed + index * 1000 + m)
            x = torch.randn(m, k, dtype=torch.float16, generator=xgen).to(device)
            first = torch.ops._xpu_C.int4_gemm_w4a16(x, qweight, None, scales, zero, 128, None)
            torch.xpu.synchronize(); first = first.clone()
            second = torch.ops._xpu_C.int4_gemm_w4a16(x, qweight, None, scales, zero, 128, None)
            torch.xpu.synchronize()
            rows.append({"name":name,"m":m,"k":k,"n":n,
                         "within_process_exact":bool(torch.equal(first,second)),"sha256":digest(first)})
            del x, first, second
        del qweight, scales, zero
        torch.xpu.empty_cache()
    print(json.dumps({"seed":args.seed,"m_values":m_values,"results":rows},sort_keys=True))


if __name__ == "__main__":
    main()
