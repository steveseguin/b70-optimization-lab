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
  5. the GDN gated RMSNorm arms (R99 single-request, R97 multi-request) and the
     eager / Inductor references.
  6. the host-side decode KV split plan for c1 versus cN at several depths.

Run inside the lane image, e.g.

  docker run --rm --workdir /tmp --device /dev/dri:/dev/dri --group-add render \
    --ipc=host --shm-size=2g --memory 8g --entrypoint python3 \
    -e ONEAPI_DEVICE_SELECTOR=level_zero:1 -e VLLM_TARGET_DEVICE=xpu \
    -v $PWD/experiments/qwen38-27b-b70/scripts:/work:ro -v $OUT:/out \
    <image> /work/qwen38-fp8-kernel-batch-invariance-census.py --out /out/census.json
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


def time_call(fn, iters: int = 20) -> float:
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
        timing_us[m] = time_call(lambda: gemm(a, w_fp8, scales_t), iters=10)
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


def census_gdn_norm(device, gen) -> dict:
    from vllm.model_executor.layers.layernorm import RMSNormGated
    from vllm.model_executor.layers.mamba.gdn import qwen_gdn_linear_attn as q

    impl = q._xpu_qwen_gdn_runtime_selected_rmsnorm_gated_impl
    heads_local = 24  # 48 v heads / TP2
    rows = 512
    x_full = (torch.randn((rows, heads_local, 128), generator=gen, device="cpu")
              * 0.5).to(torch.float16).to(device)
    z_full = (torch.randn((rows, heads_local, 128), generator=gen, device="cpu")
              * 0.5).to(torch.float16).to(device)
    weight = (torch.randn((128,), generator=gen, device="cpu") * 0.1 + 1.0).to(
        torch.float16
    ).to(device)
    eps = 1e-6

    def r99(m):
        return impl(x_full[:m].contiguous(), z_full[:m].contiguous(), weight,
                    eps, multi_request=False)

    def r97(m):
        return impl(x_full[:m].contiguous(), z_full[:m].contiguous(), weight,
                    eps, multi_request=True)

    def eager(m):
        return RMSNormGated.forward_static(
            x_full[:m].reshape(-1, 128).contiguous(),
            z_full[:m].reshape(-1, 128).contiguous(),
            weight, eps, torch.float16, group_size=None,
            norm_before_gate=True, activation="silu",
        ).reshape(m, heads_local, 128)

    compiled_static = torch.compile(RMSNormGated.forward_static, dynamic=True)

    def inductor(m):
        return compiled_static(
            x_full[:m].reshape(-1, 128).contiguous(),
            z_full[:m].reshape(-1, 128).contiguous(),
            weight, eps, torch.float16, None, True, "silu",
        ).reshape(m, heads_local, 128)

    ms = [1, 2, 4, 8, 31, 59, 64, 128, 512]
    result = {"arms": {}, "cross_arm": {}}
    outs = {}
    for label, fn in (("r99_single_request_arm", r99),
                      ("r97_multi_request_arm", r97),
                      ("eager_forward_static", eager),
                      ("inductor_forward_static_standalone", inductor)):
        try:
            outs[label] = {m: fn(m) for m in ms}
        except Exception as exc:  # noqa: BLE001
            result["arms"][label] = {"error": repr(exc)}
            continue
        base = outs[label][1]
        row_inv = {m: bool(torch.equal(outs[label][m][0:1], base)) for m in ms}
        result["arms"][label] = {
            "row0_invariant_across_M": row_inv,
            "row_invariant_across_all_M": all(row_inv.values()),
            "repeat_deterministic": bool(torch.equal(fn(59), fn(59))),
        }
    if "r99_single_request_arm" in outs and "r97_multi_request_arm" in outs:
        a = outs["r99_single_request_arm"][59]
        b = outs["r97_multi_request_arm"][59]
        result["cross_arm"]["r99_vs_r97_same_rows_bitwise_equal"] = bool(
            torch.equal(a, b)
        )
        result["cross_arm"]["r99_vs_r97_max_abs"] = max_abs(a, b)
        result["cross_arm"]["r99_vs_r97_differing_rows_of_59x24"] = int(
            (a != b).any(dim=-1).sum().item()
        )
    for label in ("r99_single_request_arm", "r97_multi_request_arm",
                  "inductor_forward_static_standalone"):
        if label in outs and "eager_forward_static" in outs:
            result["cross_arm"][f"{label}_vs_eager_max_abs"] = max_abs(
                outs[label][59], outs["eager_forward_static"][59]
            )
            result["cross_arm"][f"{label}_vs_eager_bitwise"] = bool(
                torch.equal(outs[label][59], outs["eager_forward_static"][59])
            )
    return result


