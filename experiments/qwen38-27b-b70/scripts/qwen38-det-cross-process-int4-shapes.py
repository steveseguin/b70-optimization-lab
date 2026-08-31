#!/usr/bin/env python3
"""Hash fixed INT4 production-shape outputs for cross-process comparison."""

import argparse
import hashlib
import json

import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401


SHAPES = {
    "gdn_qkv_tp2": (5120, 5120),
    "gdn_z_tp2": (5120, 3072),
    "gdn_out_tp2": (3072, 5120),
    "mlp_gate_up_tp2": (5120, 8704),
    "mlp_down_tp2": (8704, 5120),
    "attention_q_tp2": (5120, 3072),
    "attention_kv_tp2": (5120, 512),
    "attention_out_tp2": (3072, 5120),
}


def nt_pack(value: torch.Tensor) -> torch.Tensor:
    return value.t().contiguous().t()


def digest(value: torch.Tensor) -> str:
    raw = value.detach().cpu().contiguous().numpy().tobytes()
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m", type=int, default=65)
    parser.add_argument("--seed", type=int, default=20260830)
    args = parser.parse_args()

    torch.set_num_threads(1)
    device = "xpu:0"
    results = []
    for index, (name, (k, n)) in enumerate(SHAPES.items()):
        generator = torch.Generator(device="cpu")
        generator.manual_seed(args.seed + index)
        x = torch.randn(
            args.m, k, dtype=torch.float16, generator=generator
        ).to(device)
        qweight = nt_pack(
            torch.randint(
                -(2**31),
                2**31 - 1,
                (k // 8, n),
                dtype=torch.int32,
                generator=generator,
            )
        ).to(device)
        scales = torch.randn(
            k // 128, n, dtype=torch.float16, generator=generator
        ).abs().to(device)
        zero = torch.tensor([8], dtype=torch.int8, device=device)

        def run() -> torch.Tensor:
            return torch.ops._xpu_C.int4_gemm_w4a16(
                x, qweight, None, scales, zero, 128, None
            )

        first = run()
        torch.xpu.synchronize()
        first = first.clone()
        second = run()
        torch.xpu.synchronize()
        results.append(
            {
                "name": name,
                "m": args.m,
                "k": k,
                "n": n,
                "within_process_exact": bool(torch.equal(first, second)),
                "sha256": digest(first),
            }
        )
        del x, qweight, scales, zero, first, second
        torch.xpu.empty_cache()

    print(json.dumps({"seed": args.seed, "results": results}, sort_keys=True))


if __name__ == "__main__":
    main()
