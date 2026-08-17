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
SPEC_CONV_PADDING_SENTINEL = 0.03125
SSM_ROW_PADDING_SENTINEL = 0.015625


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--dtype", choices=("bf16", "fp16", "fp32"),
                        default="bf16")
    parser.add_argument(
        "--ssm-dtype", choices=("same", "bf16", "fp16", "fp32"),
        default="same",
        help="State-cache dtype; use fp32 for the Qwen3.6 27B server identity.")
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
    parser.add_argument(
        "--spec-conv-extra-state-len",
        type=int,
        default=0,
        help=(
            "Extra physical convolution-cache positions reserved by the "
            "speculative runtime. Qwen MTP3 uses 3, producing a six-wide "
            "candidate cache for a three-position causal history."
        ),
    )
    parser.add_argument(
        "--ssm-row-padding-elements",
        type=int,
        default=0,
        help=(
            "Add inaccessible physical elements after each logical SSM row. "
            "The production unified cache has stride(0) larger than the "
            "logical rank-4 state; poisoning this gap catches row copies that "
            "incorrectly use the physical stride as an element count."
        ),
    )
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
    parser.add_argument(
        "--require-bit-exact", action="store_true",
        help="Fail unless convolution, SSM, core output, and z are byte-exact.")
    parser.add_argument(
        "--exact-recurrent", action="store_true",
        help="Enable the serial native-recurrence proof implementation.")
    parser.add_argument(
        "--persistent-scratch", action="store_true",
        help="Reuse the production persistent native speculative scratch.")
    parser.add_argument(
        "--zero-state-smoke", action="store_true",
        help=(
            "Run the exact packed op twice with the graph-capture NULL state "
            "table [[0, ...]], synchronize, and require the SSM cache to stay "
            "unchanged without a device fault."
        ),
    )
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


def make_spec_conv_table(
    torch: Any,
    args: argparse.Namespace,
    initial_conv_table: Any,
    *,
    rows: int,
    conv_cols: int,
    dtype: Any,
    device: str,
) -> Any:
    """Build the production-shaped speculative cache with a poisoned tail."""
    history_len = args.width - 1
    physical_state_len = history_len + args.spec_conv_extra_state_len
    spec_conv = torch.full(
        (rows, physical_state_len, conv_cols),
        SPEC_CONV_PADDING_SENTINEL,
        dtype=dtype,
        device=device,
    )
    spec_conv[:, :history_len].zero_()
    initial_rows = min(rows, initial_conv_table.size(0))
    spec_conv[:initial_rows, :history_len].copy_(
        initial_conv_table[:initial_rows, :history_len]
    )
    return spec_conv


def spec_padding_equal(torch: Any, args: argparse.Namespace,
                       spec_conv: Any) -> bool:
    history_len = args.width - 1
    if spec_conv.size(1) == history_len:
        return True
    padding = spec_conv[:, history_len:]
    expected = torch.full_like(padding, SPEC_CONV_PADDING_SENTINEL)
    return bool(torch.equal(padding, expected))


def make_spec_ssm_table(
    torch: Any,
    args: argparse.Namespace,
    initial_ssm_table: Any,
    *,
    rows: int,
    local_v_heads: int,
    dtype: Any,
    device: str,
) -> Any:
    """Build an SSM view whose physical row stride can exceed its shape."""
    logical_row_elements = (
        local_v_heads * args.head_v_dim * args.head_k_dim
    )
    row_stride = logical_row_elements + args.ssm_row_padding_elements
    storage = torch.zeros(
        (rows * row_stride,), dtype=dtype, device=device)
    spec_ssm = torch.as_strided(
        storage,
        size=(rows, local_v_heads, args.head_v_dim, args.head_k_dim),
        stride=(
            row_stride,
            args.head_v_dim * args.head_k_dim,
            args.head_k_dim,
            1,
        ),
    )
    if args.ssm_row_padding_elements:
        physical = torch.as_strided(
            spec_ssm,
            size=(rows, row_stride),
            stride=(row_stride, 1),
        )
        row_values = (
            torch.arange(1, rows + 1, dtype=torch.float32, device=device)
            * SSM_ROW_PADDING_SENTINEL
        ).to(dtype)
        physical[:, logical_row_elements:].copy_(
            row_values.unsqueeze(1).expand(
                rows, args.ssm_row_padding_elements))
    initial_rows = min(rows, initial_ssm_table.size(0))
    spec_ssm[:initial_rows].copy_(initial_ssm_table[:initial_rows])
    return spec_ssm


