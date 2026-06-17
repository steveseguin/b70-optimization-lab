#!/usr/bin/env python3
"""Check Qwen3.6 GDN prefill state stability across cache rows.

The full-server corruption trace showed identical prompt inputs reaching
different cache rows with matching conv state but different SSM state. This
standalone harness checks the required invariant directly:

  identical prefill, has_initial_state=False, different cache row
  -> identical final conv/SSM state and identical output.

It does not prove cudagraph replay correctness, but it separates raw native GDN
prefill/cache-row behavior from vLLM scheduler and graph-runtime side effects.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")
DEFAULT_DATA_DIR = Path("/home/steve/llm-optimizations/data")


@dataclass
class CaseResult:
    iteration: int
    seed: int
    num_actual_tokens: int
    cache_rows_tested: int
    core_max_abs_diff: float
    z_max_abs_diff: float
    conv_state_max_abs_diff: float
    ssm_state_max_abs_diff: float
    core_bad_count: int
    z_bad_count: int
    conv_state_bad_count: int
    ssm_state_bad_count: int
    passed: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", choices=("bf16", "fp16"), default="bf16")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--iterations", type=int, default=16)
    parser.add_argument("--tokens", type=int, default=36)
    parser.add_argument("--cache-rows", type=int, default=16)
    parser.add_argument("--test-rows", type=int, default=8)
    parser.add_argument("--num-k-heads", type=int, default=16)
    parser.add_argument("--head-k-dim", type=int, default=128)
    parser.add_argument("--num-v-heads", type=int, default=32)
    parser.add_argument("--head-v-dim", type=int, default=128)
    parser.add_argument("--tp-size", type=int, default=4)
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--with-bias", action="store_true")
    parser.add_argument("--reorder-input", action="store_true", default=True)
    parser.add_argument("--state-init", choices=("zero", "random"), default="random")
    parser.add_argument("--atol", type=float, default=0.0)
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--kernel-repo", type=Path, default=DEFAULT_KERNEL_REPO)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    return parser.parse_args()


def add_kernel_repo_to_path(kernel_repo: Path) -> None:
    repo = str(kernel_repo)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def max_abs(torch: Any, left: Any, right: Any) -> float:
    if left.numel() == 0:
        return 0.0
    return float((left.float() - right.float()).abs().max().cpu().item())


def bad_count(torch: Any, left: Any, right: Any, *, atol: float,
              rtol: float) -> int:
    if left.numel() == 0:
        return 0
    close = torch.isclose(left.float(), right.float(), atol=atol, rtol=rtol)
    return int((~close).sum().cpu().item())


def dtype_from_name(torch: Any, name: str) -> Any:
    return torch.bfloat16 if name == "bf16" else torch.float16


def build_inputs(torch: Any, args: argparse.Namespace, *, seed: int) -> dict[str, Any]:
    torch.manual_seed(seed)
    device = args.device
    dtype = dtype_from_name(torch, args.dtype)
    local_k_heads = args.num_k_heads // args.tp_size
    local_v_heads = args.num_v_heads // args.tp_size
    kv_ratio = args.num_v_heads // args.num_k_heads
    qkvz_cols = local_k_heads * (
        2 * args.head_k_dim + 2 * kv_ratio * args.head_v_dim)
    ba_cols = 2 * local_v_heads
    qkv_cols = local_k_heads * (
        2 * args.head_k_dim + kv_ratio * args.head_v_dim)

    projected_states_qkvz = (
        torch.randn((args.tokens, qkvz_cols), dtype=dtype, device=device) * 0.25
    )
    projected_states_ba = (
        torch.randn((args.tokens, ba_cols), dtype=dtype, device=device) * 0.25
    )
    conv_weights = (
        torch.randn((qkv_cols, args.width), dtype=dtype, device=device) * 0.05
    )
    conv_bias = None
    if args.with_bias:
        conv_bias = torch.randn((qkv_cols,), dtype=dtype, device=device) * 0.01
    a_log = torch.randn((local_v_heads,), dtype=torch.float32, device=device) * 0.01
    dt_bias = torch.randn((local_v_heads,), dtype=dtype, device=device) * 0.01

    return {
        "projected_states_qkvz": projected_states_qkvz,
        "projected_states_ba": projected_states_ba,
        "conv_weights": conv_weights,
        "conv_bias": conv_bias,
        "A_log": a_log,
        "dt_bias": dt_bias,
        "qkv_cols": qkv_cols,
        "local_v_heads": local_v_heads,
        "dtype": dtype,
    }


def run_one_case(torch: Any, args: argparse.Namespace, *, iteration: int,
                 seed: int) -> CaseResult:
    inputs = build_inputs(torch, args, seed=seed)
    device = args.device
    dtype = inputs["dtype"]
    test_rows = min(args.test_rows, args.cache_rows)
    state_indices = list(range(test_rows))

    if args.state_init == "zero":
        conv_state = torch.zeros(
            (args.cache_rows, args.width - 1, inputs["qkv_cols"]),
            dtype=dtype,
            device=device,
        )
        ssm_state = torch.zeros(
            (
                args.cache_rows,
                inputs["local_v_heads"],
                args.head_v_dim,
                args.head_k_dim,
            ),
            dtype=dtype,
            device=device,
        )
    else:
        conv_state = torch.randn(
            (args.cache_rows, args.width - 1, inputs["qkv_cols"]),
            dtype=dtype,
            device=device,
        ) * 0.01
        ssm_state = torch.randn(
            (
                args.cache_rows,
                inputs["local_v_heads"],
                args.head_v_dim,
                args.head_k_dim,
            ),
            dtype=dtype,
            device=device,
        ) * 0.01

    has_initial_state = torch.zeros((1,), dtype=torch.bool, device=device)
    query_start_loc = torch.tensor([0, args.tokens], dtype=torch.int32,
                                   device=device)

    core_outputs = []
    z_outputs = []
    for row in state_indices:
        core_attn_out = torch.empty(
            (args.tokens, inputs["local_v_heads"], args.head_v_dim),
            dtype=dtype,
            device=device,
        )
        z = torch.empty_like(core_attn_out)
        state_index = torch.tensor([row], dtype=torch.int32, device=device)
        torch.ops._xpu_C.gdn_attention(
            core_attn_out,
            z,
            inputs["projected_states_qkvz"].clone(),
            inputs["projected_states_ba"].clone(),
            args.num_k_heads,
            args.num_v_heads,
            args.head_k_dim,
            args.head_v_dim,
            conv_state=conv_state,
            ssm_state=ssm_state,
            conv_weights=inputs["conv_weights"],
            conv_bias=inputs["conv_bias"],
            activation="silu",
            A_log=inputs["A_log"],
            dt_bias=inputs["dt_bias"],
            num_prefills=1,
            num_decodes=0,
            has_initial_state=has_initial_state,
            non_spec_query_start_loc=query_start_loc,
            non_spec_state_indices_tensor=state_index,
            num_actual_tokens=args.tokens,
            tp_size=args.tp_size,
            reorder_input=args.reorder_input,
        )
        core_outputs.append(core_attn_out.detach().clone())
        z_outputs.append(z.detach().clone())
    torch.xpu.synchronize()

    ref_core = core_outputs[0]
    ref_z = z_outputs[0]
    ref_conv = conv_state[state_indices[0]].detach().clone()
    ref_ssm = ssm_state[state_indices[0]].detach().clone()

    max_core = 0.0
    max_z = 0.0
    max_conv = 0.0
    max_ssm = 0.0
    bad_core = 0
    bad_z = 0
    bad_conv = 0
    bad_ssm = 0

    for idx, row in enumerate(state_indices[1:], start=1):
        max_core = max(max_core, max_abs(torch, core_outputs[idx], ref_core))
        max_z = max(max_z, max_abs(torch, z_outputs[idx], ref_z))
        max_conv = max(max_conv, max_abs(torch, conv_state[row], ref_conv))
        max_ssm = max(max_ssm, max_abs(torch, ssm_state[row], ref_ssm))
        bad_core += bad_count(torch, core_outputs[idx], ref_core,
                              atol=args.atol, rtol=args.rtol)
        bad_z += bad_count(torch, z_outputs[idx], ref_z, atol=args.atol,
                           rtol=args.rtol)
        bad_conv += bad_count(torch, conv_state[row], ref_conv,
                              atol=args.atol, rtol=args.rtol)
        bad_ssm += bad_count(torch, ssm_state[row], ref_ssm,
                             atol=args.atol, rtol=args.rtol)

    return CaseResult(
        iteration=iteration,
        seed=seed,
        num_actual_tokens=args.tokens,
        cache_rows_tested=test_rows,
        core_max_abs_diff=max_core,
        z_max_abs_diff=max_z,
        conv_state_max_abs_diff=max_conv,
        ssm_state_max_abs_diff=max_ssm,
        core_bad_count=bad_core,
        z_bad_count=bad_z,
        conv_state_bad_count=bad_conv,
        ssm_state_bad_count=bad_ssm,
        passed=(bad_core == 0 and bad_z == 0 and bad_conv == 0 and bad_ssm == 0),
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Qwen3.6 GDN Prefill State Stability",
        "",
        f"- Created: `{payload['created_at']}`",
        f"- Pass all: `{summary['pass_all']}`",
        f"- Iterations: `{summary['iterations']}`",
        f"- Failed iterations: `{summary['failed_iterations']}`",
        f"- Max core diff: `{summary['max_core_abs_diff']}`",
        f"- Max z diff: `{summary['max_z_abs_diff']}`",
        f"- Max conv-state diff: `{summary['max_conv_state_abs_diff']}`",
        f"- Max SSM-state diff: `{summary['max_ssm_state_abs_diff']}`",
        "",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    add_kernel_repo_to_path(args.kernel_repo)

    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    results = [
        run_one_case(torch, args, iteration=i, seed=args.seed + i)
        for i in range(args.iterations)
    ]
    failed = [result for result in results if not result.passed]
    summary = {
        "pass_all": not failed,
        "iterations": len(results),
        "failed_iterations": len(failed),
        "max_core_abs_diff": max(r.core_max_abs_diff for r in results),
        "max_z_abs_diff": max(r.z_max_abs_diff for r in results),
        "max_conv_state_abs_diff": max(r.conv_state_max_abs_diff for r in results),
        "max_ssm_state_abs_diff": max(r.ssm_state_max_abs_diff for r in results),
        "total_core_bad_count": sum(r.core_bad_count for r in results),
        "total_z_bad_count": sum(r.z_bad_count for r in results),
        "total_conv_state_bad_count": sum(r.conv_state_bad_count for r in results),
        "total_ssm_state_bad_count": sum(r.ssm_state_bad_count for r in results),
    }
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "args": vars(args) | {
            "kernel_repo": str(args.kernel_repo),
            "data_dir": str(args.data_dir),
            "json_out": str(args.json_out) if args.json_out else None,
            "md_out": str(args.md_out) if args.md_out else None,
        },
        "summary": summary,
        "results": [asdict(result) for result in results],
    }

    args.data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_out = args.json_out or args.data_dir / (
        f"qwen36-gdn-prefill-state-stability-{stamp}.json")
    md_out = args.md_out or json_out.with_suffix(".md")
    json_out.write_text(json.dumps(payload, indent=2) + "\n")
    write_markdown(md_out, payload)
    print(json.dumps({
        "json": str(json_out),
        "md": str(md_out),
        "summary": summary,
    }, sort_keys=True))
    return 0 if summary["pass_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
