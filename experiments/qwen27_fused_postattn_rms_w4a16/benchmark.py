#!/usr/bin/env python3
import argparse
import json
import os
import socket
import statistics
import time
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parent
M, K, N, GROUP = 4, 5120, 17408, 128


def assert_reserved_ports_idle() -> None:
    active = []
    for port in (19448, 19449):
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                active.append(port)
    if active:
        raise SystemExit(f"refusing XPU execution: active server port(s) {active}")


def load_extension() -> None:
    candidates = sorted(ROOT.glob("qwen27_fused_postattn_rms_w4a16_ext*.so"))
    if not candidates:
        raise SystemExit(f"extension is not built; run: {os.sys.executable} {ROOT / 'build.py'}")
    torch.ops.load_library(str(candidates[-1]))


def register_fake() -> None:
    @torch.library.register_fake("qwen27_postattn_w4a16::run_out")
    def _fake(hidden, residual, gamma, qweight, scales, residual_out, normed_out, output, eps):
        return None


def load_existing_w4a16(path: Path | None) -> str:
    if hasattr(torch.ops, "_xpu_C") and hasattr(torch.ops._xpu_C, "int4_gemm_w4a16"):
        return "already registered"
    if path is None:
        return "not requested"
    if not path.is_file():
        return f"not found: {path}"
    try:
        torch.ops.load_library(str(path))
    except OSError as error:
        return f"load failed: {error}"
    if not hasattr(torch.ops._xpu_C, "int4_gemm_w4a16"):
        return f"loaded without int4_gemm_w4a16: {path}"
    return f"loaded: {path}"


def load_existing_rms(path: Path | None) -> str:
    if hasattr(torch.ops, "_C") and hasattr(torch.ops._C, "fused_add_rms_norm"):
        return "already registered"
    if path is None:
        return "not requested"
    if not path.is_file():
        return f"not found: {path}"
    try:
        torch.ops.load_library(str(path))
    except OSError as error:
        return f"load failed: {error}"
    if not hasattr(torch.ops._C, "fused_add_rms_norm"):
        return f"loaded without fused_add_rms_norm: {path}"
    return f"loaded: {path}"