def ssm_padding_equal(torch: Any, args: argparse.Namespace,
                      spec_ssm: Any) -> bool:
    if not args.ssm_row_padding_elements:
        return True
    rows = spec_ssm.size(0)
    logical_row_elements = (
        spec_ssm.size(1) * spec_ssm.size(2) * spec_ssm.size(3)
    )
    row_stride = logical_row_elements + args.ssm_row_padding_elements
    physical = torch.as_strided(
        spec_ssm,
        size=(rows, row_stride),
        stride=(row_stride, 1),
    )
    padding = physical[:, logical_row_elements:]
    row_values = (
        torch.arange(1, rows + 1, dtype=torch.float32,
                     device=spec_ssm.device)
        * SSM_ROW_PADDING_SENTINEL
    ).to(spec_ssm.dtype)
    expected = row_values.unsqueeze(1).expand_as(padding)
    return bool(torch.equal(padding, expected))


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
    ssm_dtype = initial_ssm_table.dtype
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
                           args.head_k_dim), dtype=ssm_dtype, device=device)
    spec_conv = make_spec_conv_table(
        torch,
        args,
        initial_conv_table,
        rows=total_rows,
        conv_cols=conv_cols,
        dtype=dtype,
        device=device,
    )
    spec_ssm = make_spec_ssm_table(
        torch,
        args,
        initial_ssm_table,
        rows=total_rows,
        local_v_heads=local_v_heads,
        dtype=ssm_dtype,
        device=device,
    )
    ref_conv[:row_count].copy_(initial_conv_table[:row_count])
    ref_ssm[:row_count].copy_(initial_ssm_table[:row_count])

    if accepted_counts is None:
        source_cols = torch.zeros((num_reqs,), dtype=torch.long, device=device)
    else:
        source_offset = 0 if args.prefix_base_state else -1
        source_max = spec_len if args.prefix_base_state else spec_len - 1
        source_cols = torch.clamp(
            accepted_counts.to(torch.long) + source_offset,
            min=0,
            max=source_max)
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
        observed_conv = spec_conv.index_select(0, rows)[:, :args.width - 1]
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
    base_conv_equal = True
    base_ssm_equal = True
    base_conv_max = 0.0
    base_ssm_max = 0.0
    if args.prefix_base_state:
        base_rows = state_table[:, 0]
        observed_base_conv = spec_conv.index_select(
            0, base_rows)[:, :args.width - 1]
        observed_base_ssm = spec_ssm.index_select(0, base_rows)
        expected_base_conv = initial_conv_table.index_select(0, source_rows)
        expected_base_ssm = initial_ssm_table.index_select(0, source_rows)
        base_conv_max = max_abs(torch, observed_base_conv, expected_base_conv)
        base_ssm_max = max_abs(torch, observed_base_ssm, expected_base_ssm)
        base_conv_equal = bool(torch.equal(observed_base_conv,
                                           expected_base_conv))
        base_ssm_equal = bool(torch.equal(observed_base_ssm,
                                          expected_base_ssm))
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
        "conv_padding_equal": spec_padding_equal(torch, args, spec_conv),
        "ssm_prefix_close": bool(ssm_close),
        "ssm_padding_equal": ssm_padding_equal(torch, args, spec_ssm),
        "base_column_close": bool(base_conv_close and base_ssm_close),
        "base_column_equal": bool(base_conv_equal and base_ssm_equal),
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


