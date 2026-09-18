#!/usr/bin/env python3
"""Recover Comfy-Org's `int8_convrot` rotation from the two video-VAE builds on disk.

CPU only. No GPU, no network, no service.

Why this works
--------------
`/mnt/fast-ai/llm-models/minimax-h3-comfy/vae/` holds the *same* video VAE twice:

  * `minimax_h3_video_vae_fp16.safetensors`        -- unquantized F16 weights `W`
  * `minimax_h3_video_vae_int8_convrot.safetensors` -- `weight` (I8) + `weight_scale` (F32, per
                                                       output row) + `comfy_quant`
                                                       = `{"format": "int8_tensorwise",
                                                           "convrot": true,
                                                           "convrot_groupsize": 256}`

`convrot` is a QuaRot/SpinQuant-style rotate-then-quantize: an orthogonal `R` is folded into the
weight offline along the *input* axis in blocks of `convrot_groupsize`, so the stored weight is

    W' = W R          (block-diagonal R, one 256x256 block per input group)

and the runtime must rotate the activation the same way, because

    y = x W^T = x (W' R^T)^T = (x R) W'^T .

Both `W` and `W' ~= int8 * weight_scale` are on disk, so `R` is the least-squares solution of
`W[:, g] R_g = W'[:, g]` for each 256-column group -- 16384 equations for 256 unknowns per column,
heavily overdetermined.

Measured result (2026-09-17, this host):

  * every `R_g` is the *same* matrix, to the sign of every entry, across groups, across layers and
    across `ff.w1` / `ff.w2` / `attn.to_qkv` / `attn.to_out`;
  * every entry is +-1/sqrt(256) = +-0.0625 (max deviation ~1.3e-3, i.e. the int8 rounding floor);
  * the sign matrix is symmetric, orthogonal exactly, and every row sums to +16.

So the format is fully pinned: one fixed symmetric Hadamard-type matrix of order 256, shared by
every quantized Linear.  This script re-derives it and writes the sign matrix out, so the runtime
never has to guess.

Usage
-----
    /mnt/fast-ai/venvs/minimax-h3-cpu/bin/python recover-convrot-rotation.py \
        --out ../data/convrot-hadamard-256.safetensors
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import torch
from safetensors import safe_open
from safetensors.torch import save_file

FP16_VAE = "/mnt/fast-ai/llm-models/minimax-h3-comfy/vae/minimax_h3_video_vae_fp16.safetensors"
INT8_VAE = "/mnt/fast-ai/llm-models/minimax-h3-comfy/vae/minimax_h3_video_vae_int8_convrot.safetensors"

# Probes spread over the ViT decoder: different layers, different Linears, different column groups.
PROBES = [
    ("decoder.transformer_blocks.0.ff.w1", 0),
    ("decoder.transformer_blocks.0.ff.w1", 1),
    ("decoder.transformer_blocks.0.attn.to_qkv", 3),
    ("decoder.transformer_blocks.5.ff.w2", 2),
    ("decoder.transformer_blocks.20.ff.w1", 5),
    ("decoder.transformer_blocks.35.attn.to_out", 7),
]


def recover_group(fp16, int8, base: str, group: int, group_size: int) -> torch.Tensor:
    """Least-squares `R_g` for one 256-column group of one Linear."""
    w = fp16.get_tensor(base + ".weight").float()
    q = int8.get_tensor(base + ".weight").float()
    scale = int8.get_tensor(base + ".weight_scale").float()
    w_rot = q * scale  # dequantized W' = W R
    lo, hi = group * group_size, (group + 1) * group_size
    return torch.linalg.lstsq(w[:, lo:hi], w_rot[:, lo:hi]).solution


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fp16", default=FP16_VAE)
    ap.add_argument("--int8", default=INT8_VAE)
    ap.add_argument("--group-size", type=int, default=256)
    ap.add_argument("--out", type=pathlib.Path, default=None, help="where to write the sign matrix")
    args = ap.parse_args()

    g = args.group_size
    fp16 = safe_open(args.fp16, framework="pt")
    int8 = safe_open(args.int8, framework="pt")

    # Confirm the declared format before trusting the arithmetic.
    quant_meta = json.loads(bytes(int8.get_tensor(PROBES[0][0] + ".comfy_quant").tolist()).decode().rstrip("\x00"))
    print(f"comfy_quant: {quant_meta}")
    assert quant_meta.get("convrot") is True, "this file is not convrot"
    assert quant_meta.get("convrot_groupsize") == g, f"group size is {quant_meta.get('convrot_groupsize')}, not {g}"

    solutions = []
    for base, group in PROBES:
        r = recover_group(fp16, int8, base, group, g)
        solutions.append(r)
        scaled = r * g**0.5
        resid_frac = ((scaled.abs() - 1).abs() < 0.05).float().mean().item()
        print(
            f"  {base:46s} group {group}: "
            f"max|R|={r.abs().max():.5f}  frac(|R*sqrt(G)|~1)={resid_frac:.4f}  "
            f"orth_err={(r.T @ r - torch.eye(g)).abs().max():.2e}"
        )

    signs = torch.sign(torch.stack(solutions).mean(0))
    agree = min((torch.sign(r) == signs).float().mean().item() for r in solutions)
    print(f"\nsign agreement across every probe: {agree:.6f}")
    if agree != 1.0:
        print("REFUSING to write: the probes disagree, the rotation is not a single shared matrix.", file=sys.stderr)
        return 1

    rot = signs / g**0.5
    orth = (rot.T @ rot - torch.eye(g)).abs().max().item()
    print(f"orthogonality error of the consensus matrix: {orth:.3e}")
    print(f"symmetric: {torch.equal(signs, signs.T)}   row sums all equal: {bool((signs.sum(1) == g**0.5).all())}")
    if orth != 0.0:
        print("REFUSING to write: the consensus matrix is not exactly orthogonal.", file=sys.stderr)
        return 1

    if args.out is not None:
        out = args.out.resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {"convrot_signs": signs.to(torch.int8).contiguous()}
        save_file(
            payload,
            str(out),
            metadata={
                "source": "least-squares recovery from the fp16 / int8_convrot MiniMax-H3 video VAE pair",
                "group_size": str(g),
                "scale": "multiply by 1/sqrt(group_size) to get the orthogonal rotation R",
                "convention": "stored weight W' = W R ; runtime y = (x R) W'^T",
            },
        )
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        print(f"\nwrote {out}  sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
