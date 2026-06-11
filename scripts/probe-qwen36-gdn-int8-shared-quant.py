#!/usr/bin/env python3
"""Probe shared per-token INT8 quant inputs for Qwen3.6 GDN projections.

This isolates the native XPU path used by
VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT={1,true,clone}.  The accepted production mode
uses `clone`; the faster rejected mode feeds the same quantized activation and
scale tensors into both qkvz and ba W8A8 INT8 GEMMs.  This probe checks whether
that sharing mutates inputs or changes outputs in eager and torch.compile modes.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any


def configure_paths() -> None:
    if os.environ.get("VLLM_XPU_PROBE_NO_DEFAULT_PATHS") == "1":
        return

    repo_paths = ["/home/steve/src/vllm", "/home/steve/src/vllm-xpu-kernels"]
    py_path = os.environ.get("PYTHONPATH", "")
    for path in reversed(repo_paths):
        if path not in py_path.split(":"):
            py_path = f"{path}:{py_path}" if py_path else path
    os.environ["PYTHONPATH"] = py_path

    lib_paths = [
        "/home/steve/.venvs/vllm-xpu/lib",
        "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib",
        "/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels",
        "/opt/intel/oneapi/compiler/2025.3/lib",
        "/opt/intel/oneapi/compiler/2026.0/lib",
    ]
    ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    for path in reversed(lib_paths):
        if path not in ld_path.split(":"):
            ld_path = f"{path}:{ld_path}" if ld_path else path
    os.environ["LD_LIBRARY_PATH"] = ld_path


configure_paths()

import torch  # noqa: E402
import vllm_xpu_kernels._xpu_C  # noqa: F401,E402

try:
    from vllm.model_executor.kernels.linear.scaled_mm.xpu import (
        _register_int8_gemm_w8a8_fake,
        _register_int8_per_token_quant_fake,
    )

    _register_int8_gemm_w8a8_fake()
    _register_int8_per_token_quant_fake()
except Exception:
    pass


def sync() -> None:
    torch.xpu.synchronize()


def tensor_stats_delta(a: torch.Tensor, b: torch.Tensor) -> dict[str, Any]:
    diff = (a.to(torch.float32) - b.to(torch.float32)).abs()
    if diff.numel() == 0:
        return {"max_abs": 0.0, "nonzero": 0}
    return {
        "max_abs": float(diff.max().item()),
        "nonzero": int((diff != 0).sum().item()),
    }


def make_inputs(
    *,
    m: int,
    k: int,
    n_qkvz: int,
    n_ba: int,
    seed: int,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    torch.manual_seed(seed)
    x = torch.randn((m, k), device=device, dtype=torch.bfloat16)
    w_qkvz = torch.randint(
        -127, 128, (k, n_qkvz), device=device, dtype=torch.int8
    )
    w_ba = torch.randint(-127, 128, (k, n_ba), device=device, dtype=torch.int8)
    s_qkvz = (torch.rand((n_qkvz,), device=device, dtype=torch.float32) + 0.01)
    s_ba = (torch.rand((n_ba,), device=device, dtype=torch.float32) + 0.01)
    return x, w_qkvz, s_qkvz, w_ba, s_ba


def shared_pair(
    x: torch.Tensor,
    w_qkvz: torch.Tensor,
    s_qkvz: torch.Tensor,
    w_ba: torch.Tensor,
    s_ba: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    x_q, x_s = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
    y_qkvz = torch.ops._xpu_C.int8_gemm_w8a8(
        x_q, x_s, w_qkvz, s_qkvz, torch.bfloat16, None
    )
    y_ba = torch.ops._xpu_C.int8_gemm_w8a8(
        x_q, x_s, w_ba, s_ba, torch.bfloat16, None
    )
    return y_qkvz, y_ba, x_q, x_s


def cloned_pair(
    x: torch.Tensor,
    w_qkvz: torch.Tensor,
    s_qkvz: torch.Tensor,
    w_ba: torch.Tensor,
    s_ba: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    x_q, x_s = torch.ops._xpu_C.per_token_quant_int8_xpu(x)
    y_qkvz = torch.ops._xpu_C.int8_gemm_w8a8(
        x_q.clone(), x_s.clone(), w_qkvz, s_qkvz, torch.bfloat16, None
    )
    y_ba = torch.ops._xpu_C.int8_gemm_w8a8(
        x_q.clone(), x_s.clone(), w_ba, s_ba, torch.bfloat16, None
    )
    return y_qkvz, y_ba, x_q, x_s


def run_once(
    fn,
    x: torch.Tensor,
    w_qkvz: torch.Tensor,
    s_qkvz: torch.Tensor,
    w_ba: torch.Tensor,
    s_ba: torch.Tensor,
) -> dict[str, Any]:
    y_qkvz, y_ba, x_q, x_s = fn(x, w_qkvz, s_qkvz, w_ba, s_ba)
    sync()
    q_before = x_q.clone()
    s_before = x_s.clone()
    sync()
    y_qkvz_2 = torch.ops._xpu_C.int8_gemm_w8a8(
        x_q, x_s, w_qkvz, s_qkvz, torch.bfloat16, None
    )
    y_ba_2 = torch.ops._xpu_C.int8_gemm_w8a8(
        x_q, x_s, w_ba, s_ba, torch.bfloat16, None
    )
    sync()
    q_after = x_q.clone()
    s_after = x_s.clone()
    sync()
    return {
        "q_mutation": tensor_stats_delta(q_before, q_after),
        "scale_mutation": tensor_stats_delta(s_before, s_after),
        "qkvz_repeat_delta": tensor_stats_delta(y_qkvz, y_qkvz_2),
        "ba_repeat_delta": tensor_stats_delta(y_ba, y_ba_2),
    }


def bench(fn, args: tuple[Any, ...], iters: int) -> dict[str, float]:
    for _ in range(5):
        fn(*args)
    sync()
    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn(*args)
        sync()
        times.append((time.perf_counter() - t0) * 1_000_000)
    return {
        "mean_us": statistics.mean(times),
        "median_us": statistics.median(times),
        "min_us": min(times),
        "max_us": max(times),
    }


def compare_outputs(
    a: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
    b: tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor],
) -> dict[str, Any]:
    return {
        "qkvz": tensor_stats_delta(a[0], b[0]),
        "ba": tensor_stats_delta(a[1], b[1]),
        "quant": tensor_stats_delta(a[2], b[2]),
        "scale": tensor_stats_delta(a[3], b[3]),
    }


def maybe_compile(fn):
    try:
        return torch.compile(fn, fullgraph=True, dynamic=False)
    except Exception as exc:
        return exc


def try_run_compiled(fn, fn_args: tuple[Any, ...]):
    try:
        out = fn(*fn_args)
        sync()
        return out, None
    except Exception as exc:
        return None, repr(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--iters", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--m-values", default="1,2,8,18,64")
    parser.add_argument("--k", type=int, default=2048)
    parser.add_argument("--n-qkvz", type=int, default=3072)
    parser.add_argument("--n-ba", type=int, default=16)
    parser.add_argument("--device", default="xpu:0")
    args = parser.parse_args()

    device = torch.device(args.device)
    results: dict[str, Any] = {
        "torch": torch.__version__,
        "device": args.device,
        "xpu_available": torch.xpu.is_available(),
        "xpu_device_count": torch.xpu.device_count(),
        "env": {
            key: os.environ.get(key)
            for key in [
                "LD_LIBRARY_PATH",
                "PYTHONPATH",
                "ONEAPI_DEVICE_SELECTOR",
                "ZE_AFFINITY_MASK",
            ]
        },
        "cases": [],
    }

    compiled_shared = maybe_compile(shared_pair)
    compiled_cloned = maybe_compile(cloned_pair)
    compile_available = not isinstance(compiled_shared, Exception) and not isinstance(
        compiled_cloned, Exception
    )
    results["compile"] = {
        "available": compile_available,
        "shared_error": None
        if not isinstance(compiled_shared, Exception)
        else repr(compiled_shared),
        "cloned_error": None
        if not isinstance(compiled_cloned, Exception)
        else repr(compiled_cloned),
    }

    for m_text in args.m_values.split(","):
        m = int(m_text.strip())
        x, w_qkvz, s_qkvz, w_ba, s_ba = make_inputs(
            m=m,
            k=args.k,
            n_qkvz=args.n_qkvz,
            n_ba=args.n_ba,
            seed=20260610 + m,
            device=device,
        )
        fn_args = (x, w_qkvz, s_qkvz, w_ba, s_ba)

        shared_out = shared_pair(*fn_args)
        cloned_out = cloned_pair(*fn_args)
        sync()
        case: dict[str, Any] = {
            "m": m,
            "k": args.k,
            "n_qkvz": args.n_qkvz,
            "n_ba": args.n_ba,
            "eager_shared_vs_cloned": compare_outputs(shared_out, cloned_out),
            "eager_shared_probe": run_once(shared_pair, *fn_args),
            "eager_cloned_probe": run_once(cloned_pair, *fn_args),
            "eager_shared_bench": bench(shared_pair, fn_args, args.iters),
            "eager_cloned_bench": bench(cloned_pair, fn_args, args.iters),
        }

        if compile_available:
            comp_shared_out, comp_shared_error = try_run_compiled(
                compiled_shared, fn_args
            )
            comp_cloned_out, comp_cloned_error = try_run_compiled(
                compiled_cloned, fn_args
            )
            case["compiled_errors"] = {
                "shared": comp_shared_error,
                "cloned": comp_cloned_error,
            }
            if comp_shared_out is None or comp_cloned_out is None:
                results["compile"]["available"] = False
                results["compile"]["runtime_error"] = {
                    "m": m,
                    "shared": comp_shared_error,
                    "cloned": comp_cloned_error,
                }
                results["cases"].append(case)
                continue
            case["compiled_shared_vs_cloned"] = compare_outputs(
                comp_shared_out, comp_cloned_out
            )
            case["compiled_shared_vs_eager_shared"] = compare_outputs(
                comp_shared_out, shared_out
            )
            case["compiled_cloned_vs_eager_cloned"] = compare_outputs(
                comp_cloned_out, cloned_out
            )
            case["compiled_shared_probe"] = run_once(compiled_shared, *fn_args)
            case["compiled_cloned_probe"] = run_once(compiled_cloned, *fn_args)
            case["compiled_shared_bench"] = bench(compiled_shared, fn_args, args.iters)
            case["compiled_cloned_bench"] = bench(compiled_cloned, fn_args, args.iters)

        results["cases"].append(case)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
