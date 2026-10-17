"""Decode-identical MTP verifier attention on one B70 (research overlay).

Enabled only with B70_FA_VERIFY_ROWS=1. The XPU paged flash-attention kernel
(FA2) computes row r of a causal multi-query call differently from the same
query computed alone once the key length passes about 1,980 tokens (census
qwen38-fa-verify-row-census.py, served cache layout): a depth-K verify step then
drifts from no-MTP decode by FP16 ULPs and can flip a near-tie. For one-request
calls with 2..B70_FA_VERIFY_ROWS_MAX_Q query rows and max_seqlen_k above
B70_FA_VERIFY_ROWS_MIN_K (default 1536), this wraps flash_attn_varlen_func and
issues one single-query call per row with exactly the arguments a decode step
uses (seqused_k and max_seqlen_k shortened per row, same caches, block table and
descales). Prefill chunks, shorter keys and batches pass through unchanged. No
host synchronisation is added.

0.2.0 (2026-10-17), B70_FA_VERIFY_ROWS_ONE_LAUNCH=1: the same rows in one launch
of the split-K decode kernel, as one-token pseudo-sequences (row r keeps its own
seqused_k), with the number of key splits passed explicitly. A row's arithmetic
depends only on its own key count and that split count, and a single-query call
picks the split count from its max_seqlen_k (flash_api.cpp get_num_splits, batch
of one). So when all rows' single-query calls would pick the same count (computed
here on the host from max_seqlen_k - back, the inputs the per-row calls use), the
one launch is the per-row calls bit for bit; otherwise (a split-count boundary,
rare) the per-row calls are issued. The kernel library's own spec-decode fast
path is not used: it picks the count for a batch of q_len rows, which differs from
a lone row's between about 3K and 24.5K keys. One launch reads each key tile
while the other rows' reads of it are still in the card's L2: about 1.8x one
decode call instead of 6x (scripts/bench-decode-attn.py, 2026-10-17).
"""
import os


