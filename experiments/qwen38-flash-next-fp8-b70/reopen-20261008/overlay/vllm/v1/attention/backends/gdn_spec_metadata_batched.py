# SPDX-License-Identifier: Apache-2.0
"""Follow-on experiment: stage all GDN groups in one launch, keep all addresses.

Inspired by upstream #58762 and the existing multi-group ALIGN gather. Unlike
sharing captured outputs, this variant writes each builder's original buffers.
"""

from types import SimpleNamespace
import torch
from vllm.triton_utils import triton, tl
from vllm.v1.attention.backends.gdn_attn import GDNAttentionMetadataBuilder
from vllm.v1.attention.backends.gdn_spec_metadata import (
    _stage,
    eligible,
    metadata_result,
)


@triton.jit
def _all_groups(
    PTRS,
    SEQ,
    QSL,
    ACC,
    BT_STRIDE: tl.constexpr,
    BT_COL: tl.constexpr,
    SEQ_STRIDE: tl.constexpr,
    QSL_STRIDE: tl.constexpr,
    ACC_STRIDE: tl.constexpr,
    STATE_STRIDE: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
    K: tl.constexpr,
    N: tl.constexpr,
    ACTIVE: tl.constexpr,
    NUM_TOKENS: tl.constexpr,
    TILE: tl.constexpr,
):
    p = PTRS + tl.program_id(0) * 6
    bt = tl.load(p).to(tl.pointer_type(tl.int32))
    state = tl.load(p + 1).to(tl.pointer_type(tl.int32))
    mask = tl.load(p + 2).to(tl.pointer_type(tl.int1))
    tokens = tl.load(p + 3).to(tl.pointer_type(tl.int32))
    out_qsl = tl.load(p + 4).to(tl.pointer_type(tl.int32))
    out_acc = tl.load(p + 5).to(tl.pointer_type(tl.int32))
    _stage(
        bt,
        SEQ,
        QSL,
        ACC,
        state,
        mask,
        tokens,
        out_qsl,
        out_acc,
        BT_STRIDE,
        BT_COL,
        SEQ_STRIDE,
        QSL_STRIDE,
        ACC_STRIDE,
        STATE_STRIDE,
        BLOCK_SIZE,
        K,
        N,
        ACTIVE,
        NUM_TOKENS,
        TILE,
    )


class Plan:
    def __init__(self, builders, tables):
        self.builders = builders
        self.tables = tables
        b = builders[0]
        bt = tables[0]
        self.geometry = (
            b.num_spec,
            b.kv_cache_spec.block_size,
            bt.stride(),
            b.spec_state_indices_tensor.stride(0),
        )
        for b, bt in zip(builders, tables):
            assert self.geometry == (
                b.num_spec,
                b.kv_cache_spec.block_size,
                bt.stride(),
                b.spec_state_indices_tensor.stride(0),
            )
        ptrs = [
            [
                bt.data_ptr(),
                b.spec_state_indices_tensor.data_ptr(),
                b.spec_sequence_masks.data_ptr(),
                b.spec_token_indx.data_ptr(),
                b.spec_query_start_loc.data_ptr(),
                b.num_accepted_tokens.data_ptr(),
            ]
            for b, bt in zip(builders, tables)
        ]
        self.ptrs = torch.tensor(ptrs, dtype=torch.uint64, device=tables[0].device)

    def stage(self, m, acc, active):
        depth, block_size, strides, state_stride = self.geometry
        n = m.num_reqs
        k = depth + 1
        nt = active * k
        _all_groups[(len(self.builders),)](
            self.ptrs,
            m.seq_lens,
            m.query_start_loc,
            acc,
            strides[0],
            strides[1],
            m.seq_lens.stride(0),
            m.query_start_loc.stride(0),
            acc.stride(0),
            state_stride,
            block_size,
            k,
            n,
            active,
            nt,
            triton.next_power_of_2(max(n * k, n + 1)),
            num_warps=4,
        )
        return {id(b): metadata_result(b, m, active) for b in self.builders}


def prepare(kwargs):
    if kwargs.get("for_cudagraph_capture"):
        return {}
    if kwargs["seq_lens"].device.type != "xpu":
        return {}
    extra = kwargs.get("model_specific_attn_metadata")
    if extra is None:
        return {}
    # This caller guarantees identical batch inputs for all GDN groups.
    from vllm.v1.worker.gpu.model_states.mamba_hybrid import MambaHybridAttnMetadata

    if type(extra) is not MambaHybridAttnMetadata:
        return {}
    acc = getattr(extra, "num_accepted_tokens", None)
    d = getattr(extra, "num_decode_draft_tokens_cpu", None)
    if acc is None or d is None:
        return {}
    builders = []
    tables = []
    for i, groups in enumerate(kwargs["attn_groups"]):
        for group in groups:
            b = group.get_metadata_builder(kwargs.get("ubatch_idx", 0))
            if type(b) is GDNAttentionMetadataBuilder:
                builders.append(b)
                tables.append(kwargs["block_tables"][i])
    if not builders:
        return {}
    # Cached device pointer tables must not survive a discarded sleep pool.
    # Keep sleep-enabled configurations on the per-builder implementation.
    model_config = getattr(builders[0].vllm_config, "model_config", None)
    if getattr(model_config, "enable_sleep_mode", False):
        return {}
    m = SimpleNamespace(
        num_reqs=kwargs["num_reqs"],
        num_actual_tokens=kwargs["num_tokens"],
        query_start_loc_cpu=kwargs["query_start_loc_cpu"],
        query_start_loc=kwargs["query_start_loc_gpu"],
        seq_lens=kwargs["seq_lens"],
    )
    active = eligible(builders[0], m, d)
    if active is None:
        return {}
    b0 = builders[0]
    bt0 = tables[0]
    geom = (
        b0.num_spec,
        b0.kv_cache_spec.block_size,
        bt0.stride(),
        b0.decode_cudagraph_max_bs,
        b0.spec_state_indices_tensor.stride(0),
    )
    for b, bt in zip(builders, tables):
        if (
            not b.use_spec_decode
            or not b.use_full_cuda_graph
            or b.vllm_config.cache_config.mamba_cache_mode != "align"
            or bt.dtype != torch.int32
            or b.kv_cache_spec.num_speculative_blocks < b.num_spec
            or (
                b.num_spec,
                b.kv_cache_spec.block_size,
                bt.stride(),
                b.decode_cudagraph_max_bs,
                b.spec_state_indices_tensor.stride(0),
            )
            != geom
        ):
            return {}
    pointers = tuple(
        (
            id(b),
            bt.data_ptr(),
            b.spec_state_indices_tensor.data_ptr(),
            b.spec_sequence_masks.data_ptr(),
            b.spec_token_indx.data_ptr(),
            b.spec_query_start_loc.data_ptr(),
            b.num_accepted_tokens.data_ptr(),
        )
        for b, bt in zip(builders, tables)
    )
    key = (geom, pointers)
    cached = getattr(b0, "_gdn_uniform_metadata_plan", None)
    if cached is None or cached[0] != key:
        # Keep the plan with its builders, not in a process-global model cache.
        plan = Plan(builders, tables)
        b0._gdn_uniform_metadata_plan = (key, plan)
    else:
        plan = cached[1]
    return plan.stage(m, acc, active)
