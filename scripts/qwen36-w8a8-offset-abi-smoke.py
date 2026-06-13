#!/usr/bin/env python3
"""Smoke-test Qwen3.6 W8A8 grouped-GEMM extension candidates.

Each candidate/op runs in a separate child process so a bad kernel can segfault
without killing the whole report. This is an ABI and tiny execution smoke, not
a quality or endpoint benchmark.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES = [
    "/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so",
    "/home/steve/src/vllm-xpu-kernels/build/lib.linux-x86_64-cpython-312/"
    "vllm_xpu_kernels/_xpu_C.abi3.so",
    "/home/steve/src/vllm-xpu-kernels/build/temp-before-onednn-grouped-"
    "20260612064136/_xpu_C.abi3.so",
    "/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-probe-20260612/"
    "_xpu_C.abi3.so",
]
DEFAULT_PYTHON = "/home/steve/.venvs/vllm-xpu/bin/python"
DEFAULT_ONEAPI_LIB = "/opt/intel/oneapi/compiler/2026.0/lib"
DEFAULT_VENV_LIB = "/home/steve/.venvs/vllm-xpu/lib"
DEFAULT_TORCH_LIB = (
    "/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib"
)
OPS = [
    "base",
    "offsets",
    "active_offsets",
    "quant_out",
    "silu_quant_out",
]


def candidate_label(path: str) -> str:
    parts = Path(path).parts
    if "build" in parts:
        idx = parts.index("build")
        if idx + 1 < len(parts):
            return "build/" + parts[idx + 1]
    if "vllm_xpu_kernels" in parts:
        return "installed"
    return Path(path).parent.name


def child_main(args: argparse.Namespace) -> int:
    import importlib.util
    import torch

    candidate = args.candidate
    spec = importlib.util.spec_from_file_location(
        "vllm_xpu_kernels._xpu_C", candidate)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load spec for {candidate}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["vllm_xpu_kernels._xpu_C"] = mod
    spec.loader.exec_module(mod)

    op_to_symbol = {
        "base": "cutlass_grouped_gemm_w8a8_int8_interface",
        "offsets": "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
        "active_offsets": (
            "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface"),
        "quant_out": "per_token_quant_int8_xpu_out",
        "silu_quant_out": "silu_and_mul_quant_int8_xpu_out",
    }
    symbol = op_to_symbol[args.op]
    has_symbol = hasattr(torch.ops._xpu_C, symbol)
    if not has_symbol:
        print(json.dumps({
            "candidate": candidate,
            "op": args.op,
            "symbol": symbol,
            "status": "missing_symbol",
        }, sort_keys=True))
        return 0

    if not args.execute:
        print(json.dumps({
            "candidate": candidate,
            "op": args.op,
            "symbol": symbol,
            "status": "registered",
        }, sort_keys=True))
        return 0

    if not torch.xpu.is_available():
        raise RuntimeError("torch.xpu is not available")

    torch.manual_seed(args.seed)
    device = f"xpu:{args.device}"
    experts = args.experts
    rows_cpu = torch.tensor(args.rows, dtype=torch.int32)
    if rows_cpu.numel() != experts:
        raise ValueError("--rows length must equal --experts")
    offsets_cpu = torch.empty((experts + 1, ), dtype=torch.int64)
    offsets_cpu[0] = 0
    offsets_cpu[1:] = torch.cumsum(rows_cpu.to(torch.int64), dim=0)
    active_cpu = torch.nonzero(rows_cpu, as_tuple=False).flatten().to(
        torch.int32)
    total_m = int(rows_cpu.sum().item())

    ops = torch.ops._xpu_C
    if args.op in ("quant_out", "silu_quant_out"):
        if args.op == "quant_out":
            x = torch.randn((total_m, args.n),
                            dtype=torch.bfloat16,
                            device=device)
        else:
            x = torch.randn((total_m, args.n * 2),
                            dtype=torch.bfloat16,
                            device=device)
        q = torch.empty((total_m, args.n), dtype=torch.int8, device=device)
        scales = torch.empty((total_m, 1), dtype=torch.float32, device=device)
        if args.op == "quant_out":
            ops.per_token_quant_int8_xpu_out(x, q, scales)
        else:
            ops.silu_and_mul_quant_int8_xpu_out(x, q, scales)
        torch.xpu.synchronize()
        out = q.cpu().float()
        scale_cpu = scales.cpu().float()
        print(json.dumps({
            "candidate": candidate,
            "device": str(torch.xpu.get_device_name(args.device)),
            "op": args.op,
            "symbol": symbol,
            "status": "executed",
            "shape": {
                "rows": total_m,
                "in_features": int(x.shape[-1]),
                "out_features": args.n,
            },
            "checksum": float(out.sum().item()),
            "mean_abs": float(out.abs().mean().item()),
            "max_abs": float(out.abs().max().item()),
            "scale_sum": float(scale_cpu.sum().item()),
        }, sort_keys=True))
        return 0

    a = torch.randint(-8,
                      8, (total_m, args.k),
                      dtype=torch.int8,
                      device=device)
    a_scale = (torch.rand((total_m, 1), dtype=torch.float32, device=device) *
               0.03 + 0.01)
    b = torch.randint(-8,
                      8, (experts, args.k, args.n),
                      dtype=torch.int8,
                      device=device)
    b_scale = (torch.rand((experts, args.n),
                          dtype=torch.float32,
                          device=device) * 0.03 + 0.01)
    d = torch.empty((total_m, args.n), dtype=torch.bfloat16, device=device)

    rows = rows_cpu.to(device)
    offsets = offsets_cpu.to(device)
    active = active_cpu.to(device)
    if args.op == "base":
        ops.cutlass_grouped_gemm_w8a8_int8_interface(
            a, a_scale, b, b_scale, None, d, rows, args.n, args.k, experts)
    elif args.op == "offsets":
        ops.cutlass_grouped_gemm_w8a8_int8_offsets_interface(
            a, a_scale, b, b_scale, None, d, offsets, args.n, args.k,
            experts)
    elif args.op == "active_offsets":
        ops.cutlass_grouped_gemm_w8a8_int8_active_offsets_interface(
            a, a_scale, b, b_scale, None, d, offsets, active, args.n, args.k,
            experts, int(active_cpu.numel()))
    else:
        raise ValueError(args.op)

    torch.xpu.synchronize()
    out = d.cpu().float()
    print(json.dumps({
        "candidate": candidate,
        "device": str(torch.xpu.get_device_name(args.device)),
        "op": args.op,
        "symbol": symbol,
        "status": "executed",
        "shape": {
            "experts": experts,
            "rows": rows_cpu.tolist(),
            "total_m": total_m,
            "k": args.k,
            "n": args.n,
        },
        "checksum": float(out.sum().item()),
        "mean_abs": float(out.abs().mean().item()),
        "max_abs": float(out.abs().max().item()),
    }, sort_keys=True))
    return 0


def run_child(args: argparse.Namespace, candidate: str, op: str) -> dict[str, Any]:
    env = os.environ.copy()
    lib_dirs = [
        str(Path(candidate).parent),
        args.oneapi_lib,
        args.venv_lib,
        args.torch_lib,
    ]
    existing = env.get("LD_LIBRARY_PATH")
    if existing:
        lib_dirs.append(existing)
    env["LD_LIBRARY_PATH"] = ":".join(lib_dirs)

    cmd = [
        args.python,
        __file__,
        "--child",
        "--candidate",
        candidate,
        "--op",
        op,
        "--experts",
        str(args.experts),
        "--rows",
        ",".join(str(v) for v in args.rows),
        "--k",
        str(args.k),
        "--n",
        str(args.n),
        "--seed",
        str(args.seed),
        "--device",
        str(args.device),
    ]
    if args.execute:
        cmd.append("--execute")

    try:
        proc = subprocess.run(cmd,
                              text=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              env=env,
                              timeout=args.timeout,
                              check=False)
    except subprocess.TimeoutExpired as exc:
        return {
            "candidate": candidate,
            "candidate_label": candidate_label(candidate),
            "op": op,
            "returncode": None,
            "status": "timeout",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timeout_seconds": args.timeout,
            "parsed": {
                "candidate": candidate,
                "op": op,
                "status": "timeout",
                "timeout_seconds": args.timeout,
            },
        }
    parsed = None
    for line in reversed(proc.stdout.splitlines()):
        try:
            parsed = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    return {
        "candidate": candidate,
        "candidate_label": candidate_label(candidate),
        "op": op,
        "returncode": proc.returncode,
        "status": (
            "signal" if proc.returncode < 0 else
            ("ok" if proc.returncode == 0 else "failed")),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "parsed": parsed,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Qwen3.6 W8A8 Offset ABI Smoke",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
    ]
    for item in report["results"]:
        parsed = item.get("parsed") or {}
        status = parsed.get("status") or item["status"]
        returncode = item.get("returncode")
        if isinstance(returncode, int) and returncode < 0:
            status = f"signal {-item['returncode']}"
        lines.append(
            f"- `{item['candidate_label']}` `{item['op']}`: {status}")
        if parsed.get("status") == "executed":
            lines.append(
                "  "
                f"checksum `{parsed['checksum']:.6f}`, "
                f"mean_abs `{parsed['mean_abs']:.6f}`, "
                f"max_abs `{parsed['max_abs']:.6f}`")

    lines.extend([
        "",
        "## Decision",
        "",
        report["decision"],
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_rows(raw: str) -> list[int]:
    rows = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not rows:
        raise argparse.ArgumentTypeError("rows must not be empty")
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--candidate", action="append")
    parser.add_argument("--op", choices=OPS)
    parser.add_argument("--python", default=DEFAULT_PYTHON)
    parser.add_argument("--oneapi-lib", default=DEFAULT_ONEAPI_LIB)
    parser.add_argument("--venv-lib", default=DEFAULT_VENV_LIB)
    parser.add_argument("--torch-lib", default=DEFAULT_TORCH_LIB)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--experts", type=int, default=4)
    parser.add_argument("--rows", type=parse_rows, default=parse_rows("2,0,3,1"))
    parser.add_argument("--k", type=int, default=2048)
    parser.add_argument("--n", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.child:
        if not args.candidate or len(args.candidate) != 1:
            raise SystemExit("--child requires exactly one --candidate")
        if not args.op:
            raise SystemExit("--child requires --op")
        args.candidate = args.candidate[0]
        return child_main(args)

    candidates = args.candidate or DEFAULT_CANDIDATES
    results = []
    for candidate in candidates:
        for op in OPS:
            results.append(run_child(args, candidate, op))

    executed_ops_by_candidate: dict[str, set[str]] = {}
    for item in results:
        if item.get("returncode") != 0:
            continue
        if (item.get("parsed") or {}).get("status") != "executed":
            continue
        executed_ops_by_candidate.setdefault(item["candidate"], set()).add(
            item["op"])

    required_full_ops = {
        "base",
        "offsets",
        "active_offsets",
        "quant_out",
        "silu_quant_out",
    }
    full_candidates = [
        candidate for candidate, ops in executed_ops_by_candidate.items()
        if required_full_ops.issubset(ops)
    ]
    stable_offset = [
        item for item in results
        if item["op"] == "offsets" and item["returncode"] == 0 and
        (item.get("parsed") or {}).get("status") == "executed"
    ]
    active_crashes = [
        item for item in results
        if item["op"] == "active_offsets" and
        isinstance(item.get("returncode"), int) and item["returncode"] < 0
    ]
    timeouts = [
        item for item in results
        if item.get("status") == "timeout" or
        (item.get("parsed") or {}).get("status") == "timeout"
    ]
    if full_candidates:
        labels = ", ".join(candidate_label(path) for path in full_candidates)
        decision = (
            "Use the full diagnostic candidate(s) that executed base, offsets, "
            "active-offset, quant-out, and SiLU+quant-out: "
            f"{labels}. Keep endpoint promotion gated on exactness, speed, "
            "and provenance; this smoke proves only ABI and tiny execution."
        )
    elif stable_offset:
        decision = (
            "Use the stable offset-only candidate as the next no-quality-loss "
            "diagnostic lane. Treat active-offset and quant-out as unavailable "
            "until a full candidate is rebuilt or fixed."
        )
    else:
        decision = (
            "No offset candidate executed successfully; stop before endpoint "
            "testing and rebuild the XPU extension.")
    if active_crashes:
        decision += " Active-offset crashed in at least one candidate."
    if timeouts:
        decision += f" {len(timeouts)} candidate/op child run(s) timed out."

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execute": bool(args.execute),
        "python": args.python,
        "shape": {
            "experts": args.experts,
            "rows": args.rows,
            "k": args.k,
            "n": args.n,
        },
        "candidates": candidates,
        "results": results,
        "decision": decision,
    }

    if args.output_json:
        args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True)
                                    + "\n",
                                    encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.markdown_out:
        write_markdown(report, args.markdown_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