def _lone_splits(max_k, block, cores, heads_q, heads_kv):
    """flash_api.cpp get_num_splits for one sequence (batch_size 1), vllm-xpu-kernels 0.1.14.1."""
    kv_tile, sg, cap = (16, 1, 16) if block == 16 else (32, 2, 32) if block == 32 else (64, 4, 64)
    tiles = (max_k + kv_tile - 1) // kv_tile
    if tiles < 16:
        return 1
    slots = cores * 4 // sg
    wgs = heads_kv
    if wgs >= slots and tiles < 64:
        return 1
    s = max(max(1, (4 * slots + wgs - 1) // wgs), max(1, tiles // 12))
    s = min(s, max(2, 128 * cores // max(1, heads_q)))
    return max(1, min(s, max(1, tiles // 4), 32, cap))


def register():
    if os.environ.get('B70_FA_VERIFY_ROWS') != '1':
        return
    import torch
    from vllm.logger import init_logger
    from vllm.v1.attention.backends import flash_attn as fa

    if getattr(fa, '_b70_fa_verify_rows', False):
        return
    logger = init_logger('b70_fa_verify_rows')
    max_q = int(os.environ.get('B70_FA_VERIFY_ROWS_MAX_Q', '8'))
    min_k = int(os.environ.get('B70_FA_VERIFY_ROWS_MIN_K', '1536'))
    one_launch = os.environ.get('B70_FA_VERIFY_ROWS_ONE_LAUNCH') == '1'
    original = fa.flash_attn_varlen_func
    single_cu = {}
    spec = {}
    cores = {}
    state = {'logged': False, 'one': 0, 'rows': 0}
    if one_launch:
        from vllm_xpu_kernels import flash_attn_interface as fai
        kernels_fa = fai.flash_attn_varlen_func

    def xe_cores(dev):
        # get_num_splits counts gpu_slices x gpu_subslices_per_slice, i.e. all subslices (32 on a B70). torch exposes
        # that total as gpu_subslice_count; the kernel interface's own helper looks for the per-slice fields, which
        # torch 2026 does not have, and falls back to 20 (census 2026-10-17). For one sequence with 2 key/value heads
        # the split count does not depend on the core count at any key length up to 262,144, but use the right one.
        n = cores.get(dev)
        if n is None:
            props = torch.xpu.get_device_properties(dev)
            n = getattr(props, 'gpu_subslice_count', None)
            n = int(n) if n else fai._infer_num_xe_cores(dev)
            cores[dev] = n
            logger.warning('b70_fa_verify_rows: one launch per verify call, %d Xe cores on %s', n, dev)
        return n

    def rows_call(**kw):
        q, out, n = kw['q'], kw['out'], kw['q'].shape[0]
        dev = q.device
        cu = single_cu.get(dev)
        if cu is None:
            cu = single_cu[dev] = torch.tensor([0, 1], dtype=kw['cu_seqlens_q'].dtype, device=dev)
        for r in range(n):
            back = n - 1 - r
            row = dict(kw)
            row.update(q=q[r:r + 1], out=out[r:r + 1], cu_seqlens_q=cu, max_seqlen_q=1,
                       seqused_k=kw['seqused_k'] - back, max_seqlen_k=kw['max_seqlen_k'] - back)
            original(**row)
        return out

    def one_launch_call(**kw):
        q, k, out, n = kw['q'], kw['k'], kw['out'], kw['q'].shape[0]
        dev = q.device
        counts = {_lone_splits(kw['max_seqlen_k'] - (n - 1 - r), k.shape[1], xe_cores(dev), q.shape[1], k.shape[2])
                  for r in range(n)}
        if len(counts) != 1:
            state['rows'] += 1
            return rows_call(**kw)
        state['one'] += 1
        c = spec.get((dev, n))
        if c is None:
            c = spec[(dev, n)] = (torch.arange(n + 1, dtype=kw['cu_seqlens_q'].dtype, device=dev),
                                  (n - 1 - torch.arange(n, device=dev)).to(kw['seqused_k'].dtype))
        cu, back = c
        window = kw.get('window_size')
        # the arguments vllm._xpu_ops.flash_attn_varlen_func passes on, plus the split count
        kernels_fa(out=out, q=q, k=k, v=kw['v'], cu_seqlens_q=cu, cu_seqlens_k=kw.get('cu_seqlens_k'),
                   seqused_k=kw['seqused_k'] - back, max_seqlen_q=1, max_seqlen_k=kw['max_seqlen_k'],
                   softmax_scale=kw.get('softmax_scale'), causal=kw.get('causal', False),
                   block_table=kw['block_table'].repeat_interleave(n, dim=0), s_aux=kw.get('s_aux'),
                   window_size=(-1, -1) if window is None else (window[0], window[1]),
                   return_softmax_lse=kw.get('return_softmax_lse', False), q_descale=kw.get('q_descale'),
                   k_descale=kw.get('k_descale'), v_descale=kw.get('v_descale'), num_splits_kv=counts.pop())
        if (state['one'] + state['rows']) % 50000 == 0:
            logger.warning('b70_fa_verify_rows: %d one-launch verify calls, %d per-row fallbacks',
                           state['one'], state['rows'])
        return out

    def wrapped(*args, **kw):
        q = kw.get('q')
        if (not args and isinstance(q, torch.Tensor) and 2 <= q.shape[0] <= max_q
                and kw.get('max_seqlen_q') == q.shape[0] and isinstance(kw.get('max_seqlen_k'), int)
                and kw['max_seqlen_k'] > min_k and kw.get('out') is not None
                and kw['cu_seqlens_q'].shape[0] == 2 and kw['seqused_k'].shape[0] == 1
                and kw.get('causal') is True and kw.get('dynamic_causal') is None
                and kw.get('mask_mod') is None and kw.get('s_aux') is None and kw.get('alibi_slopes') is None
                and kw.get('scheduler_metadata') is None):
            if not state['logged']:
                logger.warning('b70_fa_verify_rows: verifier attention rows computed as single-query decode calls '
                               '(max_q %d, key length > %d, %s)', max_q, min_k,
                               'one launch' if one_launch else 'one call per row')
                state['logged'] = True
            if one_launch and kw.get('block_table') is not None:
                return one_launch_call(**kw)
            return rows_call(**kw)
        return original(*args, **kw)

    fa.flash_attn_varlen_func = wrapped
    fa._b70_fa_verify_rows = True
    logger.warning('b70_fa_verify_rows: enabled%s', ' (one launch per verify call)' if one_launch else '')