def compare_two_call_full_accept_restart(
    torch: Any,
    args: argparse.Namespace,
    inputs: dict[str, Any],
    *,
    initial_conv_table: Any,
    initial_ssm_table: Any,
    state_table: Any,
) -> dict[str, Any]:
    """Exercise the literal production full-accept cross-call lifecycle."""
    dtype = inputs["dtype"]
    ssm_dtype = initial_ssm_table.dtype
    local_v_heads = inputs["local_v_heads"]
    conv_cols = inputs["conv_cols"]
    device = args.device
    num_reqs = args.num_reqs
    spec_len = args.spec_len
    total_tokens = num_reqs * spec_len

    row_count = int(state_table.max().detach().cpu().item()) + 1
    running_rows = torch.arange(
        row_count, row_count + num_reqs, dtype=torch.long, device=device)
    total_rows = row_count + num_reqs

    ref_conv = torch.zeros(
        (total_rows, args.width - 1, conv_cols), dtype=dtype, device=device)
    ref_ssm = torch.zeros(
        (total_rows, local_v_heads, args.head_v_dim, args.head_k_dim),
        dtype=ssm_dtype,
        device=device,
    )
    spec_conv = make_spec_conv_table(
        torch,
        args,
        initial_conv_table,
        rows=row_count,
        conv_cols=conv_cols,
        dtype=dtype,
        device=device,
    )
    spec_ssm = make_spec_ssm_table(
        torch,
        args,
        initial_ssm_table,
        rows=row_count,
        local_v_heads=local_v_heads,
        dtype=ssm_dtype,
        device=device,
    )
    ref_conv[:row_count].copy_(initial_conv_table[:row_count])
    ref_ssm[:row_count].copy_(initial_ssm_table[:row_count])
    source_rows = state_table[:, 0]
    ref_conv.index_copy_(
        0, running_rows, ref_conv.index_select(0, source_rows).clone())
    ref_ssm.index_copy_(
        0, running_rows, ref_ssm.index_select(0, source_rows).clone())

    ref_out_first, ref_z_first, ref_conv_first, ref_ssm_first = (
        run_normal_decode_steps(
            torch,
            args,
            inputs,
            conv_state=ref_conv,
            ssm_state=ref_ssm,
            running_rows=running_rows,
            token_base=0,
        )
    )
    ref_out_second, ref_z_second, ref_conv_second, ref_ssm_second = (
        run_normal_decode_steps(
            torch,
            args,
            inputs,
            conv_state=ref_conv,
            ssm_state=ref_ssm,
            running_rows=running_rows,
            token_base=total_tokens,
        )
    )

    first_counts = torch.full(
        (num_reqs,), 0 if args.prefix_base_state else 1,
        dtype=torch.int32,
        device=device,
    )
    full_counts = torch.full(
        (num_reqs,), spec_len, dtype=torch.int32, device=device)
    spec_out_first, spec_z_first = run_spec_decode(
        torch,
        args,
        inputs,
        conv_state=spec_conv,
        ssm_state=spec_ssm,
        state_table=state_table,
        num_accepted_tokens=first_counts,
        token_base=0,
    )
    spec_out_second, spec_z_second = run_spec_decode(
        torch,
        args,
        inputs,
        conv_state=spec_conv,
        ssm_state=spec_ssm,
        state_table=state_table,
        num_accepted_tokens=full_counts,
        token_base=total_tokens,
    )
    torch.xpu.synchronize()

    conv_equal = True
    ssm_equal = True
    conv_close = True
    ssm_close = True
    conv_max = 0.0
    ssm_max = 0.0
    for pos in range(spec_len):
        rows = state_table[:, pos + (1 if args.prefix_base_state else 0)]
        observed_conv = spec_conv.index_select(0, rows)[:, :args.width - 1]
        observed_ssm = spec_ssm.index_select(0, rows)
        expected_conv = ref_conv_second[pos]
        expected_ssm = ref_ssm_second[pos]
        conv_max = max(conv_max, max_abs(torch, observed_conv, expected_conv))
        ssm_max = max(ssm_max, max_abs(torch, observed_ssm, expected_ssm))
        conv_equal = conv_equal and bool(torch.equal(observed_conv, expected_conv))
        ssm_equal = ssm_equal and bool(torch.equal(observed_ssm, expected_ssm))
        conv_close = conv_close and close_enough(
            torch, observed_conv, expected_conv, atol=args.atol, rtol=args.rtol)
        ssm_close = ssm_close and close_enough(
            torch, observed_ssm, expected_ssm, atol=args.atol, rtol=args.rtol)

    first_out_equal = bool(torch.equal(spec_out_first, ref_out_first))
    first_z_equal = bool(torch.equal(spec_z_first, ref_z_first))
    second_out_equal = bool(torch.equal(spec_out_second, ref_out_second))
    second_z_equal = bool(torch.equal(spec_z_second, ref_z_second))
    first_out_close = close_enough(
        torch, spec_out_first, ref_out_first, atol=args.atol, rtol=args.rtol)
    first_z_close = close_enough(
        torch, spec_z_first, ref_z_first, atol=args.atol, rtol=args.rtol)
    second_out_close = close_enough(
        torch, spec_out_second, ref_out_second, atol=args.atol, rtol=args.rtol)
    second_z_close = close_enough(
        torch, spec_z_second, ref_z_second, atol=args.atol, rtol=args.rtol)
    base_conv_equal = True
    base_ssm_equal = True
    base_conv_close = True
    base_ssm_close = True
    base_conv_max = 0.0
    base_ssm_max = 0.0
    if args.prefix_base_state:
        base_rows = state_table[:, 0]
        observed_base_conv = spec_conv.index_select(
            0, base_rows)[:, :args.width - 1]
        observed_base_ssm = spec_ssm.index_select(0, base_rows)
        expected_base_conv = ref_conv_first[-1]
        expected_base_ssm = ref_ssm_first[-1]
        base_conv_equal = bool(torch.equal(
            observed_base_conv, expected_base_conv))
        base_ssm_equal = bool(torch.equal(
            observed_base_ssm, expected_base_ssm))
        base_conv_close = close_enough(
            torch, observed_base_conv, expected_base_conv,
            atol=args.atol, rtol=args.rtol)
        base_ssm_close = close_enough(
            torch, observed_base_ssm, expected_base_ssm,
            atol=args.atol, rtol=args.rtol)
        base_conv_max = max_abs(
            torch, observed_base_conv, expected_base_conv)
        base_ssm_max = max_abs(
            torch, observed_base_ssm, expected_base_ssm)
    return {
        "case": "two_call_full_accept_restart",
        "accepted_counts": [spec_len] * num_reqs,
        "source_cols": [
            spec_len if args.prefix_base_state else spec_len - 1
        ] * num_reqs,
        "conv_prefix_equal": conv_equal,
        "ssm_prefix_equal": ssm_equal,
        "conv_prefix_close": conv_close,
        "conv_padding_equal": spec_padding_equal(torch, args, spec_conv),
        "ssm_prefix_close": ssm_close,
        "ssm_padding_equal": ssm_padding_equal(torch, args, spec_ssm),
        "base_column_equal": base_conv_equal and base_ssm_equal,
        "base_column_close": base_conv_close and base_ssm_close,
        "core_output_equal": first_out_equal and second_out_equal,
        "z_output_equal": first_z_equal and second_z_equal,
        "core_output_close": first_out_close and second_out_close,
        "z_output_close": first_z_close and second_z_close,
        "conv_prefix_max_abs_diff": conv_max,
        "ssm_prefix_max_abs_diff": ssm_max,
        "base_conv_max_abs_diff": base_conv_max,
        "base_ssm_max_abs_diff": base_ssm_max,
        "core_output_max_abs_diff": max(
            max_abs(torch, spec_out_first, ref_out_first),
            max_abs(torch, spec_out_second, ref_out_second),
        ),
        "z_output_max_abs_diff": max(
            max_abs(torch, spec_z_first, ref_z_first),
            max_abs(torch, spec_z_second, ref_z_second),
        ),
        "first_call_core_output_equal": first_out_equal,
        "first_call_z_output_equal": first_z_equal,
        "second_call_core_output_equal": second_out_equal,
        "second_call_z_output_equal": second_z_equal,
    }


