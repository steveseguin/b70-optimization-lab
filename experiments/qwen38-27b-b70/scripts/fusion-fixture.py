#!/usr/bin/env python3
"""Fusion-candidate fixture extraction and CPU proof for Qwen3.8 27B AutoRound.

Supports proof-order step 2 of
experiments/qwen38-27b-b70/notes/2026-08-18-autoround-fused-resadd-rmsnorm-int4-triage.md
(fused residual-add -> post-attention RMSNorm -> dense gate_up W4A16) WITHOUT
a GPU, so the 15 GiB second host can contribute safely:

  extract  Pull real checkpoint tensors (post-attention RMSNorm weight,
           gate/up qweight/scales/qzeros) for selected layers into a small
           fixture safetensors + provenance JSON.
  prove    CPU-only exactness proofs:
             1. independent pure-torch AutoRound/GPTQ-style unpack matches the
                auto_round_kernel CPU unpack bit-for-bit (integer equality);
             2. fp32 reference dequant matches the ark repack->unpack round
                trip exactly (scales fp16->fp32 is lossless);
             3. emit fp32 reference outputs for the fused op
                y = RMSNorm(h + r) @ W_gateup^T at M=4, including the TP2
                per-rank local gate/up slices the candidate kernel will see.
           Inputs h/r are deterministic synthetic rows (seeded); the harness
           accepts real activation dumps later via --activations.
  compare  (measuring host) score a candidate kernel output safetensors
           against the stored fp32 references.

Memory: peak ~1.5 GB (one projection dequantized at a time). Safe on the
15 GiB host. No GPU is touched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import load_file, save_file

GROUP_SIZE = 128
BITS = 4
# Symmetric AutoRound/GPTQ: stored zero point is 7, effective bias is 8.
QBIAS = 2 ** (BITS - 1)


def _checkpoint_tensors(model_dir: Path, layer: int) -> dict[str, tuple[str, str]]:
    """Map fixture key -> (checkpoint tensor name, shard file)."""
    idx = json.loads((model_dir / "model.safetensors.index.json").read_text())
    wm = idx["weight_map"]
    base = f"model.language_model.layers.{layer}"
    names = {
        "norm": f"{base}.post_attention_layernorm.weight",
        "gate_qweight": f"{base}.mlp.gate_proj.qweight",
        "gate_scales": f"{base}.mlp.gate_proj.scales",
        "gate_qzeros": f"{base}.mlp.gate_proj.qzeros",
        "up_qweight": f"{base}.mlp.up_proj.qweight",
        "up_scales": f"{base}.mlp.up_proj.scales",
        "up_qzeros": f"{base}.mlp.up_proj.qzeros",
    }
    out = {}
    for key, name in names.items():
        if name not in wm:
            raise SystemExit(f"missing checkpoint tensor: {name}")
        out[key] = (name, wm[name])
    return out


def cmd_extract(args: argparse.Namespace) -> None:
    model_dir = Path(args.model_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    layers = [int(x) for x in args.layers.split(",")]

    tensors: dict[str, torch.Tensor] = {}
    for layer in layers:
        for key, (name, shard) in _checkpoint_tensors(model_dir, layer).items():
            with safe_open(model_dir / shard, "pt") as f:
                tensors[f"layer{layer}.{key}"] = f.get_tensor(name)
            print(f"extracted layer{layer}.{key} {tuple(tensors[f'layer{layer}.{key}'].shape)}")

    cfg = json.loads((model_dir / "config.json").read_text())
    text_cfg = cfg.get("text_config", {})
    meta = {
        "model_dir": str(model_dir),
        "hf_revision": "bce40cacab0a4535b92fb3d57615c2bea9adf3d1",
        "layers": layers,
        "bits": BITS,
        "group_size": GROUP_SIZE,
        "sym": True,
        "qbias": QBIAS,
        "rms_norm_eps": text_cfg.get("rms_norm_eps"),
        "hidden_size": text_cfg.get("hidden_size"),
        "intermediate_size": text_cfg.get("intermediate_size"),
        "packing": {
            "qweight": "[K/8, N] int32, 8 nibbles LSB-first along K",
            "qzeros": "[K/group, N/8] int32, 8 nibbles LSB-first along N; sym stores 7, effective zp = 8",
            "scales": "[K/group, N] fp16",
        },
        "tp2_slice_rule": (
            "vLLM MergedColumnParallelLinear: rank r local gate = gate[:, "
            "r*(N/2):(r+1)*(N/2)], same for up; local gate_up output is "
            "concat(gate_local, up_local) with N_local = N (here 17408)."
        ),
        "fixture_format": "fusion-fixture-v1",
    }
    save_file(tensors, str(out_dir / "fixture.safetensors"))
    (out_dir / "fixture.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"wrote {out_dir/'fixture.safetensors'} and fixture.json")


def _unpack_qweight_ref(qweight: torch.Tensor) -> torch.Tensor:
    """[K/8, N] int32 -> [K, N] uint8, LSB-first nibble order along K."""
    k8, n = qweight.shape
    q = torch.empty((k8 * 8, n), dtype=torch.uint8)
    for j in range(8):
        q[j::8] = ((qweight >> (4 * j)) & 0xF).to(torch.uint8)
    return q


def _unpack_qzeros_ref(qzeros: torch.Tensor) -> torch.Tensor:
    """[G, N/8] int32 -> [G, N] uint8, LSB-first nibble order along N."""
    g, n8 = qzeros.shape
    zp = torch.empty((g, n8 * 8), dtype=torch.uint8)
    for j in range(8):
        zp[:, j::8] = ((qzeros >> (4 * j)) & 0xF).to(torch.uint8)
    return zp


def _dequant_ref(qweight: torch.Tensor, scales: torch.Tensor,
                 qzeros: torch.Tensor) -> torch.Tensor:
    """fp32 [K, N] reference: (q - zp) * scale, sym effective zp = qbias."""
    q = _unpack_qweight_ref(qweight).to(torch.float32)
    zp = _unpack_qzeros_ref(qzeros).to(torch.float32) + 1.0  # stored 7 -> 8
    k, n = q.shape
    g = scales.shape[0]
    assert k == g * GROUP_SIZE, (k, g)
    zp = zp.repeat_interleave(GROUP_SIZE, dim=0)
    s = scales.to(torch.float32).repeat_interleave(GROUP_SIZE, dim=0)
    return (q - zp) * s


def _ark_dequant(qweight: torch.Tensor, scales: torch.Tensor,
                 qzeros: torch.Tensor) -> torch.Tensor:
    """Dequant through the exact auto_round_kernel CPU repack/unpack path
    used by vLLM's INC loader (post_init), as the oracle."""
    from auto_round_kernel import repack_quantized_weight, unpack_weight
    from auto_round_kernel.qlinear import QuantLinear  # noqa: F401

    k = qweight.shape[0] * 8
    n = qweight.shape[1]
    ql = QuantLinear(
        bits=BITS,
        group_size=GROUP_SIZE,
        sym=True,
        in_features=k,
        out_features=n,
        bias=False,
        weight_dtype=torch.float16,
    )
    with torch.no_grad():
        ql.qweight.copy_(qweight)
        ql.qzeros.copy_(qzeros)
        ql.scales.copy_(scales)
    ql.post_init()  # CPU: unpack_to_8bit_signed + ark.repack_quantized_weight
    blob = ql.qweight
    out = unpack_weight(
        blob, torch.float32, n, k, GROUP_SIZE, "auto", "int4", "fp32", False,
    )
    return out  # [N, K] on CPU (unpack_weight returns out.T)