def make_autoround_tensors(device: str, seed: int):
    generator = torch.Generator(device=device).manual_seed(seed)
    hidden = torch.randn((M, K), device=device, dtype=torch.float16, generator=generator) * 0.2
    residual = torch.randn((M, K), device=device, dtype=torch.float16, generator=generator) * 0.2
    gamma = 0.8 + torch.rand((K,), device=device, dtype=torch.float16, generator=generator) * 0.4

    # Checkpoint qweight is contiguous [K/8,N]. The production INC loader makes
    # qweight.t().contiguous().t(), yielding the same logical shape with NT strides.
    checkpoint_qweight = torch.randint(
        -(2**31), 2**31 - 1, (K // 8, N), device=device,
        dtype=torch.int32, generator=generator,
    )
    qweight = checkpoint_qweight.t().contiguous().t()
    scales = torch.rand((K // GROUP, N), device=device, dtype=torch.float16, generator=generator) * 0.025 + 0.001
    zero_point = torch.tensor([8], device=device, dtype=torch.int8)
    return hidden, residual, gamma, qweight, scales, zero_point


def fused_call(hidden, residual, gamma, qweight, scales, residual_out, normed_out, output, eps):
    torch.ops.qwen27_postattn_w4a16.run_out(
        hidden, residual, gamma, qweight, scales,
        residual_out, normed_out, output, eps,
    )
    return output, residual_out, normed_out


def rms_reference(hidden, residual, gamma, eps):
    residual_ref = (hidden.float() + residual.float()).half()
    inv_rms = torch.rsqrt(residual_ref.float().square().mean(dim=-1, keepdim=True) + eps)
    normed_ref = (residual_ref.float() * inv_rms * gamma.float()).half()
    return residual_ref, normed_ref


def unpack_weight_slice(qweight, scales, n0, n1):
    # Work on CPU and a small N slice to avoid materializing the 178M-element
    # dequantized gate_up matrix. Bytes preserve GPTQ's low-to-high nibble order.
    packed = qweight[:, n0:n1].cpu().contiguous()
    values = packed.view(torch.uint8).reshape(K // 8, n1 - n0, 4)
    low = values.bitwise_and(0xF)
    high = values.bitwise_right_shift(4).bitwise_and(0xF)
    quant = (
        torch.stack((low, high), dim=-1)
        .permute(0, 2, 3, 1)
        .reshape(K, n1 - n0)
        .float()
        - 8.0
    )
    scale = scales[:, n0:n1].cpu().float().repeat_interleave(GROUP, dim=0)
    return quant * scale


def correctness(args, tensors, outputs):
    hidden, residual, gamma, qweight, scales, zero_point = tensors
    output, residual_out, normed_out = outputs
    residual_ref, normed_ref = rms_reference(hidden, residual, gamma, args.eps)
    torch.xpu.synchronize()
    residual_error = (residual_out.float() - residual_ref.float()).abs()
    normed_error = (normed_out.float() - normed_ref.float()).abs()
    torch.testing.assert_close(residual_out, residual_ref, atol=2e-3, rtol=2e-3)
    torch.testing.assert_close(normed_out, normed_ref, atol=3e-3, rtol=3e-3)

    ncheck = min(args.check_columns, N)
    weight_ref = unpack_weight_slice(qweight, scales, 0, ncheck)
    projection_ref = normed_ref.cpu().float() @ weight_ref
    torch.testing.assert_close(
        output[:, :ncheck].cpu().float(), projection_ref,
        atol=args.atol, rtol=args.rtol,
    )

    if hasattr(torch.ops, "_xpu_C") and hasattr(torch.ops._xpu_C, "int4_gemm_w4a16"):
        onednn = torch.ops._xpu_C.int4_gemm_w4a16(
            normed_ref, qweight, None, scales, zero_point, GROUP, None,
        )
        torch.testing.assert_close(output.float(), onednn.float(), atol=args.atol, rtol=args.rtol)
        output_error = (output.float() - onednn.float()).abs()
        return {
            "mode": "full existing oneDNN W4A16 parity",
            "residual_max_abs": residual_error.max().item(),
            "residual_mean_abs": residual_error.mean().item(),
            "normed_max_abs": normed_error.max().item(),
            "normed_mean_abs": normed_error.mean().item(),
            "output_max_abs": output_error.max().item(),
            "output_mean_abs": output_error.mean().item(),
            "output_rmse": output_error.square().mean().sqrt().item(),
        }
    return {
        "mode": f"faithful dequantized reference on first {ncheck} columns; _xpu_C unavailable",
        "residual_max_abs": residual_error.max().item(),
        "residual_mean_abs": residual_error.mean().item(),
        "normed_max_abs": normed_error.max().item(),
        "normed_mean_abs": normed_error.mean().item(),
    }


def benchmark(fn, warmup, iterations):
    for _ in range(warmup):
        fn()
    torch.xpu.synchronize()
    samples = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        torch.xpu.synchronize()
        samples.append((time.perf_counter_ns() - start) / 1e6)
    return {"median_ms": statistics.median(samples), "min_ms": min(samples), "samples_ms": samples}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--eps", type=float, default=1e-6)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--check-columns", type=int, default=64)
    parser.add_argument("--atol", type=float, default=0.8)
    parser.add_argument("--rtol", type=float, default=0.03)
    parser.add_argument("--compile-check", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--graph-check", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--graph-replays", type=int, default=1000)
    parser.add_argument("--json", type=Path)
    parser.add_argument(
        "--xpu-kernels-library",
        type=Path,
        default=Path("/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so"),
        help="existing vLLM XPU ops library used for the oneDNN baseline",
    )
    parser.add_argument(
        "--xpu-core-library",
        type=Path,
        default=Path("/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_C.abi3.so"),
        help="existing vLLM XPU core library used for native fused-add RMSNorm",
    )
    args = parser.parse_args()

    assert_reserved_ports_idle()
    load_extension()
    register_fake()
    existing_library = load_existing_w4a16(args.xpu_kernels_library)
    existing_rms_library = load_existing_rms(args.xpu_core_library)
    tensors = make_autoround_tensors(args.device, args.seed)
    hidden, residual, gamma, qweight, scales, zero_point = tensors
    residual_out = torch.empty_like(hidden)
    normed_out = torch.empty_like(hidden)
    output = torch.empty((M, N), device=args.device, dtype=torch.float16)
    call = lambda: fused_call(
        hidden, residual, gamma, qweight, scales,
        residual_out, normed_out, output, args.eps,
    )
    call()
    correctness_mode = correctness(args, tensors, (output, residual_out, normed_out))

    report = {
        "shape": {"m": M, "k": K, "n": N, "group_size": GROUP},
        "correctness": correctness_mode,
        "fused": benchmark(call, args.warmup, args.iterations),
        "torch_compile_fullgraph": "not requested",
        "xpu_graph_replay": "not requested",
        "existing_xpu_library": existing_library,
        "existing_rms_library": existing_rms_library,
        "baseline": "unavailable: installed _xpu_C.int4_gemm_w4a16 was not found",
        "native_baseline": "unavailable: native fused-add RMSNorm or W4A16 was not found",
        "projection_only": "unavailable: installed _xpu_C.int4_gemm_w4a16 was not found",
    }

    if hasattr(torch.ops, "_xpu_C") and hasattr(torch.ops._xpu_C, "int4_gemm_w4a16"):
        def baseline():
            residual_ref, normed_ref = rms_reference(hidden, residual, gamma, args.eps)
            return torch.ops._xpu_C.int4_gemm_w4a16(
                normed_ref, qweight, None, scales, zero_point, GROUP, None,
            ), residual_ref

        report["baseline"] = benchmark(baseline, args.warmup, args.iterations)

        def projection_only():
            return torch.ops._xpu_C.int4_gemm_w4a16(
                normed_out, qweight, None, scales, zero_point, GROUP, None,
            )

        report["projection_only"] = benchmark(
            projection_only, args.warmup, args.iterations
        )

        if hasattr(torch.ops, "_C") and hasattr(torch.ops._C, "fused_add_rms_norm"):
            native_input = hidden.clone()
            native_residual = residual.clone()

            def native_baseline():
                torch.ops._C.fused_add_rms_norm(
                    native_input, native_residual, gamma, args.eps
                )
                return torch.ops._xpu_C.int4_gemm_w4a16(
                    native_input, qweight, None, scales, zero_point, GROUP, None,
                )

            report["native_baseline"] = benchmark(
                native_baseline, args.warmup, args.iterations
            )

    if args.compile_check:
        compiled = torch.compile(fused_call, fullgraph=True)
        compiled(hidden, residual, gamma, qweight, scales, residual_out, normed_out, output, args.eps)
        torch.xpu.synchronize()
        report["torch_compile_fullgraph"] = "passed"

    if args.graph_check:
        if not hasattr(torch.xpu, "XPUGraph") or not hasattr(torch.xpu, "graph"):
            report["xpu_graph_replay"] = "unsupported by this torch build"
        else:
            graph = torch.xpu.XPUGraph()
            with torch.xpu.graph(graph):
                call()
            for _ in range(args.graph_replays):
                graph.replay()
            torch.xpu.synchronize()
            correctness(args, tensors, (output, residual_out, normed_out))
            report["xpu_graph_replay"] = (
                f"passed (capture plus {args.graph_replays} replays)"
            )

    text = json.dumps(report, indent=2)
    print(text)
    if args.json:
        args.json.write_text(text + "\n")


if __name__ == "__main__":
    main()
