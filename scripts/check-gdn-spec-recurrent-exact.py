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

    # Accepted-prefix tape contract prototype:
    # prefix 0 is the base state before verifier spec rows; prefix i is the
    # exact state after accepting the first i draft/verifier rows. A future
    # native implementation should publish these prefix rows and commit one
    # selected prefix row per request with a GPU-side mask/gather, without
    # Python per-layer loops in the decode hot path.
    prefix_rows = torch.arange(
        1,
        1 + num_reqs * (spec_len + 1),
        device=device,
        dtype=torch.int64,
    ).reshape(num_reqs, spec_len + 1)
    commit_rows = torch.arange(
        1 + num_reqs * (spec_len + 1),
        1 + num_reqs * (spec_len + 2),
        device=device,
        dtype=torch.int64,
    )
    prefix_row_count = 1 + num_reqs * (spec_len + 2)

    ssm_prefix_table = torch.zeros((prefix_row_count, heads, dim, dim),
                                   device=device,
                                   dtype=state_dtype)
    ssm_prefix_table.index_copy_(0, prefix_rows[:, 0], initial_state)
    for pos in range(spec_len):
        ssm_prefix_table.index_copy_(
            0,
            prefix_rows[:, pos + 1],
            reference_columns.index_select(0, state_table[:, pos]),
        )

    conv_dim = heads * dim
    conv_len = 4
    base_conv = torch.randn((num_reqs, conv_dim, conv_len),
                            device=device,
                            dtype=state_dtype)
    raw_conv_tokens = torch.randn((total_tokens, conv_dim),
                                  device=device,
                                  dtype=state_dtype)
    conv_prefix_table = torch.zeros((prefix_row_count, conv_dim, conv_len),
                                    device=device,
                                    dtype=state_dtype)
    conv_prefix_table.index_copy_(0, prefix_rows[:, 0], base_conv)
    for req_idx in range(num_reqs):
        start = int(query_offsets[req_idx].item())
        base_history = base_conv[req_idx].transpose(0, 1).contiguous()
        for prefix_len in range(1, spec_len + 1):
            accepted_tokens = raw_conv_tokens[start:start + prefix_len]
            history = torch.cat((base_history, accepted_tokens), dim=0)
            window = history[-conv_len:].transpose(0, 1).contiguous()
            conv_prefix_table[prefix_rows[req_idx, prefix_len]] = window

    def commit_prefix_rows(
        state: torch.Tensor,
        accepted_prefix: torch.Tensor,
    ) -> torch.Tensor:
        committed = state.clone()
        source_rows = prefix_rows.gather(
            1, accepted_prefix.to(torch.long).unsqueeze(1)).squeeze(1)
        committed.index_copy_(
            0,
            commit_rows,
            committed.index_select(0, source_rows).clone(),
        )
        return committed

    placeholder_token_id = -1

    def visible_count(row: torch.Tensor) -> int:
        return int((row != placeholder_token_id).sum().item())

    def commit_prefix_from_visible_row(
        row: torch.Tensor,
        scheduled_spec_ids: torch.Tensor,
        *,
        draft_only: bool = False,
        suppressed_target_owned_tail: bool = False,
    ) -> int:
        """Map scheduler-visible speculative output to draft prefix length.

        The sampler row may include a target-owned replacement on partial
        reject, or a target-owned bonus token on full accept. Neither token is
        part of the accepted draft prefix that a native GDN/DeltaNet state
        commit may select. This mirrors the endpoint contract while staying
        small and deterministic enough for a synthetic XPU guard.
        """
        count = visible_count(row)
        num_draft_tokens = int(scheduled_spec_ids.numel())
        if count <= 0:
            return 0

        row_valid = row[:count]
        if draft_only:
            return min(count, num_draft_tokens)

        # Some scheduler paths emit accepted scheduled tokens shifted by one
        # position. They are still draft-owned rows, not target replacement
        # rows, so commit exactly the visible accepted prefix.
        if (
            num_draft_tokens > 1
            and count == num_draft_tokens - 1
            and torch.equal(row_valid, scheduled_spec_ids[1:1 + count])
        ):
            return count

        # A full accept row is k accepted draft tokens plus a target-owned
        # bonus. If the bonus is suppressed for recompute, the draft prefix is
        # still k.
        if count == num_draft_tokens + 1:
            return num_draft_tokens

        # If a target-owned replacement/bonus was already marked for
        # suppression by the sampler, the prefix is the row without that tail.
        if suppressed_target_owned_tail:
            return min(max(count - 1, 0), num_draft_tokens)

        # Normal partial reject row: p accepted draft tokens plus one
        # target-owned replacement. The replacement cannot be committed from
        # verifier draft-prefix state.
        if count <= num_draft_tokens:
            return max(count - 1, 0)

        raise ValueError(
            f"invalid speculative row count={count} k={num_draft_tokens}")

    def make_row(tokens: list[int]) -> torch.Tensor:
        row = torch.full((spec_len + 1,),
                         placeholder_token_id,
                         device=device,
                         dtype=torch.int64)
        if tokens:
            row[:len(tokens)] = torch.tensor(tokens,
                                             device=device,
                                             dtype=torch.int64)
        return row

    ssm_commit_equal = True
    conv_commit_equal = True
    ssm_commit_max_abs_diff = 0.0
    conv_commit_max_abs_diff = 0.0
    accepted_cases: list[torch.Tensor] = [
        torch.full((num_reqs,), i, device=device, dtype=torch.int64)
        for i in range(spec_len + 1)
    ]
    accepted_cases.append(
        torch.arange(num_reqs, device=device, dtype=torch.int64)
        % (spec_len + 1))
    scheduled_base = torch.arange(1000,
                                  1000 + spec_len,
                                  device=device,
                                  dtype=torch.int64)
    scheduled_tokens = [1000 + i for i in range(spec_len)]
    scheduler_endpoint_cases = [
        {
            "name": "full_reject",
            "row": make_row([]),
            "expected": 0,
        },
        {
            "name": "partial_reject_at_0_replacement_only",
            "row": make_row([9000]),
            "expected": 0,
        },
        {
            "name": "partial_reject_after_1",
            "row": make_row(scheduled_tokens[:1] + [9001]),
            "expected": min(1, spec_len),
        },
        {
            "name": "partial_reject_after_2",
            "row": make_row(scheduled_tokens[:min(2, spec_len)] + [9002]),
            "expected": min(2, spec_len),
        },
        {
            "name": "full_accept_with_bonus",
            "row": make_row(scheduled_tokens + [9100]),
            "expected": spec_len,
        },
        {
            "name": "draft_only_two",
            "row": make_row(scheduled_tokens[:min(2, spec_len)]),
            "expected": min(2, spec_len),
            "draft_only": True,
        },
        {
            "name": "shifted_full_accept",
            "row": make_row(scheduled_tokens[1:]),
            "expected": max(spec_len - 1, 0),
        },
        {
            "name": "suppressed_bonus_tail",
            "row": make_row(scheduled_tokens + [9101]),
            "expected": spec_len,
            "suppressed_target_owned_tail": True,
        },
        {
            "name": "suppressed_replacement_after_2",
            "row": make_row(scheduled_tokens[:min(2, spec_len)] + [9003]),
            "expected": min(2, spec_len),
            "suppressed_target_owned_tail": True,
        },
    ]
    scheduler_case_failures: list[dict[str, object]] = []
    scheduler_case_names: list[str] = []
    for endpoint_case in scheduler_endpoint_cases:
        expected_prefix = min(int(endpoint_case["expected"]), spec_len)
        observed_prefix = commit_prefix_from_visible_row(
            endpoint_case["row"],
            scheduled_base,
            draft_only=bool(endpoint_case.get("draft_only", False)),
            suppressed_target_owned_tail=bool(
                endpoint_case.get("suppressed_target_owned_tail", False)),
        )
        scheduler_case_names.append(str(endpoint_case["name"]))
        if observed_prefix != expected_prefix:
            scheduler_case_failures.append({
                "name": str(endpoint_case["name"]),
                "observed": int(observed_prefix),
                "expected": int(expected_prefix),
                "row": [
                    int(token)
                    for token in endpoint_case["row"].detach().cpu().tolist()
                ],
            })
        accepted_cases.append(
            torch.full((num_reqs,),
                       observed_prefix,
                       device=device,
                       dtype=torch.int64))
    for accepted_prefix in accepted_cases:
        committed_ssm = commit_prefix_rows(ssm_prefix_table, accepted_prefix)
        committed_conv = commit_prefix_rows(conv_prefix_table, accepted_prefix)
        expected_ssm_rows = prefix_rows.gather(
            1, accepted_prefix.unsqueeze(1)).squeeze(1)
        expected_ssm = ssm_prefix_table.index_select(0, expected_ssm_rows)
        expected_conv = conv_prefix_table.index_select(0, expected_ssm_rows)
        observed_ssm = committed_ssm.index_select(0, commit_rows)
        observed_conv = committed_conv.index_select(0, commit_rows)
        ssm_case_equal = torch.equal(observed_ssm, expected_ssm)
        conv_case_equal = torch.equal(observed_conv, expected_conv)
        ssm_commit_equal = ssm_commit_equal and bool(ssm_case_equal)
        conv_commit_equal = conv_commit_equal and bool(conv_case_equal)
        ssm_commit_max_abs_diff = max(
            ssm_commit_max_abs_diff,
            float((observed_ssm.float() - expected_ssm.float()).abs().max()
                  .item()),
        )
        conv_commit_max_abs_diff = max(
            conv_commit_max_abs_diff,
            float((observed_conv.float() - expected_conv.float()).abs().max()
                  .item()),
        )

    result = {
        "device": str(device),
        "num_reqs": num_reqs,
        "spec_len": spec_len,
        "state_equal": bool(state_equal),
        "output_equal": bool(output_equal),
        "old_accepted_count_path_equal": bool(old_equal),
        "accepted_prefix_commit_ssm_equal": bool(ssm_commit_equal),
        "accepted_prefix_commit_conv_equal": bool(conv_commit_equal),
        "scheduler_endpoint_cases_equal": not scheduler_case_failures,
        "scheduler_endpoint_case_count": len(scheduler_endpoint_cases),
        "scheduler_endpoint_case_names": scheduler_case_names,
        "scheduler_endpoint_case_failures": scheduler_case_failures,
        "candidate_state_max_abs_diff": float(
            (cand_selected.float() - ref_selected.float()).abs().max().item()),
        "candidate_output_max_abs_diff": float(
            (candidate_out.float() - reference_out.float()).abs().max().item()),
        "old_state_max_abs_diff": float(
            (old_selected.float() - ref_selected.float()).abs().max().item()),
        "accepted_prefix_commit_ssm_max_abs_diff":
            float(ssm_commit_max_abs_diff),
        "accepted_prefix_commit_conv_max_abs_diff":
            float(conv_commit_max_abs_diff),
    }
    print(json.dumps(result, sort_keys=True))

    if not state_equal or not output_equal:
        raise SystemExit("exact serial spec recurrent path did not match reference")
    if old_equal:
        raise SystemExit("old accepted-count packed path unexpectedly matched")
    if scheduler_case_failures:
        raise SystemExit("scheduler endpoint row-to-prefix contract failed")
    if not ssm_commit_equal or not conv_commit_equal:
        raise SystemExit("accepted-prefix commit prototype did not match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
