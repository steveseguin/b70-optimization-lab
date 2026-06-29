#!/usr/bin/env python3
"""Synthetic GDN speculative recurrent-state parity check.

This exercises the verifier state contract without launching a vLLM server:
packed spec rows must leave each speculative state column equal to processing
the same rows one token at a time.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _repo_root() -> str:
    return os.environ.get("VLLM_REPO_ROOT", "/home/steve/src/vllm")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="xpu:0")
    parser.add_argument("--num-reqs", type=int, default=2)
    parser.add_argument("--spec-len", type=int, default=3)
    parser.add_argument("--heads", type=int, default=2)
    parser.add_argument("--dim", type=int, default=8)
    args = parser.parse_args()

    os.environ.setdefault("VLLM_TARGET_DEVICE", "xpu")
    sys.path.insert(0, _repo_root())

    import torch

    if not hasattr(torch, "xpu") or not torch.xpu.is_available():
        raise SystemExit("torch.xpu is not available")

    from vllm.model_executor.layers.fla.ops import (
        fused_sigmoid_gating_delta_rule_update,
    )

    device = torch.device(args.device)
    torch.xpu.set_device(device)
    torch.manual_seed(20260620)
    torch.xpu.manual_seed_all(20260620)

    num_reqs = args.num_reqs
    spec_len = args.spec_len
    heads = args.heads
    dim = args.dim
    total_tokens = num_reqs * spec_len
    dtype = torch.bfloat16
    state_dtype = torch.bfloat16

    q = torch.randn((1, total_tokens, heads, dim), device=device, dtype=dtype)
    k = torch.randn((1, total_tokens, heads, dim), device=device, dtype=dtype)
    v = torch.randn((1, total_tokens, heads, dim), device=device, dtype=dtype)
    a = torch.randn((total_tokens, heads), device=device, dtype=dtype)
    b = torch.randn((total_tokens, heads), device=device, dtype=dtype)
    a_log = torch.randn((heads,), device=device, dtype=torch.float32)
    dt_bias = torch.randn((heads,), device=device, dtype=torch.float32)

    row_count = 1 + num_reqs * spec_len
    state_table = torch.empty((num_reqs, spec_len),
                              device=device,
                              dtype=torch.int64)
    next_row = 1
    for pos in range(spec_len):
        rows = torch.arange(next_row,
                            next_row + num_reqs,
                            device=device,
                            dtype=torch.int64)
        state_table[:, pos] = rows
        next_row += num_reqs

    initial_state = torch.randn((num_reqs, heads, dim, dim),
                                device=device,
                                dtype=state_dtype)
    query_starts = torch.arange(0,
                                total_tokens + 1,
                                spec_len,
                                device=device,
                                dtype=torch.int32)
    one_token_starts = torch.arange(num_reqs + 1,
                                    device=device,
                                    dtype=torch.int32)
    query_offsets = query_starts[:-1].to(torch.long)
    scale = dim**-0.5

    reference_state = torch.zeros((row_count, heads, dim, dim),
                                  device=device,
                                  dtype=state_dtype)
    reference_running_rows = state_table[:, 0]
    reference_state.index_copy_(0, reference_running_rows, initial_state)
    reference_columns = torch.zeros_like(reference_state)
    reference_out = torch.empty((1, total_tokens, heads, dim),
                                device=device,
                                dtype=dtype)

    candidate_state = torch.randn((row_count, heads, dim, dim),
                                  device=device,
                                  dtype=state_dtype)
    candidate_state.index_copy_(0, state_table[:, 0], initial_state)
    candidate_out = torch.empty_like(reference_out)

    for pos in range(spec_len):
        token_indices = query_offsets + pos
        q_step = q.index_select(1, token_indices)
        k_step = k.index_select(1, token_indices)
        v_step = v.index_select(1, token_indices)
        a_step = a.index_select(0, token_indices)
        b_step = b.index_select(0, token_indices)

        ref_step, _ = fused_sigmoid_gating_delta_rule_update(
            A_log=a_log,
            a=a_step,
            b=b_step,
            dt_bias=dt_bias,
            q=q_step,
            k=k_step,
            v=v_step,
            initial_state=reference_state,
            inplace_final_state=True,
            cu_seqlens=one_token_starts,
            ssm_state_indices=reference_running_rows,
            use_qk_l2norm_in_kernel=True,
        )
        reference_out.index_copy_(1, token_indices, ref_step)
        reference_columns.index_copy_(
            0,
            state_table[:, pos],
            reference_state.index_select(0, reference_running_rows).clone(),
        )

        candidate_rows = state_table[:, pos]
        if pos > 0:
            previous_rows = state_table[:, pos - 1]
            candidate_state.index_copy_(
                0,
                candidate_rows,
                candidate_state.index_select(0, previous_rows).clone(),
            )
        cand_step, _ = fused_sigmoid_gating_delta_rule_update(
            A_log=a_log,
            a=a_step,
            b=b_step,
            dt_bias=dt_bias,
            q=q_step,
            k=k_step,
            v=v_step,
            initial_state=candidate_state,
            inplace_final_state=True,
            cu_seqlens=one_token_starts,
            ssm_state_indices=candidate_rows,
            use_qk_l2norm_in_kernel=True,
        )
        candidate_out.index_copy_(1, token_indices, cand_step)

    old_state = torch.randn((row_count, heads, dim, dim),
                            device=device,
                            dtype=state_dtype)
    old_state.index_copy_(0, state_table[:, 0], initial_state)
    accepted_one = torch.ones((num_reqs,), device=device, dtype=torch.int32)
    old_out, _ = fused_sigmoid_gating_delta_rule_update(
        A_log=a_log,
        a=a,
        b=b,
        dt_bias=dt_bias,
        q=q,
        k=k,
        v=v,
        initial_state=old_state,
        inplace_final_state=True,
        cu_seqlens=query_starts,
        ssm_state_indices=state_table,
        num_accepted_tokens=accepted_one,
        use_qk_l2norm_in_kernel=True,
    )
    del old_out
    torch.xpu.synchronize(device)

    flat_state_indices = state_table.reshape(-1)
    ref_selected = reference_columns.index_select(0, flat_state_indices)
    cand_selected = candidate_state.index_select(0, flat_state_indices)
    old_selected = old_state.index_select(0, flat_state_indices)
    state_equal = torch.equal(cand_selected, ref_selected)
    output_equal = torch.equal(candidate_out, reference_out)
    old_equal = torch.equal(old_selected, ref_selected)

    result = {
        "device": str(device),
        "num_reqs": num_reqs,
        "spec_len": spec_len,
        "state_equal": bool(state_equal),
        "output_equal": bool(output_equal),
        "old_accepted_count_path_equal": bool(old_equal),
        "candidate_state_max_abs_diff": float(
            (cand_selected.float() - ref_selected.float()).abs().max().item()),
        "candidate_output_max_abs_diff": float(
            (candidate_out.float() - reference_out.float()).abs().max().item()),
        "old_state_max_abs_diff": float(
            (old_selected.float() - ref_selected.float()).abs().max().item()),
    }
    print(json.dumps(result, sort_keys=True))

    if not state_equal or not output_equal:
        raise SystemExit("exact serial spec recurrent path did not match reference")
    if old_equal:
        raise SystemExit("old accepted-count packed path unexpectedly matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