def cmd_prove(args: argparse.Namespace) -> None:
    fixture_dir = Path(args.fixture_dir)
    meta = json.loads((fixture_dir / "fixture.json").read_text())
    tensors = load_file(str(fixture_dir / "fixture.safetensors"))
    eps = float(meta["rms_norm_eps"])
    failures = 0

    for layer in meta["layers"]:
        for proj in ("gate", "up"):
            qw = tensors[f"layer{layer}.{proj}_qweight"]
            sc = tensors[f"layer{layer}.{proj}_scales"]
            qz = tensors[f"layer{layer}.{proj}_qzeros"]

            # Proof 1: reference unpack matches ark oracle dequant exactly.
            w_ref = _dequant_ref(qw, sc, qz)          # [K, N] fp32
            w_ark = _ark_dequant(qw, sc, qz).t()      # -> [K, N] fp32
            max_abs = (w_ref - w_ark).abs().max().item()
            exact = torch.equal(w_ref, w_ark)
            print(f"layer{layer} {proj}: dequant vs ark oracle "
                  f"max_abs_diff={max_abs} exact={exact}")
            if not exact:
                failures += 1
            del w_ref, w_ark

        # Proof 3 inputs/outputs: fused residual-add -> RMSNorm -> gate_up.
        g = torch.Generator().manual_seed(args.seed + layer)
        hidden = int(meta["hidden_size"])
        h = torch.randn((4, hidden), generator=g, dtype=torch.float32).to(torch.float16)
        r = torch.randn((4, hidden), generator=g, dtype=torch.float32).to(torch.float16)
        norm_w = tensors[f"layer{layer}.norm"].to(torch.float32)

        x = (h + r).to(torch.float32)
        denom = x.pow(2).mean(dim=-1, keepdim=True) + eps
        xn = x * torch.rsqrt(denom) * norm_w

        wg = _dequant_ref(tensors[f"layer{layer}.gate_qweight"],
                          tensors[f"layer{layer}.gate_scales"],
                          tensors[f"layer{layer}.gate_qzeros"])
        wu = _dequant_ref(tensors[f"layer{layer}.up_qweight"],
                          tensors[f"layer{layer}.up_scales"],
                          tensors[f"layer{layer}.up_qzeros"])
        out_g = xn @ wg            # [4, N] fp32
        out_u = xn @ wu
        n = wg.shape[1]
        half = n // 2
        update = {
            f"layer{layer}.h": h,
            f"layer{layer}.r": r,
            f"layer{layer}.fused_out.gate": out_g,
            f"layer{layer}.fused_out.up": out_u,
        }
        for rank in (0, 1):
            sl = slice(rank * half, (rank + 1) * half)
            # TP-local gate_up output: concat(gate shard, up shard).
            update[f"layer{layer}.rank{rank}.fused_out"] = torch.cat(
                [out_g[:, sl], out_u[:, sl]], dim=-1
            )
        save_file(update, str(fixture_dir / f"reference-layer{layer}.safetensors"))
        print(f"layer{layer}: wrote fp32 fused-op references "
              f"(M=4, K={wg.shape[0]}, N={n}; TP2 local N={n})")
        del wg, wu, out_g, out_u

    if failures:
        print(f"PROOF FAILED: {failures} projection(s) diverged from the ark oracle",
              file=sys.stderr)
        raise SystemExit(1)
    print("all CPU proofs passed")