def census_plain_rmsnorm(device, gen) -> dict:
    """Decoder input/post-attention RMSNorm (width 5120) under Inductor."""
    width = 5120
    x_full = torch.randn((512, width), generator=gen, device="cpu").to(
        torch.float16
    ).to(device)
    weight = (torch.randn((width,), generator=gen, device="cpu") * 0.1 + 1.0).to(
        torch.float16
    ).to(device)

    def rmsnorm(x, w, eps: float = 1e-6):
        xf = x.float()
        var = xf.pow(2).mean(dim=-1, keepdim=True)
        return (xf * torch.rsqrt(var + eps)).to(x.dtype) * w

    compiled = torch.compile(rmsnorm, dynamic=True)
    ms = [1, 2, 4, 8, 31, 59, 64, 128, 512]
    out = {}
    try:
        eager = {m: rmsnorm(x_full[:m].contiguous(), weight) for m in ms}
        comp = {m: compiled(x_full[:m].contiguous(), weight) for m in ms}
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}
    out["eager_row0_invariant_across_M"] = all(
        torch.equal(eager[m][0:1], eager[1]) for m in ms
    )
    out["inductor_standalone_row0_invariant_across_M"] = all(
        torch.equal(comp[m][0:1], comp[1]) for m in ms
    )
    out["inductor_vs_eager_bitwise_M59"] = bool(torch.equal(comp[59], eager[59]))
    out["inductor_vs_eager_max_abs_M59"] = max_abs(comp[59], eager[59])
    return out


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
    args = parser.parse_args()

    if not torch.xpu.is_available():
        raise SystemExit("XPU is required")
    device = torch.device("xpu:0")
    props = torch.xpu.get_device_properties(0)
    import vllm  # noqa: F401  (registers _xpu_C ops)
    import vllm._xpu_ops  # noqa: F401
    if not hasattr(torch.ops._xpu_C, "fp8_gemm_w8a16"):
        raise SystemExit("_xpu_C::fp8_gemm_w8a16 is missing in this image")

    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    scale_dtype = torch.float32
    # Probe the scale dtype the kernel accepts.
    try:
        w, s = make_weight(gen, 256, 256, device, torch.float32)
        gemm(torch.zeros((2, 256), dtype=torch.float16, device=device), w, s)
    except Exception:  # noqa: BLE001
        scale_dtype = torch.float16

    report: dict = {
        "schema": "neural.download.qwen38-fp8-kernel-batch-invariance-census.v1",
        "classification": "operator-diagnostic-only",
        "environment": {
            "device": props.name,
            "driver_version": getattr(props, "driver_version", None),
            "eu_count": getattr(props, "gpu_eu_count", None),
            "torch": torch.__version__,
            "vllm": getattr(vllm, "__version__", None),
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

    for name, (k, n) in GEMMS.items():
        if args.skip_lm_head and name == "lm_head":
            continue
        t0 = time.perf_counter()
        report["gemm_w8a16"][name] = census_gemm(name, k, n, device, gen,
                                                 scale_dtype)
        report["gemm_w8a16"][name]["census_seconds"] = round(
            time.perf_counter() - t0, 1
        )
        print(f"[census] {name}: classes={report['gemm_w8a16'][name]['row0_invariance_classes_by_M']}", flush=True)

    report["gdn_gated_rmsnorm"] = census_gdn_norm(device, gen)
    report["plain_rmsnorm_5120"] = census_plain_rmsnorm(device, gen)
    report["decode_kv_split_plan"] = census_decode_split_plan(device)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps({k: v for k, v in report.items() if k != "gemm_w8a16"},
                     indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
