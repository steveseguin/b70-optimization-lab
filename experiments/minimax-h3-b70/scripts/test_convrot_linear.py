#!/usr/bin/env python3
"""`ConvRotLinear` dequantizes an INT8 ConvRot Linear correctly, and does it deterministically.

    /mnt/fast-ai/venvs/minimax-h3-cpu/bin/python test_convrot_linear.py

CPU only, no GPU.  Host memory: the synthetic part allocates kilobytes; the real-file part reads
**one 64-row slice** of two weights out of the 34 GB int8 denoiser through the pread reader, about
1.2 MB in total.  It never reads a whole tensor and never maps the file, so it needs no watchdog.

Why it exists
-------------
`--denoiser int8` replaces 250 of the denoiser's `nn.Linear` modules with `ConvRotLinear`, and
unlike the dense path there is nothing to compare bit-for-bit against afterwards: if the rotation,
the group size, the scale axis or the row mapping were wrong, the load would still succeed and the
only symptom would be a bad clip, after a full GPU session.  So the arithmetic is pinned here, on
CPU, before any card is touched:

1. **The identity the format rests on.**  Comfy stores `W' = W R` quantized to int8 with a
   per-output-row scale.  Because `R` is orthogonal, `x W^T = (x R) W'^T`, which is what
   `ConvRotLinear.forward` computes.  The synthetic case builds `W`, `R` and `W'` by hand at a
   group size of 4 and checks the module reproduces the reference to the last bit in float64, and
   the unquantized answer to within the rounding floor.
2. **Determinism.**  Two calls on the same input must hash identically -- the same bytewise repeat
   gate the run receipt applies to the clip.
3. **The row algebra.**  `row_slice` (Comfy's fused `qkv_proj` -> diffusers' `to_q`/`to_k`/`to_v`)
   and `swap_halves` (Comfy's `[gate ; value]` `mlp.fc1` -> diffusers' `[value ; gate]`) both act
   on the output axis, so weight and scale must be permuted *together*.  Doing one and not the
   other is the single easiest way to get this wrong, so it is tested directly.
4. **The rotation family.**  `convrot_rotation()` claims the order-64 rotation the denoiser's
   `adaln_proj` needs is the leading 64x64 block of the recovered order-256 matrix.  That is
   checked here as algebra (exact orthogonality, exact Kronecker structure); `run_h3_t2v.py
   --dry-run --verify-remap --denoiser int8` checks it against the real weights.
5. **The real file.**  One small int8 weight and its scale are read from the actual checkpoint and
   pushed through the module, so the shapes, dtypes and scale orientation that the loader will
   hand `ConvRotLinear` are the ones that were tested.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import pathlib
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = pathlib.Path(__file__).resolve().parent
ROTATION = HERE.parent / "data" / "convrot-hadamard-256.safetensors"
INT8_DENOISER = pathlib.Path(
    "/mnt/fast-ai/llm-models/minimax-h3-comfy/diffusion_models/minimax_h3_fl2va_int8_convrot.safetensors"
)
REAL_ROWS = 64  # output rows read from the real file, per probe

FAILURES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def load_runner():
    spec = importlib.util.spec_from_file_location("run_h3_t2v", HERE / "run_h3_t2v.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_h3_t2v"] = module
    spec.loader.exec_module(module)
    return module


def sha(t: torch.Tensor) -> str:
    a = t.detach().contiguous().flatten()
    if a.dtype is not torch.uint8:
        a = a.view(torch.uint8)
    return hashlib.sha256(memoryview(a.numpy())).hexdigest()


# ---------------------------------------------------------------------------------------------
# 1-3. Synthetic: a tiny quantized Linear built by hand, so every intermediate is known.
# ---------------------------------------------------------------------------------------------

A4 = torch.tensor([[1.0, 1, 1, -1], [1, 1, -1, 1], [1, -1, 1, 1], [-1, 1, 1, 1]])


def quantize(w: torch.Tensor, rotation: torch.Tensor, group: int):
    """Comfy's side of the contract: rotate along the input axis in blocks, then int8 per row."""
    shape = w.shape
    rotated = (w.reshape(shape[0], shape[1] // group, group) @ rotation).reshape(shape)
    scale = rotated.abs().amax(dim=1, keepdim=True) / 127.0
    qweight = torch.round(rotated / scale).clamp(-127, 127).to(torch.int8)
    return qweight, scale.to(torch.float32)


def test_synthetic(runner) -> None:
    print("synthetic INT8 ConvRot Linear (float64 reference, group size 4):")
    ConvRotLinear = runner.make_convrot_linear(torch, nn, F)
    torch.manual_seed(20260918)
    group, out_f, in_f, rows = 4, 12, 16, 5
    rotation = (A4 / math.sqrt(group)).double()
    w = torch.randn(out_f, in_f, dtype=torch.float64)
    bias = torch.randn(out_f, dtype=torch.float64)
    x = torch.randn(rows, in_f, dtype=torch.float64)

    qweight, scale = quantize(w, rotation, group)
    layer = ConvRotLinear(qweight, scale.double(), bias, rotation, group)
    y = layer(x)

    # The reference is the identity the format rests on, computed independently of the module but
    # in the module's documented operation order -- rotate, accumulate against the *int8* weight,
    # scale per output row, then add the bias.  Folding the scale into the weight first is the
    # same arithmetic in exact math and a different rounding in floating point, which is exactly
    # why the module does not do it; so the reference must not either, or this is a test of BLAS
    # associativity rather than of the format.
    xr = (x.reshape(rows, in_f // group, group) @ rotation).reshape(rows, in_f)
    ref = (xr @ qweight.double().T) * scale.double().reshape(1, -1) + bias
    check(torch.equal(y, ref), "forward == ((x R) Q^T) * scale + b, bitwise",
          f"max|diff| = {(y - ref).abs().max():.3e}")
    # ... and the folded form agrees to float64 rounding, i.e. the identity itself is right.
    folded = (xr @ (qweight.double() * scale.double()).T) + bias
    check(torch.allclose(y, folded, rtol=0, atol=1e-12), "forward == (x R) W'^T + b to float64 rounding",
          f"max|diff| = {(y - folded).abs().max():.3e}")

    # And it must approximate the *unquantized* Linear to within the int8 floor.
    exact = x @ w.T + bias
    err = (y - exact).abs().max().item()
    floor = (scale.double().max() * math.sqrt(in_f) * x.abs().max() * 0.5).item()
    check(err <= floor, "forward ~= x W^T + b within the int8 floor", f"err {err:.3e} <= floor {floor:.3e}")

    # An orthogonal rotation must be undone exactly by the transpose, or the identity above is
    # not the one Comfy applied.
    check(
        torch.allclose(rotation.T @ rotation, torch.eye(group, dtype=torch.float64), atol=0, rtol=0),
        "the group-4 rotation is exactly orthogonal",
    )

    # Determinism: the bytewise repeat gate, applied to the module itself.
    h1, h2 = sha(layer(x)), sha(layer(x))
    check(h1 == h2, "two calls hash identically (bitwise deterministic)", h1[:16])

    # bf16 is the dtype the denoiser's block stack actually runs in; it must not change shape,
    # dtype or determinism, and `compute_dtype` / `out_dtype` must be honoured.
    layer_bf = ConvRotLinear(qweight, scale, bias.bfloat16(), rotation.bfloat16(), group)
    y_bf = layer_bf(x.bfloat16())
    check(y_bf.dtype is torch.bfloat16 and y_bf.shape == (rows, out_f), "bf16 forward keeps shape and dtype")
    check(sha(layer_bf(x.bfloat16())) == sha(y_bf), "bf16 forward is bitwise deterministic")
    # `compute_dtype` must make a float32 activation behave exactly like a bf16 one -- that is the
    # whole point of pinning it on the denoiser's `adaln_proj`, which diffusers hands float32.
    # No bias in this pair: a bf16 bias added in float32 rounds differently from one added in
    # bf16, which would test the addition order rather than `compute_dtype`.
    x_bf = x.bfloat16()
    plain_bf = ConvRotLinear(qweight, scale, None, rotation.bfloat16(), group)
    pinned = ConvRotLinear(qweight, scale, None, rotation.bfloat16(), group,
                           compute_dtype=torch.bfloat16, out_dtype=torch.float32)
    y_pin = pinned(x_bf.float())
    check(y_pin.dtype is torch.float32, "out_dtype=float32 is honoured", str(y_pin.dtype))
    check(torch.equal(y_pin.bfloat16(), plain_bf(x_bf)),
          "compute_dtype=bfloat16 makes a float32 activation match a bf16 one")

    # A group size that does not divide in_features must be refused, not silently reshaped.
    try:
        ConvRotLinear(qweight, scale, None, rotation, 7)
        check(False, "a group size that does not divide in_features is refused")
    except ValueError:
        check(True, "a group size that does not divide in_features is refused")

    # --- the row algebra ----------------------------------------------------------------------
    # A sub-Linear's GEMM has a different shape from the full one, so BLAS may accumulate it in a
    # different order; the comparisons below are therefore to float64 rounding, not bitwise. The
    # thing being tested is the *pairing* of weight rows with scale rows, whose failure mode is a
    # wrong scale per row -- orders of magnitude, never 1e-15.
    lo, hi = 4, 8
    sub = ConvRotLinear(qweight[lo:hi], scale[lo:hi].double(), bias[lo:hi], rotation, group)
    check(torch.allclose(sub(x), y[:, lo:hi], rtol=0, atol=1e-12),
          "row_slice(weight, scale) == the same rows of the full output",
          f"max|diff| = {(sub(x) - y[:, lo:hi]).abs().max():.3e}")

    # Swapping halves of weight and scale together must equal swapping halves of the output.
    half = out_f // 2
    swapped = ConvRotLinear(
        torch.cat((qweight[half:], qweight[:half])),
        torch.cat((scale[half:], scale[:half])).double(),
        torch.cat((bias[half:], bias[:half])),
        rotation,
        group,
    )
    check(torch.allclose(swapped(x), torch.cat((y[:, half:], y[:, :half]), dim=-1), rtol=0, atol=1e-12),
          "swap_halves(weight, scale) == swapping the output halves",
          f"max|diff| = {(swapped(x) - torch.cat((y[:, half:], y[:, :half]), dim=-1)).abs().max():.3e}")

    # The failure this guards against: swapping the weight but not the scale.  It has to be a
    # *gross* difference, not a rounding one, or the check above could not tell them apart.
    wrong = ConvRotLinear(torch.cat((qweight[half:], qweight[:half])), scale.double(), bias, rotation, group)
    gap = (wrong(x) - swapped(x)).abs().max().item()
    check(gap > 1e-3, "swapping the weight WITHOUT the scale is detectably wrong", f"max|diff| = {gap:.3e}")


# ---------------------------------------------------------------------------------------------
# 4. The rotation family.
# ---------------------------------------------------------------------------------------------


def test_rotation(runner) -> None:
    print("\nConvRot rotation (data/convrot-hadamard-256.safetensors):")
    if not ROTATION.exists():
        check(False, f"{ROTATION.name} is present")
        return
    with runner.open_tensor_reader(ROTATION) as fh:
        signs = fh.get_tensor("convrot_signs")
    check(signs.shape == (256, 256), "recovered matrix is 256x256", str(tuple(signs.shape)))

    kron = A4.clone()
    for _ in range(3):
        kron = torch.kron(kron, A4)
    check(torch.equal(kron, signs.to(torch.float32)),
          "the recovered order-256 matrix is exactly A (x) A (x) A (x) A")

    for group in (64, 256):
        R = runner.convrot_rotation(torch, signs, group)
        err = (R.T @ R - torch.eye(group)).abs().max().item()
        check(err == 0.0, f"convrot_rotation(group={group}) is exactly orthogonal", f"err {err:.1e}")
    # The claim the int8 adaln path depends on: the order-64 rotation is the leading block.
    kron3 = torch.kron(torch.kron(A4, A4), A4)
    check(torch.equal(runner.convrot_rotation(torch, signs, 64), kron3 / 8.0),
          "the order-64 rotation is A (x) A (x) A, i.e. the leading 64x64 block")
    # A group size the family cannot supply must be refused.
    for bad in (512, 96):
        try:
            runner.convrot_rotation(torch, signs, bad)
            check(False, f"group size {bad} is refused")
        except ValueError:
            check(True, f"group size {bad} is refused")


# ---------------------------------------------------------------------------------------------
# 5. One small slice of the real checkpoint, end to end.
# ---------------------------------------------------------------------------------------------


def test_real_file(runner) -> None:
    print(f"\nreal INT8 denoiser ({REAL_ROWS}-row slices through the pread reader):")
    if not INT8_DENOISER.exists():
        check(False, f"{INT8_DENOISER.name} is present")
        return
    header = runner.read_header(INT8_DENOISER)
    quant_meta = runner.read_comfy_quant(INT8_DENOISER, header)
    with runner.open_tensor_reader(ROTATION) as fh:
        signs = fh.get_tensor("convrot_signs")
    ConvRotLinear = runner.make_convrot_linear(torch, nn, F)

    # One Linear per group size: the smallest 256-group weight, and the 64-group AdaLN one.
    probes = [("blocks.0.attn.out_proj", 256), ("blocks.0.adaln_proj.linear", 64)]
    with runner.PreadTensorReader(INT8_DENOISER, header) as fh:
        for base, expect_group in probes:
            meta = quant_meta[base]
            check(meta["convrot_groupsize"] == expect_group,
                  f"{base}: comfy_quant declares group {expect_group}", str(meta))
            group = int(meta["convrot_groupsize"])

            qw = fh.get_tensor(base + ".weight", (0, REAL_ROWS))
            sc = fh.get_tensor(base + ".weight_scale", (0, REAL_ROWS))
            in_f = header[base + ".weight"]["shape"][1]
            check(qw.dtype is torch.int8 and tuple(qw.shape) == (REAL_ROWS, in_f),
                  f"{base}: weight slice is int8 {(REAL_ROWS, in_f)}", f"{qw.dtype} {tuple(qw.shape)}")
            check(sc.dtype is torch.float32 and tuple(sc.shape) == (REAL_ROWS, 1),
                  f"{base}: scale slice is float32 [{REAL_ROWS}, 1] (per output row)",
                  f"{sc.dtype} {tuple(sc.shape)}")
            check(in_f % group == 0, f"{base}: in_features {in_f} is a multiple of the group size {group}")

            R = runner.convrot_rotation(torch, signs, group).to(torch.bfloat16)
            layer = ConvRotLinear(qw, sc, None, R, group, compute_dtype=torch.bfloat16)
            x = torch.arange(in_f, dtype=torch.bfloat16).reshape(1, in_f) / in_f
            y = layer(x)
            check(y.dtype is torch.bfloat16 and tuple(y.shape) == (1, REAL_ROWS),
                  f"{base}: forward round-trips to bf16 [1, {REAL_ROWS}]", f"{y.dtype} {tuple(y.shape)}")
            check(bool(torch.isfinite(y).all()) and bool((y != 0).any()),
                  f"{base}: output is finite and non-trivial", f"max|y| = {y.abs().max().float():.4f}")
            check(sha(layer(x)) == sha(y), f"{base}: forward is bitwise deterministic")

            # Dequantizing must land inside the int8 rounding floor of the stored values.
            deq = qw.float() * sc.float()
            check(float(deq.abs().max()) <= float(sc.abs().max()) * 127.0 + 1e-6,
                  f"{base}: dequantized magnitude is within 127 * scale")
            for suffix in (".weight", ".weight_scale"):
                fh.release(base + suffix, (0, REAL_ROWS))


def main() -> int:
    runner = load_runner()
    test_synthetic(runner)
    test_rotation(runner)
    test_real_file(runner)
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all checks passed: the INT8 ConvRot dequant path is correct and deterministic")
    return 0


if __name__ == "__main__":
    sys.exit(main())
