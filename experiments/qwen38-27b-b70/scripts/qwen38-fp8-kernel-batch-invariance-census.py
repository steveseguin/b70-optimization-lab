#!/usr/bin/env python3
"""Kernel-level batch-shape invariance census for the Qwen3.8-27B FP8 TP2 lane.

Operator diagnostic only; never a speed or quality claim.

The c1-versus-c2 token-identity gate in this lane is decided by an exact
float16 logit tie (R67: both candidate tokens at cache-c000 index 96 have the
same sequential logprob).  Any kernel whose per-row result depends on how many
other rows share the call (M), or on the row's position within the call,
therefore decides that tie differently under a different scheduler shape.
Instead of bisecting token streams one layer at a time, this script asks each
production kernel the question directly, on one XPU, with random data of the
real per-rank TP2 shapes:

  1. row invariance across M: is row r of gemm(A[:M]) bitwise equal to row r of
     gemm(A[:M']) for every pair (M, M') that this lane can schedule?
  2. position invariance at fixed M: does permuting rows permute the output
     bitwise?
  3. padding: do the real rows of a padded call depend on the pad contents?
  4. repeat determinism.
  5. auxiliary (rewritten 2026-10-04 for R310): the normalisation paths the
     R310 server executes by default, each with a row census (for M in
     NORM_M every row of the M-row call bit-identical to that row alone,
     shuffled rows, repeats), at TP2 and TP1 per-rank shapes:
       - GDN gated RMSNorm = RMSNormGated.forward_static compiled by Inductor
         (the R97/R99 arms of the older images no longer exist), plus the
         eager function and the non-default Triton layernorm_guard kernel;
       - decoder RMSNorm 5120 = GemmaRMSNorm.forward_native -> vllm.ir
         rms_norm / fused_add_rms_norm 'native' impls, Inductor and eager.
     See the block comment above NORM_M for how that was read from source.
  6. the host-side decode KV split plan for c1 versus cN at several depths.
Each auxiliary diagnostic is independent: one that cannot run records
{"status": "unavailable", "error": ...} and the rest still run.

Run inside the lane image. R310 (the shipped two-card image), auxiliary only:

  docker run --rm --network none --workdir /tmp --device /dev/dri:/dev/dri \
    --group-add <render gid> --ipc=host --shm-size=2g --memory 10g --memory-swap 10g \
    --entrypoint python3 \
    --env-file /mnt/fast-ai/bench-results/fp8-census-r310-20261004/env.list \
    -e ZE_AFFINITY_MASK=0 -e ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    -v $PWD/experiments/qwen38-27b-b70/scripts:/work:ro -v $OUT:/out \
    sha256:eb8165070409959c9ce4ba4c605ebaf2a39f82ce6b755e408241ab85b08b1e04 \
    /work/qwen38-fp8-kernel-batch-invariance-census.py --only-auxiliary \
    --out /out/kernel-census-aux-r310.json

Drop --only-auxiliary to rerun the GEMM census too (slow); --skip-auxiliary
runs only the GEMMs. The report's environment.vllm_file must point into
/opt/venv/lib/python3.12/site-packages (the copy the server imports), not
the image's /workspace source checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import time
from pathlib import Path

import torch

# Per-rank (TP2) GEMM shapes (K, N) derived from the checkpoint config.json:
# hidden 5120, intermediate 17408, 24 q heads x 256 (+ gate), 4 kv heads x 256,
# GDN 16 k heads x 128 and 48 v heads x 128, vocab 248320.
GEMMS: dict[str, tuple[int, int]] = {
    "gdn_in_proj_qkvz": (5120, 8192),
    "gdn_out_proj": (3072, 5120),
    "attn_qkv_proj": (5120, 7168),
    "attn_o_proj": (3072, 5120),
    "mlp_gate_up_proj": (5120, 17408),
    "mlp_down_proj": (8704, 5120),
    # CAUTION (2026-10-04): this entry runs the FP8 W8A16 kernel at the output layer's SHAPE. The lane's real output
    # layer is an FP16 F.linear, a different kernel with different row classes (bit-identical rows for 1..32 rows).
    # Its census is qwen38-fp8-output-layer-row-census.py; do not read this entry as the output layer.
    "lm_head": (5120, 124160),
}
# Decode shapes (c requests x 2 MTP1 rows), the fixture prefill shapes
# (31, 28, 59), and padding buckets.
M_VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 24, 28, 30, 31, 32, 48, 59, 60,
            64, 96, 128, 256, 512]
PERM_M = [2, 4, 6, 8, 16, 31, 59, 64, 128, 256]
PAD_BUCKETS = [32, 64, 128, 256, 512]
BLOCK = 128


def digest(t: torch.Tensor) -> str:
    return hashlib.sha256(
        t.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes()
    ).hexdigest()


def max_abs(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).abs().max().item()) if a.numel() else 0.0


def make_weight(gen, k: int, n: int, device, scale_dtype):
    w = (torch.randn((n, k), generator=gen, device="cpu") * 0.05)
    w_fp8 = w.to(torch.float8_e4m3fn).to(device)
    scales_t = (
        torch.rand((k // BLOCK, n // BLOCK), generator=gen, device="cpu") * 0.02
        + 0.005
    ).to(scale_dtype).to(device).contiguous()
    return w_fp8, scales_t


def gemm(a: torch.Tensor, w_fp8: torch.Tensor, scales_t: torch.Tensor):
    # Mirrors XPUFp8BlockScaledMMKernel with VLLM_XPU_FP8_BLOCK_W8A16=1:
    # fp8_gemm_w8a16(A, B.t(), Bs.t(), None) where B is [N, K] and Bs.t() is the
    # contiguous [k_blocks, n_blocks] scale buffer.
    return torch.ops._xpu_C.fp8_gemm_w8a16(a, w_fp8.t(), scales_t, None)


def time_call(fn, iters: int = 30, warmup: int = 10) -> float:
    # CR1 lesson: one warmup call plus ten timed iterations reported the attn
    # qkv M<=16 kernel at ~180 us; with a deeper warmup it measures ~65 us
    # (see bench-qwen38-fp8-w8a16-pad-overhead.py). Lazy first-call work in
    # oneDNN is not steady-state kernel latency.
    for _ in range(warmup):
        fn()
    torch.xpu.synchronize()
    start = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.xpu.synchronize()
    return (time.perf_counter() - start) / iters * 1e6


def census_gemm(name: str, k: int, n: int, device, gen, scale_dtype) -> dict:
    w_fp8, scales_t = make_weight(gen, k, n, device, scale_dtype)
    a_full = torch.randn((max(M_VALUES), k), generator=gen, device="cpu").to(
        torch.float16
    ).to(device)
    out_by_m: dict[int, torch.Tensor] = {}
    timing_us: dict[int, float] = {}
    for m in M_VALUES:
        a = a_full[:m].contiguous()
        out_by_m[m] = gemm(a, w_fp8, scales_t)
        timing_us[m] = time_call(lambda: gemm(a, w_fp8, scales_t))
    torch.xpu.synchronize()

    # Row-invariance classes: group M values by the bitwise value of row 0 and
    # of rows 0..1 (the two MTP1 rows of one request).
    row0_class: dict[str, list[int]] = {}
    for m in M_VALUES:
        row0_class.setdefault(digest(out_by_m[m][0:1]), []).append(m)
    classes = sorted(row0_class.values(), key=lambda ms: ms[0])
    prefix_vs_m1 = {}
    for m in M_VALUES:
        prefix_vs_m1[m] = {
            "row0_equal_M1": bool(torch.equal(out_by_m[m][0:1], out_by_m[1])),
            "row0_max_abs_vs_M1": max_abs(out_by_m[m][0:1], out_by_m[1]),
        }
    # Pairwise prefix consistency for the lane's important pairs.
    pairs = [(2, 4), (2, 6), (2, 8), (2, 16), (2, 30), (2, 32), (2, 64),
             (2, 128), (4, 8), (4, 128), (31, 59), (28, 59), (31, 256),
             (59, 64), (64, 128), (128, 256), (256, 512)]
    pairwise = {}
    for small, big in pairs:
        pairwise[f"{small}vs{big}"] = {
            "prefix_bitwise_equal": bool(
                torch.equal(out_by_m[big][:small], out_by_m[small])
            ),
            "prefix_max_abs": max_abs(out_by_m[big][:small], out_by_m[small]),
        }

    # Position invariance at fixed M.
    position = {}
    for m in PERM_M:
        x = a_full[:m].contiguous()
        perm = torch.randperm(m, generator=gen).to(device)
        out_x = gemm(x, w_fp8, scales_t)
        out_p = gemm(x[perm].contiguous(), w_fp8, scales_t)
        position[m] = {
            "permuted_rows_bitwise_equal": bool(torch.equal(out_p, out_x[perm])),
            "max_abs": max_abs(out_p, out_x[perm]),
        }

    # Padding: real rows of a padded call versus pad contents and natural M.
    real_m = 31
    x_real = a_full[:real_m]
    natural = gemm(x_real.contiguous(), w_fp8, scales_t)
    padding = {}
    for bucket in PAD_BUCKETS:
        pad_zero = torch.zeros((bucket, k), dtype=torch.float16, device=device)
        pad_zero[:real_m] = x_real
        pad_rand = torch.randn((bucket, k), generator=gen, device="cpu").to(
            torch.float16
        ).to(device)
        pad_rand[:real_m] = x_real
        out_zero = gemm(pad_zero, w_fp8, scales_t)[:real_m]
        out_rand = gemm(pad_rand, w_fp8, scales_t)[:real_m]
        padding[bucket] = {
            "real_rows_independent_of_pad_contents": bool(
                torch.equal(out_zero, out_rand)
            ),
            "real_rows_equal_natural_M31": bool(torch.equal(out_zero, natural)),
            "max_abs_vs_natural_M31": max_abs(out_zero, natural),
        }

    determinism = {}
    for m in (2, 4, 59, 128):
        x = a_full[:m].contiguous()
        determinism[m] = bool(
            torch.equal(gemm(x, w_fp8, scales_t), gemm(x, w_fp8, scales_t))
        )

    del out_by_m, w_fp8, scales_t, a_full
    torch.xpu.synchronize()
    torch.xpu.empty_cache()
    return {
        "shape_per_rank": {"K": k, "N": n},
        "row0_invariance_classes_by_M": classes,
        "row_invariant_across_all_M": len(classes) == 1,
        "prefix_vs_M1": prefix_vs_m1,
        "pairwise_prefix": pairwise,
        "position_invariance_at_fixed_M": position,
        "padding_M31": padding,
        "repeat_deterministic": determinism,
        "latency_us_by_M": timing_us,
    }


# ---------------------------------------------------------------------------
# Auxiliary census: the normalisation paths the R310 server really executes.
#
# What R310 runs (read from the image's site-packages, 2026-10-04):
#   * The lane compiles with CompilationMode.VLLM_COMPILE + Inductor, so
#     CompilationConfig.custom_ops defaults to ["none"] (vllm/config/vllm.py)
#     and every CustomOp takes forward_native, traced into the Inductor graph.
#     IR op priority on XPU under Inductor is ['native'] (platforms/xpu.py
#     get_default_ir_op_priority), matching the server log line.
#   * GDN gated RMSNorm: QwenGatedDeltaNetAttention.forward_xpu calls
#     self.norm(core_attn_out.reshape(-1, 128), z.reshape(-1, 128)) after the
#     gdn_attention_core_xpu custom op. self.norm is RMSNormGated(128,
#     eps=rms_norm_eps=1e-6, group_size=None, norm_before_gate=True,
#     activation="silu"), weight in the model dtype (float16). Disabled custom
#     op => RMSNormGated.forward_static, Inductor-generated. The same code runs
#     for single- and multi-request steps (no arm selection any more).
#     VLLM_XPU_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT, VLLM_XPU_GDN_ROW_STABLE_RMSNORM,
#     VLLM_XPU_RMSNORM_TRITON and VLLM_XPU_GEMMA_RMSNORM_TRITON are not read
#     anywhere in R310 (dead in the shipped env). The non-default forward_xpu
#     (layernorm_guard.rmsnorm_fn Triton kernel) only runs with
#     custom_ops "+rms_norm_gated"; it is censused as a non-default arm.
#   * Decoder RMSNorm (hidden 5120): Qwen3_5RMSNorm is GemmaRMSNorm. Disabled
#     custom op => forward_native: weight = self.weight.float() + 1.0, then
#     ir.ops.rms_norm (layer-0 input norm) or ir.ops.fused_add_rms_norm (every
#     other input/post-attention norm and the final norm), lowered by
#     VllmIRLoweringPass to the 'native' impl in vllm/ir/ops/layernorm.py and
#     fused by Inductor. VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1
#     (shipped; default 0) only changes the x.shape[0] == 2 case, which it
#     computes row by row (so it is row-invariant by construction).
#     VLLM_BATCH_INVARIANT only affects the plain RMSNorm class, not this one.
# Server-like compilation: torch.compile(fullgraph=True) of the real image
# function, dim 0 marked dynamic, first traced at the profile-run size
# (max_num_batched_tokens=4096), all Dynamo guards dropped as vLLM does
# (vllm/compilation/wrapper.py), and the shipped inductor_compile_config.
# Standalone compilation is not the server's fused graph; a pass here clears
# the reduction's row structure, not every possible neighbour fusion.
# ---------------------------------------------------------------------------
NORM_M = [1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 17, 24, 31, 32, 33, 48, 64, 128, 192, 248, 256, 384, 512]
NORM_PERM_M = [2, 6, 17, 33, 64, 128]
NORM_REPEAT_M = [1, 6, 33, 128]
NORM_HINT_M = 4096  # --max-num-batched-tokens of both shipped launchers
GDN_HEADS_LOCAL = {"tp2": 24, "tp1": 48}  # 48 linear value heads / TP
HEAD_V_DIM = 128
HIDDEN = 5120
RMS_EPS = 1e-6  # config.json rms_norm_eps (also the GDN norm eps)
SERVER_INDUCTOR_CONFIG = {  # packages/qwen38-27b-fp8-tp*-b70/scripts/serve.py
    "combo_kernels": False,
    "benchmark_combo_kernel": False,
    "deterministic": True,
    "triton.autotune_pointwise": False,
    "benchmark_epilogue_fusion": False,
}


def bits(t: torch.Tensor) -> torch.Tensor:
    """Bit pattern view, so NaN == NaN and -0.0 != +0.0."""
    t = t.detach().contiguous()
    if t.element_size() == 2:
        return t.view(torch.int16)
    if t.element_size() == 4:
        return t.view(torch.int32)
    return t.view(torch.uint8)


def bit_equal(a: torch.Tensor, b: torch.Tensor) -> bool:
    return a.shape == b.shape and bool(torch.equal(bits(a), bits(b)))


def as_tuple(out) -> tuple:
    return tuple(out) if isinstance(out, (tuple, list)) else (out,)


def sync(device) -> None:
    if torch.device(device).type == "xpu":
        torch.xpu.synchronize()


def row_census(fn, inputs: list, device) -> dict:
    """Row invariance of fn over dim 0 (tokens).

    For every M in NORM_M each row of fn(inputs[:M]) must be bit-identical to
    the same row computed alone (fn(inputs[r:r+1])); rows permuted at fixed M
    must give permuted outputs; repeated calls must be identical.
    """
    max_m = max(NORM_M)
    alone = [as_tuple(fn(*[t[r:r + 1].contiguous() for t in inputs]))
             for r in range(max_m)]
    n_out = len(alone[0])
    alone_cat = [torch.cat([a[k] for a in alone], dim=0) for k in range(n_out)]
    by_m, outs = {}, {}
    for m in NORM_M:
        out = as_tuple(fn(*[t[:m].contiguous() for t in inputs]))
        outs[m] = out
        bad = torch.zeros(m, dtype=torch.bool, device=out[0].device)
        worst = 0.0
        for k in range(n_out):
            diff = bits(out[k]) != bits(alone_cat[k][:m])
            bad |= diff.reshape(m, -1).any(dim=1)
            worst = max(worst, max_abs(out[k], alone_cat[k][:m]))
        bad_rows = torch.nonzero(bad).flatten().tolist()
        by_m[m] = {"rows_equal_alone": not bad_rows,
                   "mismatching_rows_first8": bad_rows[:8],
                   "mismatching_row_count": len(bad_rows),
                   "max_abs_vs_alone": worst}
    gen = torch.Generator(device="cpu").manual_seed(4242)
    position = {}
    for m in NORM_PERM_M:
        perm = torch.randperm(m, generator=gen).to(inputs[0].device)
        out_p = as_tuple(fn(*[t[:m][perm].contiguous() for t in inputs]))
        position[m] = all(bit_equal(out_p[k], outs[m][k][perm])
                          for k in range(n_out))
    repeat = {}
    for m in NORM_REPEAT_M:
        a = as_tuple(fn(*[t[:m].contiguous() for t in inputs]))
        b = as_tuple(fn(*[t[:m].contiguous() for t in inputs]))
        repeat[m] = all(bit_equal(a[k], b[k]) for k in range(n_out))
    sync(device)
    first_bad = next((m for m in NORM_M if not by_m[m]["rows_equal_alone"]), None)
    return {
        "status": "ok",
        "row_invariant_all_M": first_bad is None,
        "first_failing_M": first_bad,
        "by_M": by_m,
        "position_invariant_by_M": position,
        "position_invariant_all": all(position.values()),
        "repeat_deterministic_by_M": repeat,
        "repeat_deterministic_all": all(repeat.values()),
        "_out_M33": outs[33],
    }


def _inductor_options() -> dict:
    import torch._inductor.config as ic
    opts = {}
    for key, value in SERVER_INDUCTOR_CONFIG.items():
        obj = ic
        *parents, leaf = key.split(".")
        for p in parents:
            obj = getattr(obj, p, None)
        if obj is not None and hasattr(obj, leaf):
            opts[key] = value
    return opts


def compile_server_like(fn, hint_inputs: list):
    """torch.compile fn the way vLLM compiles the model graph (see above)."""
    torch._dynamo.reset()
    opts = _inductor_options()
    guard_filter = getattr(torch.compiler, "skip_all_guards_unsafe", None) or (
        lambda entries: [False for _ in entries])
    meta = {"inductor_options": opts, "hint_rows": int(hint_inputs[0].shape[0]),
            "guards_dropped": True, "fallback_error": None}
    try:
        compiled = torch.compile(fn, fullgraph=True, dynamic=False,
                                 options={**opts, "guard_filter_fn": guard_filter})
        for t in hint_inputs:
            torch._dynamo.mark_dynamic(t, 0)
        compiled(*hint_inputs)
    except Exception as exc:  # noqa: BLE001  (older torch: no guard_filter_fn)
        torch._dynamo.reset()
        meta.update(guards_dropped=False, fallback_error=repr(exc))
        compiled = torch.compile(fn, fullgraph=True, dynamic=True, options=opts)
        compiled(*hint_inputs)
    return compiled, meta


def _rand(gen, shape, scale, device, dtype=torch.float16):
    return (torch.randn(shape, generator=gen, device="cpu") * scale).to(dtype).to(device)


def _run_arms(arms: list, device) -> tuple[dict, dict]:
    """arms: (label, default_path, builder) with builder() -> (fn, inputs, meta).

    Each arm is independent: a failure records status unavailable and the
    remaining arms still run.
    """
    result, outs = {}, {}
    for label, is_default, builder in arms:
        t0 = time.perf_counter()
        try:
            torch._dynamo.utils.counters.clear()
            fn, inputs, meta = builder()
            entry = row_census(fn, inputs, device)
            outs[label] = entry.pop("_out_M33")
            entry.update(meta)
            if meta:  # compiled arm: 1 == one dynamic graph served every M (as in vLLM)
                entry["dynamo_unique_graphs"] = int(
                    torch._dynamo.utils.counters["stats"]["unique_graphs"])
        except Exception as exc:  # noqa: BLE001
            entry = {"status": "unavailable", "error": repr(exc)}
        entry["server_default_path"] = is_default
        entry["census_seconds"] = round(time.perf_counter() - t0, 1)
        result[label] = entry
        if entry["status"] == "ok":
            print(f"CENSUS {label} row_invariant_all_M={entry['row_invariant_all_M']}"
                  f" first_failing_M={entry['first_failing_M']}"
                  f" position_ok={entry['position_invariant_all']}"
                  f" repeat_ok={entry['repeat_deterministic_all']}", flush=True)
        else:
            print(f"CENSUS {label} status=unavailable error={entry['error'][:160]}",
                  flush=True)
    return result, outs


def census_gdn_norm(device, gen) -> dict:
    """GDN gated RMSNorm, per-rank heads for TP2 (24) and TP1 (48)."""
    from vllm.model_executor.layers.layernorm import RMSNormGated

    static = RMSNormGated.forward_static
    weight = (_rand(gen, (HEAD_V_DIM,), 0.1, "cpu", torch.float32) + 1.0).to(
        torch.float16).to(device)
    result: dict = {"source": "vllm.model_executor.layers.layernorm.RMSNormGated",
                    "eps": RMS_EPS, "activation": "silu", "norm_before_gate": True}
    for tp, heads in GDN_HEADS_LOCAL.items():
        x_full = _rand(gen, (NORM_HINT_M, heads, HEAD_V_DIM), 0.5, device)
        z_full = _rand(gen, (NORM_HINT_M, heads, HEAD_V_DIM), 0.5, device)

        def gated(x, z):
            return static(x.reshape(-1, HEAD_V_DIM), z.reshape(-1, HEAD_V_DIM),
                          weight, RMS_EPS, x.dtype, None, True, "silu"
                          ).reshape(x.shape)

        def build_inductor():
            compiled, meta = compile_server_like(
                gated, [x_full.clone(), z_full.clone()])
            return compiled, [x_full, z_full], meta

        def build_eager():
            return gated, [x_full, z_full], {}

        def build_triton_guard():
            from vllm.third_party.flash_linear_attention.ops.layernorm_guard import (
                rmsnorm_fn,
            )

            def fn(x, z):
                return rmsnorm_fn(x.reshape(-1, HEAD_V_DIM), weight, None,
                                  z=z.reshape(-1, HEAD_V_DIM), eps=RMS_EPS,
                                  group_size=None, norm_before_gate=True,
                                  activation="silu").reshape(x.shape)
            return fn, [x_full, z_full], {}

        arms = [
            (f"gdn_norm_{tp}_inductor_forward_static", True, build_inductor),
            (f"gdn_norm_{tp}_eager_forward_static", False, build_eager),
            (f"gdn_norm_{tp}_triton_layernorm_guard_not_default", False,
             build_triton_guard),
        ]
        arm_results, outs = _run_arms(arms, device)
        cross = {}
        ref = f"gdn_norm_{tp}_eager_forward_static"
        for label in outs:
            if label != ref and ref in outs:
                cross[f"{label}_vs_eager_bitwise_M33"] = bit_equal(outs[label][0],
                                                                  outs[ref][0])
                cross[f"{label}_vs_eager_max_abs_M33"] = max_abs(outs[label][0],
                                                                outs[ref][0])
        result[tp] = {"heads_local": heads, "arms": arm_results,
                      "cross_arm_informational": cross}
        del x_full, z_full
    torch._dynamo.reset()
    return result


def census_plain_rmsnorm(device, gen) -> dict:
    """Decoder RMSNorm (GemmaRMSNorm, width 5120) through the IR 'native' impls."""
    try:
        from vllm import ir
        rms_native = ir.ops.rms_norm.impls["native"].impl_fn
        add_native = ir.ops.fused_add_rms_norm.impls["native"].impl_fn
        source = "vllm.ir.ops.{rms_norm,fused_add_rms_norm}.impls['native'].impl_fn"
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "error": f"vllm.ir native impls: {exc!r}"}

    gemma_weight = _rand(gen, (HIDDEN,), 0.1, device)  # checkpoint stores w, not 1+w
    x_full = _rand(gen, (NORM_HINT_M, HIDDEN), 1.0, device)
    r_full = _rand(gen, (NORM_HINT_M, HIDDEN), 1.0, device)

    def gemma_rms(x):  # GemmaRMSNorm.forward_native, residual None
        return rms_native(x, gemma_weight.float() + 1.0, RMS_EPS)

    def gemma_add_rms(x, residual):  # GemmaRMSNorm.forward_native with residual
        return add_native(x, residual, gemma_weight.float() + 1.0, RMS_EPS)

    def compiled_builder(fn, inputs):
        def build():
            compiled, meta = compile_server_like(fn, [t.clone() for t in inputs])
            return compiled, inputs, meta
        return build

    arms = [
        ("rmsnorm5120_inductor_native_rms_norm", True,
         compiled_builder(gemma_rms, [x_full])),
        ("rmsnorm5120_inductor_native_fused_add_rms_norm", True,
         compiled_builder(gemma_add_rms, [x_full, r_full])),
        ("rmsnorm5120_eager_native_rms_norm", False,
         lambda: (gemma_rms, [x_full], {})),
        ("rmsnorm5120_eager_native_fused_add_rms_norm", False,
         lambda: (gemma_add_rms, [x_full, r_full], {})),
    ]
    arm_results, outs = _run_arms(arms, device)
    cross = {}
    for kind in ("rms_norm", "fused_add_rms_norm"):
        a, b = (f"rmsnorm5120_inductor_native_{kind}",
                f"rmsnorm5120_eager_native_{kind}")
        if a in outs and b in outs:
            cross[f"{kind}_inductor_vs_eager_bitwise_M33"] = all(
                bit_equal(p, q) for p, q in zip(outs[a], outs[b]))
            cross[f"{kind}_inductor_vs_eager_max_abs_M33"] = max(
                max_abs(p, q) for p, q in zip(outs[a], outs[b]))
    torch._dynamo.reset()
    return {"status": "ok", "source": source, "width": HIDDEN, "eps": RMS_EPS,
            "weight": "GemmaRMSNorm: float32 (w + 1)",
            "packed_serial_exact_note": (
                "VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT=1 computes an "
                "M == 2 call as two one-row calls; row-invariant by construction"),
            "arms": arm_results, "cross_arm_informational": cross}


def census_decode_split_plan(device) -> dict:
    try:
        import vllm_xpu_kernels.flash_attn_interface as fai
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}
    kv_tile = fai._kv_tile_from_block_size(64)
    xe_cores = fai._infer_num_xe_cores(device)
    heads_kv_local = 2  # 4 kv heads / TP2
    cap = 32
    depths = [64, 128, 256, 1024, 2048, 4096, 8192, 16384, 32768]
    rows = {}
    for depth in depths:
        c1, _ = fai.build_decode_split_plan([depth], kv_tile, cap, xe_cores,
                                           heads_kv_local)
        c2, _ = fai.build_decode_split_plan([depth, depth - 3], kv_tile, cap,
                                           xe_cores, heads_kv_local)
        c64, _ = fai.build_decode_split_plan([depth] * 64, kv_tile, cap,
                                            xe_cores, heads_kv_local)
        rows[depth] = {
            "c1_splits_seq0": int(c1[0]),
            "c2_splits_seq0": int(c2[0]),
            "c64_splits_seq0": int(c64[0]),
            "seq0_plan_invariant_c1_c2_c64": int(c1[0]) == int(c2[0]) == int(c64[0]),
        }
    # Does the installed vLLM actually request split-KV planning?
    try:
        import vllm._xpu_ops as xo
        src = inspect.getsource(xo)
        passes_num_splits_kv = "num_splits_kv" in src
    except Exception:  # noqa: BLE001
        passes_num_splits_kv = None
    return {
        "kv_tile": kv_tile,
        "inferred_xe_cores": xe_cores,
        "min_blocks_for_split": fai._min_blocks_for_split(kv_tile),
        "single_split_below_tokens": fai._min_blocks_for_split(kv_tile) * kv_tile,
        "installed_vllm_xpu_ops_mentions_num_splits_kv": passes_num_splits_kv,
        "by_depth": rows,
        "note": "Host-side plan only. A sequence shorter than single_split_below_tokens is always one split, so the 256-token fixture cannot see this effect; deeper contexts can.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260902)
    parser.add_argument("--skip-lm-head", action="store_true")
    parser.add_argument("--skip-auxiliary", action="store_true")
    parser.add_argument("--only-auxiliary", action="store_true",
                        help="skip the (slow) GEMM census; run only the "
                             "normalisation and split-plan diagnostics")
    parser.add_argument("--device", default="xpu:0",
                        help="debug only: 'cpu' smoke-tests the auxiliary "
                             "norm census without a GPU")
    args = parser.parse_args()
    if args.only_auxiliary and args.skip_auxiliary:
        raise SystemExit("--only-auxiliary and --skip-auxiliary are exclusive")

    device = torch.device(args.device)
    if device.type == "xpu":
        if not torch.xpu.is_available():
            raise SystemExit("XPU is required")
        props = torch.xpu.get_device_properties(device.index or 0)
    elif not args.only_auxiliary:
        raise SystemExit("--device cpu is only supported with --only-auxiliary")
    else:
        props = None
    import vllm  # noqa: F401
    if device.type == "xpu":
        import vllm._xpu_ops  # noqa: F401
        import vllm_xpu_kernels._xpu_C  # noqa: F401  (registers _xpu_C ops)
    if not args.only_auxiliary and not hasattr(torch.ops._xpu_C, "fp8_gemm_w8a16"):
        raise SystemExit("_xpu_C::fp8_gemm_w8a16 is missing in this image")

    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    scale_dtype = torch.float32
    # Probe the scale dtype the kernel accepts.
    if not args.only_auxiliary:
        try:
            w, s = make_weight(gen, 256, 256, device, torch.float32)
            gemm(torch.zeros((2, 256), dtype=torch.float16, device=device), w, s)
        except Exception:  # noqa: BLE001
            scale_dtype = torch.float16

    report: dict = {
        "schema": "neural.download.qwen38-fp8-kernel-batch-invariance-census.v2",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": props.name if props is not None else str(device),
            "driver_version": getattr(props, "driver_version", None),
            "eu_count": getattr(props, "gpu_eu_count", None),
            "torch": torch.__version__,
            "vllm": getattr(vllm, "__version__", None),
            "vllm_file": getattr(vllm, "__file__", None),
            "python": platform.python_version(),
            "scale_dtype_used": str(scale_dtype),
            "seed": args.seed,
        },
        "gemm_w8a16": {},
    }
    try:
        import triton
        report["environment"]["triton"] = triton.__version__
    except Exception:  # noqa: BLE001
        pass

    args.out.parent.mkdir(parents=True, exist_ok=True)

    if args.only_auxiliary:
        report["gemm_w8a16"] = {"status": "skipped-by-request (--only-auxiliary)"}
    for name, (k, n) in ({} if args.only_auxiliary else GEMMS).items():
        if args.skip_lm_head and name == "lm_head":
            continue
        t0 = time.perf_counter()
        report["gemm_w8a16"][name] = census_gemm(name, k, n, device, gen,
                                                 scale_dtype)
        report["gemm_w8a16"][name]["census_seconds"] = round(
            time.perf_counter() - t0, 1
        )
        # Preserve completed expensive shapes if a later, unrelated auxiliary
        # diagnostic is unavailable in a particular lane image.
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
        print(f"[census] {name}: classes={report['gemm_w8a16'][name]['row0_invariance_classes_by_M']}", flush=True)

    if args.skip_auxiliary:
        report["auxiliary_diagnostics"] = {"status": "skipped-by-request"}
    else:
        # Each diagnostic is independent: one that cannot run in this image
        # records {"status": "unavailable"} and the others still run; the JSON
        # is rewritten after each so a later crash keeps earlier results.
        aux = (("gdn_gated_rmsnorm", census_gdn_norm),
               ("plain_rmsnorm_5120", census_plain_rmsnorm),
               ("decode_kv_split_plan", lambda d, g: census_decode_split_plan(d)))
        for key, fn in aux:
            if key == "decode_kv_split_plan" and device.type != "xpu":
                report[key] = {"status": "unavailable", "error": "needs an XPU"}
                continue
            try:
                report[key] = fn(device, gen)
                if isinstance(report[key], dict) and "error" in report[key]:
                    report[key].setdefault("status", "unavailable")
            except Exception as exc:  # noqa: BLE001
                report[key] = {"status": "unavailable", "error": repr(exc)}
            report[key].setdefault("status", "ok")
            print(f"CENSUS {key} status={report[key]['status']}", flush=True)
            args.out.write_text(json.dumps(report, indent=1, sort_keys=True,
                                           default=str))

    args.out.write_text(json.dumps(report, indent=1, sort_keys=True, default=str))
    summary = {}
    for key in ("gdn_gated_rmsnorm", "plain_rmsnorm_5120"):
        sec = report.get(key, {})
        arms = {}
        for part in ([sec] + [v for v in sec.values() if isinstance(v, dict)]):
            arms.update(part.get("arms", {}) if isinstance(part, dict) else {})
        for label, arm in arms.items():
            summary[label] = (arm.get("row_invariant_all_M")
                              if arm.get("status") == "ok" else "unavailable")
    print(json.dumps({"row_invariant_all_M_by_arm": summary}, indent=1,
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
