#!/usr/bin/env python3
"""The LoRA merge and the ConvRot runtime term are both correct, and both deterministic.

    /mnt/fast-ai/venvs/minimax-h3-cpu/bin/python test_lora.py

CPU only, no GPU.  Host memory: the synthetic part allocates kilobytes; the real-file part reads
**safetensors headers plus 208 four-byte `alpha` scalars** out of the 1.96 GB turbo LoRA and the
two denoiser checkpoints.  No tensor data is read from any large file, nothing is mapped, and no
watchdog is needed.

Why it exists
-------------
`--lora` applies the same adapter through two arithmetically *different* paths, and only one of
them is a merge:

1. **Dense BF16 weights are merged at load time**, `W' = W + s * (B @ A)`, with the sum taken in
   float32 and rounded once into the destination dtype.  bf16 -> float32 is exact, so the merged
   weight differs from an infinitely precise merge by one rounding and nothing else.  Checked here
   against a **float64** reference.
2. **int8 ConvRot Linears cannot be merged at all.**  The stored weight is `round(W R / s)`; there
   is no way to fold a delta in without re-quantizing, which would replace the measured int8 error
   by a different and larger one.  So the adapter stays an additive term evaluated per call,
   `y = dequant(W) x + s * B (A x)` -- checked here against a float64 reference too.

Three ways to get path 2 silently wrong, all tested directly:

* **The rotation.**  The LoRA adapts `W`, not Comfy's rotated `W R`, so its term must be built
  from the **unrotated** activation.  Feeding it the rotated `x` still runs, still produces
  plausible numbers, and is wrong.  `test_rotated_uses_unrotated_x` pins it.
* **The output axis.**  `row_slice` (fused `qkv_proj` -> `to_q`/`to_k`/`to_v`) and `swap_halves`
  (Comfy's `[gate ; value]` `mlp.fc1` -> diffusers' `[value ; gate]`) act on `lora_B`'s rows,
  exactly as they act on the weight's rows, and `lora_A` is always taken whole.
* **The scale.**  The effective multiplier is `user_scale * alpha / rank`, and the turbo file's
  fused `qkv_proj` carries `alpha = 24` against `rank = 384` precisely so that ratio stays
  `0.0625` like every other module.  Checked on the real file's own metadata.

Determinism is checked the same way the run receipt checks the clip: the same input twice must
hash to the same bytes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = pathlib.Path(__file__).resolve().parent
TURBO_LORA = pathlib.Path(
    "/mnt/fast-ai/llm-models/minimax-h3-comfy/loras/"
    "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
)

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


class DictReader:
    """The two methods `lora_delta` / `lora_runtime_tensors` use, over an in-memory dict.

    Same row-slice semantics as `PreadTensorReader`: `row_slice` takes rows `[begin, end)` of the
    first axis, which is the output axis for `lora_B`.
    """

    def __init__(self, tensors: dict[str, torch.Tensor]):
        self.tensors = tensors
        self.released: list[tuple] = []

    def get_tensor(self, key: str, row_slice=None):
        t = self.tensors[key]
        return t if row_slice is None else t[row_slice[0]: row_slice[1]]

    def release(self, key: str, row_slice=None) -> None:
        self.released.append((key, row_slice))


# ---------------------------------------------------------------------------------------------
# 1. The merge: W' = W + s * (B @ A), float32, one rounding, against a float64 reference.
# ---------------------------------------------------------------------------------------------

def reference_delta(b: torch.Tensor, a: torch.Tensor, scale: float) -> torch.Tensor:
    """The thing the merge approximates, in float64: no bf16 anywhere in the product."""
    return (b.to(torch.float64) @ a.to(torch.float64)) * float(scale)


def make_pair(runner, out_features: int, in_features: int, rank: int, alpha: float, seed: int):
    g = torch.Generator().manual_seed(seed)
    a = (torch.randn(rank, in_features, generator=g) * 0.05).to(torch.bfloat16)
    b = (torch.randn(out_features, rank, generator=g) * 0.05).to(torch.bfloat16)
    pair = runner.LoraPair(
        base="blocks.0.test",
        down="blocks.0.test.lora_A.weight",
        up="blocks.0.test.lora_B.weight",
        rank=rank,
        in_features=in_features,
        out_features=out_features,
        alpha=alpha,
    )
    reader = DictReader({pair.down: a, pair.up: b})
    return pair, reader, a, b


def test_merge(runner) -> None:
    print("\n1. merge: W' = W + scale * (B @ A), float32, rounded once")
    out_features, in_features, rank, alpha = 96, 64, 8, 4.0
    pair, reader, a, b = make_pair(runner, out_features, in_features, rank, alpha, seed=11)

    check(abs(pair.strength - alpha / rank) < 1e-12,
          "alpha / rank is the file's own strength", f"{alpha} / {rank} = {pair.strength}")

    user = 0.75
    sl = runner.LoraSlice(pair, None, False, user * pair.strength)
    check(abs(sl.scale - user * alpha / rank) < 1e-12,
          "effective scale is user_scale * alpha / rank", f"{sl.scale}")

    delta = runner.lora_delta(torch, reader, sl)
    ref = reference_delta(b, a, sl.scale)
    check(delta.dtype is torch.float32, "delta is float32", str(delta.dtype))
    check(tuple(delta.shape) == (out_features, in_features), "delta has the weight's shape",
          str(tuple(delta.shape)))
    err = (delta.to(torch.float64) - ref).abs().max().item()
    scale_of = ref.abs().max().item()
    check(err <= scale_of * 1e-6, "delta matches the float64 reference to float32 precision",
          f"max err {err:.3e} on max|delta| {scale_of:.3e}")
    check(sorted(reader.released) == sorted([(pair.up, None), (pair.down, None)]),
          "both factors are released back to the reader")

    # The merge as the loader performs it: widen, add, round once.
    g = torch.Generator().manual_seed(12)
    w = (torch.randn(out_features, in_features, generator=g) * 0.02).to(torch.bfloat16)
    merged = (w.to(torch.float32) + runner.lora_delta(torch, reader, sl)).to(torch.bfloat16)
    ref_merged = (w.to(torch.float64) + ref)
    # Exactly one rounding: the merged bf16 weight must be the bf16 nearest to the float64 truth,
    # up to the float32 error in the delta itself -- i.e. no worse than half a bf16 ulp + that.
    ulp = torch.where(ref_merged == 0, torch.tensor(1e-30, dtype=torch.float64),
                      ref_merged.abs() * 2.0 ** -8)
    within = ((merged.to(torch.float64) - ref_merged).abs() <= ulp).all().item()
    check(bool(within), "merged weight is within one bf16 ulp of the float64 reference",
          f"max err {(merged.to(torch.float64) - ref_merged).abs().max().item():.3e}")
    check(sha(merged) == sha((w.to(torch.float32) + runner.lora_delta(torch, reader, sl)).to(torch.bfloat16)),
          "merge is bitwise deterministic")

    # A zero-strength LoRA must leave the weight bit-identical.
    zero = runner.LoraSlice(pair, None, False, 0.0)
    unchanged = (w.to(torch.float32) + runner.lora_delta(torch, reader, zero)).to(torch.bfloat16)
    check(sha(unchanged) == sha(w), "scale 0 leaves the weight bit-identical")


def test_output_axis(runner) -> None:
    print("\n2. the output axis: row_slice and swap_halves act on lora_B's rows, lora_A is whole")
    out_features, in_features, rank = 96, 64, 8
    pair, reader, a, b = make_pair(runner, out_features, in_features, rank, 4.0, seed=21)
    scale = pair.strength

    # row_slice: the qkv split.  Slicing the delta must equal the delta of the slice.
    rows = (32, 64)
    sl = runner.LoraSlice(pair, rows, False, scale)
    got = runner.lora_delta(torch, reader, sl)
    want = reference_delta(b, a, scale)[rows[0]: rows[1]]
    check(tuple(got.shape) == (rows[1] - rows[0], in_features), "row-sliced delta has the slice's shape",
          str(tuple(got.shape)))
    check((got.to(torch.float64) - want).abs().max().item() <= want.abs().max().item() * 1e-6,
          "delta of the row slice == row slice of the delta")

    # swap_halves: the SwiGLU reorder.
    sl = runner.LoraSlice(pair, None, True, scale)
    got = runner.lora_delta(torch, reader, sl)
    full = reference_delta(b, a, scale)
    half = out_features // 2
    want = torch.cat((full[half:], full[:half]), dim=0)
    check((got.to(torch.float64) - want).abs().max().item() <= want.abs().max().item() * 1e-6,
          "delta with swapped halves == the delta's halves swapped")

    # Both at once, which is what a sliced SwiGLU would need (and which the real file never asks
    # for) -- the order must be slice-then-swap on lora_B, the same order the weight loader uses.
    sl = runner.LoraSlice(pair, (0, 64), True, scale)
    got = runner.lora_delta(torch, reader, sl)
    sliced = full[0:64]
    want = torch.cat((sliced[32:], sliced[:32]), dim=0)
    check((got.to(torch.float64) - want).abs().max().item() <= want.abs().max().item() * 1e-6,
          "row_slice then swap_halves composes like the weight path")

    # lora_A is never sliced: a slice on A's rows would change the rank, not the output axis.
    sl = runner.LoraSlice(pair, (0, 16), False, scale)
    runner.lora_delta(torch, reader, sl)
    check((pair.down, None) in reader.released, "lora_A is always requested whole")


# ---------------------------------------------------------------------------------------------
# 3. The runtime term inside ConvRotLinear.
# ---------------------------------------------------------------------------------------------

def dequantized_weight(qw: torch.Tensor, sc: torch.Tensor, rotation: torch.Tensor, group: int):
    """The effective weight `W` a ConvRotLinear stands for, in the ORIGINAL (unrotated) basis.

    Comfy stores `W' = W R` quantized, and the module computes `(x R) W'^T`.  Since `R` is
    orthogonal that equals `x W^T` with `W = (sc . qw) R^T`, so a reference that wants to write the
    Linear as one matmul has to undo the rotation on the input axis -- blockwise, like the forward.
    """
    wr = qw.to(torch.float64) * sc.to(torch.float64)
    out_features, in_features = wr.shape
    return (wr.reshape(out_features, in_features // group, group)
            @ rotation.to(torch.float64).T).reshape(out_features, in_features)


A4 = torch.tensor([[1.0, 1, 1, -1], [1, 1, -1, 1], [1, -1, 1, 1], [-1, 1, 1, 1]])


def quantize(w: torch.Tensor, rotation: torch.Tensor, group: int):
    """Comfy's side of the contract: rotate along the input axis in blocks, then int8 per row."""
    shape = w.shape
    rotated = (w.reshape(shape[0], shape[1] // group, group) @ rotation).reshape(shape)
    scale = rotated.abs().amax(dim=1, keepdim=True) / 127.0
    qweight = torch.round(rotated / scale).clamp(-127, 127).to(torch.int8)
    return qweight, scale.to(torch.float32)


def test_runtime_term(runner) -> None:
    print("\n3. runtime term: y = dequant(W) x + scale * B (A x), inside ConvRotLinear")
    ConvRotLinear = runner.make_convrot_linear(torch, nn, F)
    out_features, in_features, rank, group = 24, 16, 4, 4
    g = torch.Generator().manual_seed(31)
    w = torch.randn(out_features, in_features, generator=g) * 0.1
    rotation = torch.kron(A4, A4)[:group, :group] / group ** 0.5
    qw, sc = quantize(w, rotation, group)
    a = (torch.randn(rank, in_features, generator=g) * 0.05).to(torch.bfloat16)
    b = (torch.randn(out_features, rank, generator=g) * 0.05).to(torch.bfloat16)
    scale = 0.0625
    x = torch.randn(3, in_features, generator=g, dtype=torch.float64)

    plain = ConvRotLinear(qw, sc, None, rotation, group)
    with_lora = ConvRotLinear(qw, sc, None, rotation, group, lora_a=a, lora_b=b, lora_scale=scale)

    # The float64 reference: the dequantized weight PLUS the low-rank term, one matmul.
    w_deq = dequantized_weight(qw, sc, rotation, group)
    ref = x @ (w_deq + reference_delta(b, a, scale)).T

    y = with_lora(x)
    check(y.dtype is torch.float64, "a float64 activation keeps the whole path in float64", str(y.dtype))
    err = (y - ref).abs().max().item()
    check(err <= ref.abs().max().item() * 1e-12,
          "float64 activation reproduces the float64 reference", f"max err {err:.3e}")

    # And the term really is additive on top of the un-adapted Linear.
    term = with_lora(x) - plain(x)
    ref_term = x @ reference_delta(b, a, scale).T
    check((term - ref_term).abs().max().item() <= ref_term.abs().max().item() * 1e-12,
          "with_lora(x) - plain(x) is exactly the low-rank term")

    # scale 0 must be bit-identical to no LoRA at all.
    zeroed = ConvRotLinear(qw, sc, None, rotation, group, lora_a=a, lora_b=b, lora_scale=0.0)
    check(sha(zeroed(x)) == sha(plain(x)), "lora_scale 0 is bitwise identical to no LoRA")

    # bf16, i.e. what the cards run: float32 accumulation, so a float32-sized tolerance.
    xb = x.to(torch.bfloat16)
    yb = with_lora(xb)
    refb = xb.to(torch.float64) @ (w_deq + reference_delta(b, a, scale)).T
    check(yb.dtype is torch.bfloat16, "a bf16 activation returns bf16", str(yb.dtype))
    rel = (yb.to(torch.float64) - refb).abs().max().item() / refb.abs().max().item()
    check(rel <= 5e-2, "bf16 activation tracks the float64 reference within the bf16 floor",
          f"max relative err {rel:.3e}")
    check(sha(with_lora(xb)) == sha(yb), "runtime term is bitwise deterministic")

    # Bias still lands after the LoRA, not before it.
    bias = torch.randn(out_features, generator=g, dtype=torch.float64)
    biased = ConvRotLinear(qw, sc, bias, rotation, group, lora_a=a, lora_b=b, lora_scale=scale)
    check((biased(x) - (y + bias)).abs().max().item() <= 1e-12,
          "bias is added after the LoRA term")

    # Shape guards fail closed.
    for label, kwargs in (
        ("A with the wrong in_features", dict(lora_a=a[:, :-1].contiguous(), lora_b=b)),
        ("B with the wrong out_features", dict(lora_a=a, lora_b=b[:-1].contiguous())),
        ("mismatched ranks", dict(lora_a=a, lora_b=b[:, :-1].contiguous())),
        ("A without B", dict(lora_a=a)),
    ):
        try:
            ConvRotLinear(qw, sc, None, rotation, group, lora_scale=scale, **kwargs)
            check(False, f"rejects {label}")
        except ValueError:
            check(True, f"rejects {label}")


def test_rotated_uses_unrotated_x(runner) -> None:
    print("\n4. the rotation: the LoRA adapts W, so its term is built from the UNROTATED x")
    ConvRotLinear = runner.make_convrot_linear(torch, nn, F)
    out_features, in_features, rank, group = 24, 16, 4, 4
    g = torch.Generator().manual_seed(41)
    w = torch.randn(out_features, in_features, generator=g) * 0.1
    rotation = torch.kron(A4, A4)[:group, :group] / group ** 0.5
    qw, sc = quantize(w, rotation, group)
    a = (torch.randn(rank, in_features, generator=g) * 0.05).to(torch.bfloat16)
    b = (torch.randn(out_features, rank, generator=g) * 0.05).to(torch.bfloat16)
    scale = 0.5  # deliberately large, so the wrong branch cannot hide inside the int8 floor
    x = torch.randn(3, in_features, generator=g, dtype=torch.float64)

    layer = ConvRotLinear(qw, sc, None, rotation, group, lora_a=a, lora_b=b, lora_scale=scale)
    w_deq = dequantized_weight(qw, sc, rotation, group)
    delta = reference_delta(b, a, scale)

    right = x @ (w_deq + delta).T  # the LoRA on the original weight -- what we want
    # The wrong implementation: feeding the rotated activation into A.  `x R` blockwise.
    xr = (x.reshape(x.shape[0], in_features // group, group) @ rotation.to(torch.float64)).reshape(x.shape)
    wrong = x @ w_deq.T + xr @ delta.T

    y = layer(x)
    check((y - right).abs().max().item() <= right.abs().max().item() * 1e-12,
          "the term uses the unrotated activation")
    gap = (right - wrong).abs().max().item()
    check((y - wrong).abs().max().item() > gap * 0.5,
          "and is measurably NOT the rotated-activation variant", f"the two differ by {gap:.3e}")


# ---------------------------------------------------------------------------------------------
# 5. The real turbo file: headers + alphas only, no tensor data.
# ---------------------------------------------------------------------------------------------

def test_real_file(runner) -> None:
    print("\n5. the real 8-step turbo LoRA (headers + 208 alpha scalars, no tensor data)")
    if not TURBO_LORA.exists():
        check(False, f"{TURBO_LORA.name} is on disk")
        return
    header = runner.read_header(TURBO_LORA)
    meta = runner.read_metadata(TURBO_LORA)
    pairs, stray = runner.scan_lora_header(header)
    check(len(pairs) == 208 and not stray, "624 tensors scan into 208 (A, B) pairs, 0 stray",
          f"{len(pairs)} pairs, {len(stray)} stray")
    pairs = runner.read_lora_alphas(TURBO_LORA, pairs, header)
    strengths = {round(p.strength, 6) for p in pairs.values()}
    check(strengths == {0.0625}, "every pair's alpha/rank is the file's declared training_scale",
          f"{sorted(strengths)} vs metadata {meta.get('training_scale')}")
    ranks = {p.rank for p in pairs.values()}
    check(ranks == {128, 384}, "ranks are 128, and 384 for the fused qkv (3 x 128)", str(sorted(ranks)))

    config = __import__("json").loads(runner.TRANSFORMER_CONFIG.read_text())
    for variant, dense_want, runtime_want in (("pruned", 312, 0), ("int8", 12, 300)):
        d_header = runner.read_header(runner.denoiser_path(variant))
        remap = runner.build_remap(config["num_layers"], config["num_refiner_layers"], variant)
        quant = (
            runner.build_quant_map(config["num_layers"], d_header,
                                   runner.read_comfy_quant(runner.denoiser_path(variant), d_header))
            if variant == "int8" else {}
        )
        plan = runner.build_lora_plan(TURBO_LORA, 1.0, d_header, remap, quant)
        check(not plan.shape_errors, f"{variant}: every pair fits its checkpoint weight",
              str(plan.shape_errors[:2]))
        check(not plan.unmatched, f"{variant}: 0 unmatched LoRA keys", str(plan.unmatched[:3]))
        check(len(plan.matched) == 208, f"{variant}: all 208 pairs matched", str(len(plan.matched)))
        check((len(plan.dense), len(plan.runtime)) == (dense_want, runtime_want),
              f"{variant}: {dense_want} merged + {runtime_want} runtime destinations",
              f"got {len(plan.dense)} + {len(plan.runtime)}")
        # The qkv pair must reach all three of to_q / to_k / to_v, on disjoint row ranges.
        dest = plan.runtime if variant == "int8" else plan.dense
        qkv = {k: v for k, v in dest.items()
               if v.pair.base == "blocks.0.attn.qkv_proj"}
        rows = sorted(v.row_slice for v in qkv.values())
        check(len(qkv) == 3 and rows == [(0, 7168), (7168, 14336), (14336, 21504)],
              f"{variant}: the fused qkv pair splits into three disjoint row ranges", str(rows))
        swi = [v for k, v in dest.items() if v.pair.base == "blocks.0.mlp.fc1"]
        check(len(swi) == 1 and swi[0].swap_halves,
              f"{variant}: the mlp.fc1 pair carries the SwiGLU half swap")


def test_arg_parsing(runner) -> None:
    print("\n6. --lora PATH[:scale] parsing")
    for value, want_path, want_scale in (
        ("/a/b.safetensors", "/a/b.safetensors", 1.0),
        ("/a/b.safetensors:0.8", "/a/b.safetensors", 0.8),
        ("/a/b.safetensors:1", "/a/b.safetensors", 1.0),
        ("/a/b.safetensors:0", "/a/b.safetensors", 0.0),
        ("/a/b.safetensors:-0.5", "/a/b.safetensors", -0.5),
        # A colon that is not a scale stays part of the path.
        ("/a:dir/b.safetensors", "/a:dir/b.safetensors", 1.0),
    ):
        path, scale = runner.parse_lora_arg(value)
        check(str(path) == want_path and scale == want_scale, f"{value!r} -> ({want_path}, {want_scale})",
              f"got ({path}, {scale})")


def main() -> int:
    runner = load_runner()
    test_merge(runner)
    test_output_axis(runner)
    test_runtime_term(runner)
    test_rotated_uses_unrotated_x(runner)
    test_real_file(runner)
    test_arg_parsing(runner)
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all checks passed: the merge is exact, the ConvRot runtime term is exact and additive, "
          "and the turbo LoRA maps onto both denoisers with nothing left over")
    return 0


if __name__ == "__main__":
    sys.exit(main())
