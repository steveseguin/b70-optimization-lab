#!/usr/bin/env python3
"""Native XPU GDN spec-decode prefix-row parity check.

This checks the packed native ``gdn_attention_spec_decode`` state contract
without launching a vLLM server. The native op should publish speculative state
columns that exactly match processing the same rows one token at a time through
normal ``gdn_attention`` decode.

The important convention this script verifies is the current packed native
contract:

  * ``spec_state_indices_tensor[:, j]`` is the state after packed spec row ``j``.
  * ``num_accepted_tokens=N`` selects source column ``N - 1`` for the next
    packed spec step.

There is no independent base column in the native packed table; the running
column is copied from the selected accepted source and then overwritten with
the first published prefix row.

With ``--prefix-base-state``, the experimental contract is:

  * ``spec_state_indices_tensor[:, 0]`` stays the selected base/running state.
  * ``spec_state_indices_tensor[:, j + 1]`` is the state after packed row ``j``.
  * ``num_accepted_tokens=N`` selects source column ``N`` for the next packed
    spec step, because column 0 is the base state and column ``N`` is the state
    after accepting ``N`` tokens.
  * overflow rows (for example the target-owned bonus row when rows == columns)
    produce outputs but do not overwrite the final stored prefix column.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_KERNEL_REPO = Path("/home/steve/src/vllm-xpu-kernels")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"),
                        default="bf16")
    parser.add_argument("--seed", type=int, default=20260705)
    parser.add_argument("--num-reqs", type=int, default=3)
    parser.add_argument("--spec-len", type=int, default=4,
                        help="Packed rows per request, e.g. MTP3 => 4.")
    parser.add_argument("--num-k-heads", type=int, default=1)
    parser.add_argument("--num-v-heads", type=int, default=1)
    parser.add_argument("--head-k-dim", type=int, default=32)
    parser.add_argument("--head-v-dim", type=int, default=32)
    parser.add_argument("--tp-size", type=int, default=1)
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--activation", choices=("silu", "swish"),
                        default="silu")
    parser.add_argument("--with-bias", action="store_true")
    parser.add_argument("--reorder-input", action=argparse.BooleanOptionalAction,
                        default=True)
    parser.add_argument("--prefix-base-state", action="store_true",
                        help="Verify VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE=1.")
    parser.add_argument("--atol", type=float, default=1e-2,
                        help="Tolerance for packed-vs-one-step numeric parity.")
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--kernel-repo", type=Path, default=DEFAULT_KERNEL_REPO)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def add_kernel_repo_to_path(kernel_repo: Path) -> None:
    repo = str(kernel_repo)
    if repo not in sys.path:
        sys.path.insert(0, repo)


def dtype_from_name(torch: Any, name: str) -> Any:
    if name == "bf16":
        return torch.bfloat16
    if name == "fp16":
        return torch.float16
    return torch.float32


def max_abs(torch: Any, left: Any, right: Any) -> float:
    if left.numel() == 0:
        return 0.0
    return float((left.float() - right.float()).abs().max().cpu().item())


def close_enough(torch: Any, left: Any, right: Any, *, atol: float,
                 rtol: float) -> bool:
    if left.numel() == 0:
        return True
    return bool(torch.allclose(left.float(), right.float(), atol=atol,
                               rtol=rtol))


def build_inputs(torch: Any, args: argparse.Namespace, *,
                 tokens: int, seed: int) -> dict[str, Any]:
    torch.manual_seed(seed)
    dtype = dtype_from_name(torch, args.dtype)
    device = args.device
    local_k_heads = args.num_k_heads // args.tp_size
    local_v_heads = args.num_v_heads // args.tp_size
    kv_ratio = args.num_v_heads // args.num_k_heads
    qkvz_cols = local_k_heads * (
        2 * args.head_k_dim + 2 * kv_ratio * args.head_v_dim)
    ba_cols = 2 * local_v_heads
    conv_cols = local_k_heads * (
        2 * args.head_k_dim + kv_ratio * args.head_v_dim)

    return {
        "projected_states_qkvz": (
            torch.randn((tokens, qkvz_cols), dtype=dtype, device=device) * 0.2
        ).contiguous(),
        "projected_states_ba": (
            torch.randn((tokens, ba_cols), dtype=dtype, device=device) * 0.2
        ).contiguous(),
        "conv_weights": (
            torch.randn((conv_cols, args.width), dtype=dtype, device=device)
            * 0.03
        ).contiguous(),
        "conv_bias": (
            torch.randn((conv_cols,), dtype=dtype, device=device) * 0.01
            if args.with_bias else None
        ),
        "A_log": (
            torch.randn((local_v_heads,), dtype=torch.float32, device=device)
            * 0.01
        ).contiguous(),
        "dt_bias": (
            torch.randn((local_v_heads,), dtype=dtype, device=device) * 0.01
        ).contiguous(),
        "dtype": dtype,
        "local_v_heads": local_v_heads,
        "conv_cols": conv_cols,
    }


def run_normal_decode_steps(
    torch: Any,
    args: argparse.Namespace,
    inputs: dict[str, Any],
    *,
    conv_state: Any,
    ssm_state: Any,
    running_rows: Any,
    token_base: int,
) -> tuple[Any, Any, list[Any], list[Any]]:
    num_reqs = args.num_reqs
    spec_len = args.spec_len
    dtype = inputs["dtype"]
    local_v_heads = inputs["local_v_heads"]
    device = args.device

    query_start = torch.arange(num_reqs + 1, dtype=torch.int32, device=device)
    outputs = torch.empty((num_reqs * spec_len, local_v_heads,
                           args.head_v_dim), dtype=dtype, device=device)
    z_outputs = torch.empty_like(outputs)
    conv_prefixes: list[Any] = []
    ssm_prefixes: list[Any] = []

    for pos in range(spec_len):
        token_indices = (
            torch.arange(num_reqs, dtype=torch.long, device=device)
            * spec_len + pos + token_base
        )
        out_step = torch.empty((num_reqs, local_v_heads, args.head_v_dim),
                               dtype=dtype, device=device)
        z_step = torch.empty_like(out_step)
        torch.ops._xpu_C.gdn_attention(
            out_step,
            z_step,
            inputs["projected_states_qkvz"].index_select(
                0, token_indices).contiguous(),
            inputs["projected_states_ba"].index_select(
                0, token_indices).contiguous(),
            args.num_k_heads,
            args.num_v_heads,
            args.head_k_dim,
            args.head_v_dim,
            conv_state=conv_state,
            ssm_state=ssm_state,
            conv_weights=inputs["conv_weights"],
            conv_bias=inputs["conv_bias"],
            activation=args.activation,
            A_log=inputs["A_log"],
            dt_bias=inputs["dt_bias"],
            num_prefills=0,
            num_decodes=num_reqs,
            has_initial_state=None,
            non_spec_query_start_loc=query_start,
            non_spec_state_indices_tensor=running_rows.to(torch.int32),
            num_actual_tokens=num_reqs,
            tp_size=args.tp_size,
            reorder_input=args.reorder_input,
        )
        dst = (
            torch.arange(num_reqs, dtype=torch.long, device=device) * spec_len
            + pos
        )
        outputs.index_copy_(0, dst, out_step)
        z_outputs.index_copy_(0, dst, z_step)
        conv_prefixes.append(conv_state.index_select(0, running_rows).clone())
        ssm_prefixes.append(ssm_state.index_select(0, running_rows).clone())
    return outputs, z_outputs, conv_prefixes, ssm_prefixes


def run_spec_decode(
    torch: Any,
    args: argparse.Namespace,
    inputs: dict[str, Any],
    *,
    conv_state: Any,
    ssm_state: Any,
    state_table: Any,
    num_accepted_tokens: Any | None,
    token_base: int,
) -> tuple[Any, Any]:
    total_tokens = args.num_reqs * args.spec_len
    dtype = inputs["dtype"]
    local_v_heads = inputs["local_v_heads"]
    device = args.device
    query_start = torch.arange(
        0,
        total_tokens + 1,
        args.spec_len,
        dtype=torch.int32,
        device=device,
    )
    spec_token_indices = (
        torch.arange(total_tokens, dtype=torch.int32, device=device)
        + token_base
    )
    out = torch.empty((total_tokens + token_base, local_v_heads,
                       args.head_v_dim), dtype=dtype, device=device)
    z = torch.empty_like(out)
    torch.ops._xpu_C.gdn_attention_spec_decode(
        out,
        z,
        inputs["projected_states_qkvz"],
        inputs["projected_states_ba"],
        args.num_k_heads,
        args.num_v_heads,
        args.head_k_dim,
        args.head_v_dim,
        conv_state=conv_state,
        ssm_state=ssm_state,
        conv_weights=inputs["conv_weights"],
        conv_bias=inputs["conv_bias"],
        activation=args.activation,
        A_log=inputs["A_log"],
        dt_bias=inputs["dt_bias"],
        spec_query_start_loc=query_start,
        spec_state_indices_tensor=state_table.to(torch.int32),
        spec_token_indices=spec_token_indices,
        num_accepted_tokens=num_accepted_tokens,
        num_spec_decodes=args.num_reqs,
        num_actual_tokens=total_tokens + token_base,
        tp_size=args.tp_size,
        reorder_input=args.reorder_input,
    )
    return out[token_base:], z[token_base:]


def compare_case(
    torch: Any,
    args: argparse.Namespace,
    inputs: dict[str, Any],
    *,
    case_name: str,
    initial_conv_table: Any,
    initial_ssm_table: Any,
    state_table: Any,
    accepted_counts: Any | None,
    token_base: int,
) -> dict[str, Any]:
    dtype = inputs["dtype"]
    local_v_heads = inputs["local_v_heads"]
    conv_cols = inputs["conv_cols"]
    device = args.device
    num_reqs = args.num_reqs
    spec_len = args.spec_len

    row_count = int(state_table.max().detach().cpu().item()) + 1
    running_rows = torch.arange(row_count, row_count + num_reqs,
                                dtype=torch.long, device=device)
    total_rows = row_count + num_reqs

    ref_conv = torch.zeros((total_rows, args.width - 1, conv_cols),
                           dtype=dtype, device=device)
    ref_ssm = torch.zeros((total_rows, local_v_heads, args.head_v_dim,
                           args.head_k_dim), dtype=dtype, device=device)
    spec_conv = torch.zeros_like(ref_conv)
    spec_ssm = torch.zeros_like(ref_ssm)
    ref_conv[:row_count].copy_(initial_conv_table[:row_count])
    ref_ssm[:row_count].copy_(initial_ssm_table[:row_count])
    spec_conv[:row_count].copy_(initial_conv_table[:row_count])
    spec_ssm[:row_count].copy_(initial_ssm_table[:row_count])

    if accepted_counts is None:
        source_cols = torch.zeros((num_reqs,), dtype=torch.long, device=device)
    else:
        source_offset = 0 if args.prefix_base_state else -1
        source_cols = torch.clamp(
            accepted_counts.to(torch.long) + source_offset,
            min=0,
            max=spec_len - 1)
    source_rows = state_table.gather(1, source_cols.unsqueeze(1)).squeeze(1)
    ref_conv.index_copy_(0, running_rows,
                         ref_conv.index_select(0, source_rows).clone())
    ref_ssm.index_copy_(0, running_rows,
                        ref_ssm.index_select(0, source_rows).clone())

    ref_out, ref_z, ref_conv_prefixes, ref_ssm_prefixes = run_normal_decode_steps(
        torch,
        args,
        inputs,
        conv_state=ref_conv,
        ssm_state=ref_ssm,
        running_rows=running_rows,
        token_base=token_base,
    )
    spec_out, spec_z = run_spec_decode(
        torch,
        args,
        inputs,
        conv_state=spec_conv,
        ssm_state=spec_ssm,
        state_table=state_table,
        num_accepted_tokens=accepted_counts,
        token_base=token_base,
    )
    torch.xpu.synchronize()

    conv_ok = True
    ssm_ok = True
    conv_close = True
    ssm_close = True
    conv_max = 0.0
    ssm_max = 0.0
    for pos in range(spec_len):
        if args.prefix_base_state:
            if pos + 1 >= state_table.size(1):
                continue
            rows = state_table[:, pos + 1]
        else:
            rows = state_table[:, pos]
        observed_conv = spec_conv.index_select(0, rows)
        observed_ssm = spec_ssm.index_select(0, rows)
        expected_conv = ref_conv_prefixes[pos]
        expected_ssm = ref_ssm_prefixes[pos]
        conv_diff = max_abs(torch, observed_conv, expected_conv)
        ssm_diff = max_abs(torch, observed_ssm, expected_ssm)
        conv_max = max(conv_max, conv_diff)
        ssm_max = max(ssm_max, ssm_diff)
        conv_ok = conv_ok and bool(torch.equal(observed_conv, expected_conv))
        ssm_ok = ssm_ok and bool(torch.equal(observed_ssm, expected_ssm))
        conv_close = conv_close and close_enough(
            torch, observed_conv, expected_conv, atol=args.atol, rtol=args.rtol)
        ssm_close = ssm_close and close_enough(
            torch, observed_ssm, expected_ssm, atol=args.atol, rtol=args.rtol)

    base_conv_close = True
    base_ssm_close = True
    base_conv_max = 0.0
    base_ssm_max = 0.0
    if args.prefix_base_state:
        base_rows = state_table[:, 0]
        observed_base_conv = spec_conv.index_select(0, base_rows)
        observed_base_ssm = spec_ssm.index_select(0, base_rows)
        expected_base_conv = initial_conv_table.index_select(0, source_rows)
        expected_base_ssm = initial_ssm_table.index_select(0, source_rows)
        base_conv_max = max_abs(torch, observed_base_conv, expected_base_conv)
        base_ssm_max = max_abs(torch, observed_base_ssm, expected_base_ssm)
        base_conv_close = close_enough(
            torch, observed_base_conv, expected_base_conv, atol=args.atol,
            rtol=args.rtol)
        base_ssm_close = close_enough(
            torch, observed_base_ssm, expected_base_ssm, atol=args.atol,
            rtol=args.rtol)

    out_diff = max_abs(torch, spec_out, ref_out)
    z_diff = max_abs(torch, spec_z, ref_z)
    out_equal = bool(torch.equal(spec_out, ref_out))
    z_equal = bool(torch.equal(spec_z, ref_z))
    out_close = close_enough(torch, spec_out, ref_out, atol=args.atol,
                             rtol=args.rtol)
    z_close = close_enough(torch, spec_z, ref_z, atol=args.atol,
                           rtol=args.rtol)
    return {
        "case": case_name,
        "accepted_counts": (
            None if accepted_counts is None
            else [int(x) for x in accepted_counts.detach().cpu().tolist()]
        ),
        "source_cols": [int(x) for x in source_cols.detach().cpu().tolist()],
        "conv_prefix_equal": bool(conv_ok),
        "ssm_prefix_equal": bool(ssm_ok),
        "conv_prefix_close": bool(conv_close),
        "ssm_prefix_close": bool(ssm_close),
        "base_column_close": bool(base_conv_close and base_ssm_close),
        "core_output_equal": out_equal,
        "z_output_equal": z_equal,
        "core_output_close": bool(out_close),
        "z_output_close": bool(z_close),
        "conv_prefix_max_abs_diff": conv_max,
        "ssm_prefix_max_abs_diff": ssm_max,
        "base_conv_max_abs_diff": base_conv_max,
        "base_ssm_max_abs_diff": base_ssm_max,
        "core_output_max_abs_diff": out_diff,
        "z_output_max_abs_diff": z_diff,
    }


def main() -> int:
    args = parse_args()
    if args.num_k_heads % args.tp_size != 0:
        raise SystemExit("num-k-heads must be divisible by tp-size")
    if args.num_v_heads % args.tp_size != 0:
        raise SystemExit("num-v-heads must be divisible by tp-size")
    if args.num_v_heads % args.num_k_heads != 0:
        raise SystemExit("num-v-heads must be divisible by num-k-heads")
    if args.head_k_dim % 32 != 0:
        raise SystemExit("head-k-dim must be a multiple of 32")

    os.environ.setdefault("VLLM_TARGET_DEVICE", "xpu")
    os.environ["VLLM_XPU_GDN_NATIVE_SPEC_PREFIX_BASE_STATE"] = (
        "1" if args.prefix_base_state else "0")
    add_kernel_repo_to_path(args.kernel_repo)

    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    torch.xpu.set_device(torch.device(args.device))
    torch.manual_seed(args.seed)
    torch.xpu.manual_seed_all(args.seed)

    total_tokens = args.num_reqs * args.spec_len
    inputs = build_inputs(torch, args, tokens=total_tokens * 2, seed=args.seed)
    dtype = inputs["dtype"]
    local_v_heads = inputs["local_v_heads"]
    conv_cols = inputs["conv_cols"]
    device = args.device

    state_cols = args.spec_len
    state_table = torch.arange(
        1,
        1 + args.num_reqs * state_cols,
        dtype=torch.long,
        device=device,
    ).reshape(args.num_reqs, state_cols)
    row_count = int(state_table.max().detach().cpu().item()) + 1

    initial_conv = torch.randn((row_count, args.width - 1, conv_cols),
                               dtype=dtype, device=device) * 0.01
    initial_ssm = torch.randn((row_count, local_v_heads, args.head_v_dim,
                               args.head_k_dim), dtype=dtype,
                              device=device) * 0.01

    cases: list[dict[str, Any]] = []
    first_counts = torch.ones((args.num_reqs,), dtype=torch.int32,
                              device=device)
    cases.append(compare_case(
        torch,
        args,
        inputs,
        case_name="fresh_source_col0",
        initial_conv_table=initial_conv,
        initial_ssm_table=initial_ssm,
        state_table=state_table,
        accepted_counts=first_counts,
        token_base=0,
    ))

    # Build a realistic restart table by using the first pass's expected
    # prefixes as the available source columns, then verify that accepted count
    # N starts the next packed step from column N-1.
    restart_conv = initial_conv.clone()
    restart_ssm = initial_ssm.clone()
    running_rows = torch.arange(row_count, row_count + args.num_reqs,
                                dtype=torch.long, device=device)
    ref_conv = torch.zeros((row_count + args.num_reqs, args.width - 1,
                            conv_cols), dtype=dtype, device=device)
    ref_ssm = torch.zeros((row_count + args.num_reqs, local_v_heads,
                           args.head_v_dim, args.head_k_dim), dtype=dtype,
                          device=device)
    ref_conv[:row_count].copy_(initial_conv)
    ref_ssm[:row_count].copy_(initial_ssm)
    ref_conv.index_copy_(0, running_rows,
                         initial_conv.index_select(0, state_table[:, 0]))
    ref_ssm.index_copy_(0, running_rows,
                        initial_ssm.index_select(0, state_table[:, 0]))
    _, _, conv_prefixes, ssm_prefixes = run_normal_decode_steps(
        torch,
        args,
        inputs,
        conv_state=ref_conv,
        ssm_state=ref_ssm,
        running_rows=running_rows,
        token_base=0,
    )
    if args.prefix_base_state:
        for pos in range(max(0, args.spec_len - 1)):
            restart_conv.index_copy_(0, state_table[:, pos + 1],
                                     conv_prefixes[pos])
            restart_ssm.index_copy_(0, state_table[:, pos + 1],
                                    ssm_prefixes[pos])
    else:
        for pos in range(args.spec_len):
            restart_conv.index_copy_(0, state_table[:, pos], conv_prefixes[pos])
            restart_ssm.index_copy_(0, state_table[:, pos], ssm_prefixes[pos])

    varied_counts = (
        torch.arange(args.num_reqs, dtype=torch.int32, device=device)
        % args.spec_len
    ) + 1
    cases.append(compare_case(
        torch,
        args,
        inputs,
        case_name="restart_from_varied_accepted_counts",
        initial_conv_table=restart_conv,
        initial_ssm_table=restart_ssm,
        state_table=state_table,
        accepted_counts=varied_counts,
        token_base=total_tokens,
    ))

    result = {
        "device": args.device,
        "dtype": args.dtype,
        "seed": args.seed,
        "num_reqs": args.num_reqs,
        "spec_len": args.spec_len,
        "num_k_heads": args.num_k_heads,
        "num_v_heads": args.num_v_heads,
        "head_k_dim": args.head_k_dim,
        "head_v_dim": args.head_v_dim,
        "width": args.width,
        "atol": args.atol,
        "rtol": args.rtol,
        "contract": {
            "state_column_j": (
                "column j+1 is state after packed spec row j"
                if args.prefix_base_state
                else "column j is state after packed spec row j"
            ),
            "source_column": (
                "clamp(num_accepted_tokens, 0, spec_len - 1)"
                if args.prefix_base_state
                else "clamp(num_accepted_tokens - 1, 0, spec_len - 1)"
            ),
            "base_column": (
                "column 0 is selected base/running state"
                if args.prefix_base_state
                else "no separate base column in native packed table"
            ),
            "prefix_base_state": bool(args.prefix_base_state),
        },
        "cases": cases,
    }
    result["passed"] = all(
        case["conv_prefix_close"]
        and case["ssm_prefix_close"]
        and case["base_column_close"]
        and case["core_output_close"]
        and case["z_output_close"]
        for case in cases
    )

    text = json.dumps(result, sort_keys=True)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit("native spec prefix contract mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
