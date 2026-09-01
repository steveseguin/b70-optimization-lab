#!/usr/bin/env python3
"""Compare packed c2 GDN execution with two isolated c1 transactions.

This is an operator diagnostic, not a performance benchmark.  It uses the
Qwen3.8-27B TP2 GDN dimensions and the exact state-index rows observed by R83.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("native", "r80-serial"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def configure_mode(mode: str) -> None:
    gates = {
        "VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT": "0",
        "VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT": "0",
        "VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT": "0",
        "VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT": "0",
        "VLLM_XPU_GDN_NATIVE_SPEC_METADATA_TRACE": "0",
        "VLLM_XPU_GDN_NATIVE_SPEC_EVOLVING_METADATA_TRACE": "0",
    }
    if mode == "r80-serial":
        gates.update({
            "VLLM_XPU_GDN_NATIVE_SPEC_CONV_SERIAL_EXACT": "1",
            "VLLM_XPU_GDN_NATIVE_SPEC_DELTA_SERIAL_EXACT": "1",
            "VLLM_XPU_GDN_NATIVE_SPEC_MULTI_REQUEST_SPLIT": "1",
        })
    os.environ.update(gates)


def comparison(torch, left, right) -> dict:
    finite = bool(torch.isfinite(left).all() and torch.isfinite(right).all())
    if left.numel():
        max_abs = float((left.float() - right.float()).abs().max().item())
    else:
        max_abs = 0.0
    return {
        "bitwise_equal": bool(torch.equal(left, right)),
        "finite": finite,
        "max_abs": max_abs,
    }


def run_transaction(
    torch,
    *,
    projected_qkvz,
    projected_ba,
    conv_initial,
    ssm_initial,
    conv_weights,
    conv_bias,
    a_log,
    dt_bias,
    state_indices,
    accepted,
    reorder_input: bool,
    isolated: bool,
):
    num_k_heads = 16
    num_v_heads = 48
    head_dim = 128
    tp_size = 2
    rows_per_request = 2
    num_requests = 2
    local_v_heads = num_v_heads // tp_size

    conv_state = conv_initial.clone()
    ssm_state = ssm_initial.clone()
    z = torch.zeros(
        (num_requests * rows_per_request, local_v_heads, head_dim),
        dtype=projected_qkvz.dtype,
        device=projected_qkvz.device,
    )
    core = torch.zeros_like(z)

    if not isolated:
        query_start = torch.tensor([0, 2, 4], dtype=torch.int32, device="xpu")
        token_indices = torch.tensor([0, 1, 2, 3],
                                     dtype=torch.int32,
                                     device="xpu")
        intermediates = torch.ops._xpu_C.causal_conv1d_spec(
            z,
            projected_qkvz,
            projected_ba,
            num_k_heads,
            num_v_heads,
            head_dim,
            head_dim,
            conv_state=conv_state,
            conv_weights=conv_weights,
            conv_bias=conv_bias,
            activation="silu",
            num_prefills=0,
            num_decodes=0,
            num_spec_decodes=2,
            spec_query_start_loc=query_start,
            spec_token_indx=token_indices,
            spec_state_indices_tensor=state_indices,
            num_accepted_tokens=accepted,
            num_actual_tokens=4,
            tp_size=tp_size,
            reorder_input=reorder_input,
        )
        torch.ops._xpu_C.gated_delta_rule_spec(
            core,
            *intermediates,
            num_v_heads,
            head_dim,
            A_log=a_log,
            dt_bias=dt_bias,
            ssm_state=ssm_state,
            num_prefills=0,
            num_decodes=0,
            num_spec_decodes=2,
            spec_query_start_loc=query_start,
            spec_token_indx=token_indices,
            spec_state_indices_tensor=state_indices,
            num_accepted_tokens=accepted,
            num_actual_tokens=4,
            tp_size=tp_size,
        )
    else:
        query_start = torch.tensor([0, 2], dtype=torch.int32, device="xpu")
        token_indices = torch.tensor([0, 1], dtype=torch.int32, device="xpu")
        for request in range(num_requests):
            start = request * rows_per_request
            qkvz_request = projected_qkvz.narrow(0, start, rows_per_request).contiguous()
            ba_request = projected_ba.narrow(0, start, rows_per_request).contiguous()
            z_request = torch.zeros_like(z.narrow(0, start, rows_per_request))
            core_request = torch.zeros_like(z_request)
            states_request = state_indices.narrow(0, request, 1).contiguous()
            accepted_request = accepted.narrow(0, request, 1).contiguous()
            intermediates = torch.ops._xpu_C.causal_conv1d_spec(
                z_request,
                qkvz_request,
                ba_request,
                num_k_heads,
                num_v_heads,
                head_dim,
                head_dim,
                conv_state=conv_state,
                conv_weights=conv_weights,
                conv_bias=conv_bias,
                activation="silu",
                num_prefills=0,
                num_decodes=0,
                num_spec_decodes=1,
                spec_query_start_loc=query_start,
                spec_token_indx=token_indices,
                spec_state_indices_tensor=states_request,
                num_accepted_tokens=accepted_request,
                num_actual_tokens=2,
                tp_size=tp_size,
                reorder_input=reorder_input,
            )
            torch.ops._xpu_C.gated_delta_rule_spec(
                core_request,
                *intermediates,
                num_v_heads,
                head_dim,
                A_log=a_log,
                dt_bias=dt_bias,
                ssm_state=ssm_state,
                num_prefills=0,
                num_decodes=0,
                num_spec_decodes=1,
                spec_query_start_loc=query_start,
                spec_token_indx=token_indices,
                spec_state_indices_tensor=states_request,
                num_accepted_tokens=accepted_request,
                num_actual_tokens=2,
                tp_size=tp_size,
            )
            z.narrow(0, start, rows_per_request).copy_(z_request)
            core.narrow(0, start, rows_per_request).copy_(core_request)

    torch.xpu.synchronize()
    return z, core, conv_state, ssm_state


def main() -> int:
    args = parse_args()
    configure_mode(args.mode)

    import torch
    import vllm_xpu_kernels._xpu_C  # noqa: F401

    if not torch.xpu.is_available() or torch.xpu.device_count() != 1:
        raise RuntimeError("R84 requires exactly one visible XPU")

    projected_dtype = torch.float16
    state_rows = (
        ((7, 6), (8, 9)),
        ((5, 4), (10, 11)),
        ((3, 2), (12, 13)),
    )
    accepted_pairs = ((1, 1), (1, 2), (2, 1), (2, 2))
    cases = []
    case_id = 0

    for ssm_dtype in (torch.float16, torch.float32):
        for reorder_input in (False, True):
            for accepted_pair in accepted_pairs:
                for state_row in state_rows:
                    torch.manual_seed(84000 + case_id)
                    device = "xpu"
                    num_k_heads = 16
                    num_v_heads = 48
                    head_dim = 128
                    tp_size = 2
                    local_k_heads = num_k_heads // tp_size
                    local_v_heads = num_v_heads // tp_size
                    mixed_qkvz = local_k_heads * (
                        2 * head_dim
                        + 2 * head_dim * num_v_heads // num_k_heads
                    )
                    mixed_ba = local_k_heads * (2 * num_v_heads // num_k_heads)
                    mixed_qkv = local_k_heads * (
                        2 * head_dim + head_dim * num_v_heads // num_k_heads
                    )
                    projected_qkvz = torch.randn(
                        4, mixed_qkvz, dtype=projected_dtype, device=device
                    )
                    projected_ba = torch.randn(
                        4, mixed_ba, dtype=projected_dtype, device=device
                    )
                    conv_initial = torch.randn(
                        16, 3, mixed_qkv, dtype=projected_dtype, device=device
                    )
                    ssm_initial = torch.randn(
                        16,
                        local_v_heads,
                        head_dim,
                        head_dim,
                        dtype=ssm_dtype,
                        device=device,
                    )
                    conv_weights = torch.randn(
                        mixed_qkv, 4, dtype=projected_dtype, device=device
                    )
                    conv_bias = torch.randn(
                        mixed_qkv, dtype=projected_dtype, device=device
                    )
                    a_log = torch.randn(
                        local_v_heads, dtype=torch.float32, device=device
                    )
                    dt_bias = torch.randn(
                        local_v_heads, dtype=projected_dtype, device=device
                    )
                    state_indices = torch.tensor(
                        state_row, dtype=torch.int32, device=device
                    )
                    accepted = torch.tensor(
                        accepted_pair, dtype=torch.int32, device=device
                    )

                    kwargs = dict(
                        torch=torch,
                        projected_qkvz=projected_qkvz,
                        projected_ba=projected_ba,
                        conv_initial=conv_initial,
                        ssm_initial=ssm_initial,
                        conv_weights=conv_weights,
                        conv_bias=conv_bias,
                        a_log=a_log,
                        dt_bias=dt_bias,
                        state_indices=state_indices,
                        accepted=accepted,
                        reorder_input=reorder_input,
                    )
                    packed = run_transaction(**kwargs, isolated=False)
                    isolated = run_transaction(**kwargs, isolated=True)
                    packed_repeat = run_transaction(**kwargs, isolated=False)
                    isolated_repeat = run_transaction(**kwargs, isolated=True)
                    touched = state_indices.flatten().to(torch.long)

                    case = {
                        "case_id": case_id,
                        "ssm_state_dtype": str(ssm_dtype),
                        "reorder_input": reorder_input,
                        "accepted_pair": list(accepted_pair),
                        "state_indices": [list(row) for row in state_row],
                        "packed_vs_isolated": {
                            "z": comparison(torch, packed[0], isolated[0]),
                            "core": comparison(torch, packed[1], isolated[1]),
                            "conv_touched": comparison(
                                torch,
                                packed[2].index_select(0, touched),
                                isolated[2].index_select(0, touched),
                            ),
                            "ssm_touched": comparison(
                                torch,
                                packed[3].index_select(0, touched),
                                isolated[3].index_select(0, touched),
                            ),
                        },
                        "packed_repeat_exact": all(
                            torch.equal(a, b)
                            for a, b in zip(packed, packed_repeat)
                        ),
                        "isolated_repeat_exact": all(
                            torch.equal(a, b)
                            for a, b in zip(isolated, isolated_repeat)
                        ),
                    }
                    cases.append(case)
                    case_id += 1

    fields = ("z", "core", "conv_touched", "ssm_touched")
    summary = {
        field: {
            "bitwise_equal_cases": sum(
                case["packed_vs_isolated"][field]["bitwise_equal"]
                for case in cases
            ),
            "max_abs_across_cases": max(
                case["packed_vs_isolated"][field]["max_abs"]
                for case in cases
            ),
        }
        for field in fields
    }
    result = {
        "schema": "neural.download.qwen38-gdn-c2-isolation-operator.v1",
        "mode": args.mode,
        "case_count": len(cases),
        "all_finite": all(
            comparison_result["finite"]
            for case in cases
            for comparison_result in case["packed_vs_isolated"].values()
        ),
        "packed_repeat_exact_cases": sum(
            case["packed_repeat_exact"] for case in cases
        ),
        "isolated_repeat_exact_cases": sum(
            case["isolated_repeat_exact"] for case in cases
        ),
        "summary": summary,
        "cases": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
