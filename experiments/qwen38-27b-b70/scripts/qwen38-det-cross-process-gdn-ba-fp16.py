#!/usr/bin/env python3
"""Hash the exact padded GDN B/A FP16 projection across processes."""

import hashlib
import json

import torch
import torch.nn.functional as F


M_VALUES = (48, 49, 52, 53, 55, 56, 57, 59, 65, 71, 75, 78)
N_VALUES = (48, 96)
K = 5120
PAD_M = 256
SEED = 20260831


def digest(value: torch.Tensor) -> str:
    return hashlib.sha256(value.cpu().contiguous().numpy().tobytes()).hexdigest()


def main() -> None:
    torch.set_num_threads(1)
    device = torch.device("xpu:0")
    rows = []
    for n in N_VALUES:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(SEED + n)
        weight = torch.randn(n, K, dtype=torch.float16, generator=generator).to(device)
        for m in M_VALUES:
            x_generator = torch.Generator(device="cpu")
            x_generator.manual_seed(SEED + n * 1000 + m)
            x = torch.randn(m, K, dtype=torch.float16, generator=x_generator).to(device)

            direct_a = F.linear(x, weight)
            torch.xpu.synchronize()
            direct_a = direct_a.clone()
            direct_b = F.linear(x, weight)
            torch.xpu.synchronize()

            padded = torch.zeros(PAD_M, K, dtype=x.dtype, device=device)
            padded[:m].copy_(x)
            padded_a = F.linear(padded, weight)[:m]
            torch.xpu.synchronize()
            padded_a = padded_a.clone()
            padded_b = F.linear(padded, weight)[:m]
            torch.xpu.synchronize()

            rows.append({
                "m": m,
                "k": K,
                "n": n,
                "direct_within_process_exact": bool(torch.equal(direct_a, direct_b)),
                "padded_within_process_exact": bool(torch.equal(padded_a, padded_b)),
                "padded_vs_direct_exact": bool(torch.equal(padded_a, direct_a)),
                "direct_sha256": digest(direct_a),
                "padded_sha256": digest(padded_a),
            })
            del x, direct_a, direct_b, padded, padded_a, padded_b
        del weight
        torch.xpu.empty_cache()
    print(json.dumps({"seed": SEED, "pad_m": PAD_M, "rows": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