def cmd_compare(args: argparse.Namespace) -> None:
    fixture_dir = Path(args.fixture_dir)
    meta = json.loads((fixture_dir / "fixture.json").read_text())
    cand = load_file(args.candidate)
    worst = 0.0
    bad = 0
    for layer in meta["layers"]:
        ref = load_file(str(fixture_dir / f"reference-layer{layer}.safetensors"))
        for rank in (0, 1):
            key = f"layer{layer}.rank{rank}.fused_out"
            if key not in cand:
                print(f"missing candidate key: {key}", file=sys.stderr)
                bad += 1
                continue
            c = cand[key].to(torch.float32)
            t = ref[key]
            diff = (c - t).abs()
            rel = (diff / t.abs().clamp_min(1e-6)).max().item()
            ma = diff.max().item()
            worst = max(worst, ma)
            ok = ma <= args.atol or rel <= args.rtol
            print(f"{key}: max_abs={ma:.6g} max_rel={rel:.6g} "
                  f"{'OK' if ok else 'FAIL'}")
            if not ok:
                bad += 1
    print(f"worst max_abs={worst:.6g}")
    if bad:
        raise SystemExit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract")
    pe.add_argument("--model-dir", required=True)
    pe.add_argument("--out-dir", required=True)
    pe.add_argument("--layers", default="0,30")
    pe.set_defaults(fn=cmd_extract)

    pp = sub.add_parser("prove")
    pp.add_argument("--fixture-dir", required=True)
    pp.add_argument("--seed", type=int, default=20260818)
    pp.set_defaults(fn=cmd_prove)

    pc = sub.add_parser("compare")
    pc.add_argument("--fixture-dir", required=True)
    pc.add_argument("--candidate", required=True)
    pc.add_argument("--atol", type=float, default=1e-3)
    pc.add_argument("--rtol", type=float, default=1e-3)
    pc.set_defaults(fn=cmd_compare)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
