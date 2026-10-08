# SPDX-License-Identifier: Apache-2.0
"""Experimental uniform-spec GDN metadata staging, preserving builder buffers.

ALIGN gather idea follows upstream vLLM PR 38020. This fuses the entire
uniform speculative staging path, with per-cache-group block tables retained.
Mixed/prefill/nonuniform batches use the installed implementation unchanged.
"""

import numpy as np
from vllm.triton_utils import triton, tl


@triton.jit
def _stage(
    BT,
    SEQ,
    QSL,
    ACC,
    STATE,
    MASK,
    TOKENS,
    OUT_QSL,
    OUT_ACC,
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
    x = tl.arange(0, TILE)
    row = x // K
    col = x % K
    seq = tl.load(SEQ + row * SEQ_STRIDE, mask=row < ACTIVE, other=0)
    start = tl.maximum((seq - 1) // BLOCK_SIZE, 0)
    # Valid inputs have K reserved state slots, just as torch.gather requires.
    state = tl.load(
        BT + row * BT_STRIDE + (start + col) * BT_COL, mask=row < ACTIVE, other=0
    )
    tl.store(STATE + row * STATE_STRIDE + col, state, mask=row < N)
    tl.store(TOKENS + x, x, mask=x < NUM_TOKENS)
    tl.store(MASK + x, x < ACTIVE, mask=x < N)
    acc = tl.load(ACC + x * ACC_STRIDE, mask=x < ACTIVE, other=1)
    tl.store(OUT_ACC + x, acc, mask=x < N)
    q = tl.load(QSL + tl.minimum(x, ACTIVE) * QSL_STRIDE, mask=x <= N, other=0)
    tl.store(OUT_QSL + x, q, mask=x <= N)


def eligible(b, m, d):
    if (
        not b.use_spec_decode
        or not b.use_full_cuda_graph
        or d is None
        or b.vllm_config.cache_config.mamba_cache_mode != "align"
    ):
        return None
    n = m.num_reqs
    k = b.num_spec + 1
    if (
        n > b.decode_cudagraph_max_bs
        or b.kv_cache_spec.num_speculative_blocks < b.num_spec
    ):
        return None
    dc = d.numpy()
    q = m.query_start_loc_cpu.numpy()
    if len(dc) != n or len(q) != n + 1:
        return None
    active = int(np.count_nonzero(dc >= 0))
    if (
        active == 0
        or active * k > b.decode_cudagraph_max_bs
        or not np.all(dc[:active] == b.num_spec)
        or not np.all(dc[active:] < 0)
        or not np.all(np.diff(q[: active + 1]) == k)
        or not np.all(q[active:] == active * k)
        or q[0] != 0
    ):
        return None
    return active


def try_build_uniform_spec_metadata(
    b, m, num_accepted_tokens, num_decode_draft_tokens_cpu
):
    active = eligible(b, m, num_decode_draft_tokens_cpu)
    if active is None:
        return None
    assert num_accepted_tokens is not None
    n = m.num_reqs
    k = b.num_spec + 1
    nt = active * k
    _stage[(1,)](
        m.block_table_tensor,
        m.seq_lens,
        m.query_start_loc,
        num_accepted_tokens,
        b.spec_state_indices_tensor,
        b.spec_sequence_masks,
        b.spec_token_indx,
        b.spec_query_start_loc,
        b.num_accepted_tokens,
        m.block_table_tensor.stride(0),
        m.block_table_tensor.stride(1),
        m.seq_lens.stride(0),
        m.query_start_loc.stride(0),
        num_accepted_tokens.stride(0),
        b.spec_state_indices_tensor.stride(0),
        b.kv_cache_spec.block_size,
        k,
        n,
        active,
        nt,
        triton.next_power_of_2(max(n * k, n + 1)),
        num_warps=4,
    )
    return metadata_result(b, m, active)


def metadata_result(b, m, active):
    from vllm.v1.attention.backends.gdn_attn import GDNAttentionMetadata

    n = m.num_reqs
    nt = active * (b.num_spec + 1)
    return GDNAttentionMetadata(
        num_prefills=0,
        num_prefill_tokens=0,
        num_decodes=0,
        num_decode_tokens=0,
        num_spec_decodes=active,
        num_spec_decode_tokens=nt,
        num_actual_tokens=m.num_actual_tokens,
        spec_query_start_loc=b.spec_query_start_loc[: n + 1],
        spec_state_indices_tensor=b.spec_state_indices_tensor[:n],
        spec_sequence_masks=b.spec_sequence_masks[:n],
        spec_token_indx=b.spec_token_indx[:nt],
        non_spec_token_indx=b.non_spec_token_indx[:0],
        num_accepted_tokens=b.num_accepted_tokens[:n],
    )