def main() -> int:
    args = parse_args()
    if args.spec_conv_extra_state_len < 0:
        raise SystemExit("spec-conv-extra-state-len must be non-negative")
    if args.ssm_row_padding_elements < 0:
        raise SystemExit("ssm-row-padding-elements must be non-negative")
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
    os.environ["VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT"] = (
        "1" if args.exact_recurrent else "0")
    os.environ["VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH"] = (
        "1" if args.persistent_scratch else "0")
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
    ssm_dtype = (
        dtype if args.ssm_dtype == "same"
        else dtype_from_name(torch, args.ssm_dtype)
    )
    local_v_heads = inputs["local_v_heads"]
    conv_cols = inputs["conv_cols"]
    device = args.device

    if args.zero_state_smoke:
        if not args.exact_recurrent or args.num_reqs != 1:
            raise SystemExit(
                "zero-state-smoke requires --exact-recurrent --num-reqs 1"
            )
        initial_conv = torch.randn(
            (1, args.width - 1, conv_cols), dtype=dtype, device=device
        ) * 0.01
        initial_ssm = torch.randn(
            (1, local_v_heads, args.head_v_dim, args.head_k_dim),
            dtype=ssm_dtype,
            device=device,
        ) * 0.01
        conv_state = make_spec_conv_table(
            torch,
            args,
            initial_conv,
            rows=1,
            conv_cols=conv_cols,
            dtype=dtype,
            device=device,
        )
        ssm_state = make_spec_ssm_table(
            torch,
            args,
            initial_ssm,
            rows=1,
            local_v_heads=local_v_heads,
            dtype=ssm_dtype,
            device=device,
        )
        ssm_before = ssm_state.clone()
        state_cols = args.spec_len + (1 if args.prefix_base_state else 0)
        state_table = torch.zeros(
            (1, state_cols), dtype=torch.long, device=device
        )
        accepted = torch.ones((1,), dtype=torch.int32, device=device)
        for _ in range(2):
            run_spec_decode(
                torch,
                args,
                inputs,
                conv_state=conv_state,
                ssm_state=ssm_state,
                state_table=state_table,
                num_accepted_tokens=accepted,
                token_base=0,
            )
        torch.xpu.synchronize()
        result = {
            "schema_version": 1,
            "case": "exact_recurrent_zero_state_smoke",
            "runs": 2,
            "state_table": [[0] * state_cols],
            "ssm_unchanged": bool(torch.equal(ssm_state, ssm_before)),
            "ssm_padding_equal": ssm_padding_equal(torch, args, ssm_state),
        }
        result["passed"] = (
            result["ssm_unchanged"] and result["ssm_padding_equal"]
        )
        text = json.dumps(result, sort_keys=True)
        print(text)
        if args.json_out is not None:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(text + "\n", encoding="utf-8")
        if not result["passed"]:
            raise SystemExit("zero-state exact recurrent smoke failed")
        return 0

    state_cols = args.spec_len + (1 if args.prefix_base_state else 0)
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
                               args.head_k_dim), dtype=ssm_dtype,
                              device=device) * 0.01

    cases: list[dict[str, Any]] = []
    if args.prefix_base_state:
        zero_counts = torch.zeros((args.num_reqs,), dtype=torch.int32,
                                  device=device)
        cases.append(compare_case(
            torch,
            args,
            inputs,
            case_name="full_reject_source_base_col0",
            initial_conv_table=initial_conv,
            initial_ssm_table=initial_ssm,
            state_table=state_table,
            accepted_counts=zero_counts,
            token_base=0,
        ))
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
    cases.append(compare_case(
        torch,
        args,
        inputs,
        case_name="fresh_second_token_window",
        initial_conv_table=initial_conv,
        initial_ssm_table=initial_ssm,
        state_table=state_table,
        accepted_counts=(
            torch.zeros((args.num_reqs,), dtype=torch.int32, device=device)
            if args.prefix_base_state else first_counts
        ),
        token_base=total_tokens,
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
                           args.head_v_dim, args.head_k_dim), dtype=ssm_dtype,
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
        for pos in range(args.spec_len):
            restart_conv.index_copy_(0, state_table[:, pos + 1],
                                     conv_prefixes[pos])
            restart_ssm.index_copy_(0, state_table[:, pos + 1],
                                    ssm_prefixes[pos])
    else:
        for pos in range(args.spec_len):
            restart_conv.index_copy_(0, state_table[:, pos], conv_prefixes[pos])
            restart_ssm.index_copy_(0, state_table[:, pos], ssm_prefixes[pos])

    if args.prefix_base_state:
        varied_counts = (
            torch.arange(args.num_reqs, dtype=torch.int32, device=device)
            % args.spec_len
        )
    else:
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
    # The production proof is deliberately restricted to one request.  A
    # single arange row would otherwise exercise only one accepted count, so
    # add one restart per source column. Prefix-base covers N=0..spec_len;
    # the legacy layout covers N=1..spec_len.
    if args.num_reqs == 1:
        accepted_start = 0 if args.prefix_base_state else 1
        for accepted_count in range(accepted_start, args.spec_len + 1):
            cases.append(compare_case(
                torch,
                args,
                inputs,
                case_name=f"restart_from_accepted_count_{accepted_count}",
                initial_conv_table=restart_conv,
                initial_ssm_table=restart_ssm,
                state_table=state_table,
                accepted_counts=torch.tensor(
                    [accepted_count], dtype=torch.int32, device=device),
                token_base=total_tokens,
            ))

    cases.append(compare_two_call_full_accept_restart(
        torch,
        args,
        inputs,
        initial_conv_table=initial_conv,
        initial_ssm_table=initial_ssm,
        state_table=state_table,
    ))

    result = {
        "device": args.device,
        "dtype": args.dtype,
        "ssm_dtype": args.ssm_dtype,
        "seed": args.seed,
        "num_reqs": args.num_reqs,
        "spec_len": args.spec_len,
        "num_k_heads": args.num_k_heads,
        "num_v_heads": args.num_v_heads,
        "head_k_dim": args.head_k_dim,
        "head_v_dim": args.head_v_dim,
        "width": args.width,
        "spec_conv_extra_state_len": args.spec_conv_extra_state_len,
        "spec_conv_physical_state_len": (
            args.width - 1 + args.spec_conv_extra_state_len
        ),
        "ssm_row_padding_elements": args.ssm_row_padding_elements,
        "exact_recurrent": bool(args.exact_recurrent),
        "persistent_scratch": bool(args.persistent_scratch),
        "atol": args.atol,
        "rtol": args.rtol,
        "contract": {
            "state_column_j": (
                "column j+1 is state after packed spec row j"
                if args.prefix_base_state
                else "column j is state after packed spec row j"
            ),
            "source_column": (
                "clamp(num_accepted_tokens, 0, spec_len)"
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
    if args.require_bit_exact:
        result["passed"] = all(
            case["conv_prefix_equal"]
            and case["conv_padding_equal"]
            and case["ssm_prefix_equal"]
            and case["ssm_padding_equal"]
            and case["base_column_equal"]
            and case["core_output_equal"]
            and case["z_output_equal"]
            for case in cases
        )
    else:
        result["passed"] = all(
            case["conv_prefix_close"]
            and case["conv_padding_equal"]
            and case["ssm_prefix_close"]
            and case["ssm_padding_equal"]
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
