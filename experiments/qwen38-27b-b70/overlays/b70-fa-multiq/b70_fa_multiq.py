"""One-pass verifier attention for MTP on one B70 (research overlay, needs the r312 kernel library). B70_FA_MULTIQ=1.

Supersedes b70_fa_verify_rows: for a one-request verify call with 2..B70_FA_MULTIQ_MAX_Q query rows over more than
B70_FA_MULTIQ_MIN_K keys, the rows are computed by `_vllm_fa2_C.paged_decode_multiq` in one pass over the cache (K and
V tiles loaded once, output columns split into B70_FA_MULTIQ_VTILE-wide slices), which the census showed bit-identical
to the single-query decode calls the verify-rows overlay issues. When the rows do not all end in the same 64-key tile
(the op's precondition, about 8% of steps), the per-row calls are issued instead, so every row is still computed by
the decode arithmetic. Prefill chunks, short keys and batches pass through unchanged. The precondition reads the
request's key length from seqused_k (one small device-to-host read per call; the op itself reads the same value to
check its precondition, so the queue is drained anyway). Version 1 used max_seqlen_k, a host integer that is NOT
always the key length: on 2026-09-18 (lc-3, long-corpus prose-2048 warmup) the op refused a call the host check had
let through, and the engine died. B70_FA_MULTIQ_DEBUG=1 logs every mismatch between the two.
"""
import os


def register():
    if os.environ.get('B70_FA_MULTIQ') != '1':
        return
    import torch
    from vllm.logger import init_logger
    from vllm.v1.attention.backends import flash_attn as fa

    if getattr(fa, '_b70_fa_multiq', False):
        return
    logger = init_logger('b70_fa_multiq')
    import vllm_xpu_kernels._xpu_C  # noqa: F401
    if not hasattr(torch.ops._xpu_C, 'paged_decode_multiq'):
        raise RuntimeError('b70_fa_multiq: the kernel library has no paged_decode_multiq (needs the r312 build)')
    max_q = int(os.environ.get('B70_FA_MULTIQ_MAX_Q', '8'))
    min_k = int(os.environ.get('B70_FA_MULTIQ_MIN_K', '1536'))
    v_tile = int(os.environ.get('B70_FA_MULTIQ_VTILE', '64'))
    kv_tile = 64
    original = fa.flash_attn_varlen_func
    single_cu = {}
    state = {'logged': False, 'multiq': 0, 'rows': 0, 'mismatch': 0}
    debug = os.environ.get('B70_FA_MULTIQ_DEBUG', '0') == '1'

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

    def multiq_call(**kw):
        q, out, n = kw['q'], kw['out'], kw['q'].shape[0]
        torch.ops._xpu_C.paged_decode_multiq(
            q, kw['k'], kw['v'], out, kw['cu_seqlens_q'], kw['seqused_k'], kw['block_table'], n, kw['max_seqlen_k'],
            kw.get('k_descale'), kw.get('v_descale'), kw['softmax_scale'], None, v_tile)
        return out

    def wrapped(*args, **kw):
        q = kw.get('q')
        if (not args and isinstance(q, torch.Tensor) and 2 <= q.shape[0] <= max_q
                and kw.get('max_seqlen_q') == q.shape[0] and isinstance(kw.get('max_seqlen_k'), int)
                and kw['max_seqlen_k'] > min_k and kw.get('out') is not None
                and kw['cu_seqlens_q'].shape[0] == 2 and kw['seqused_k'].shape[0] == 1
                and kw.get('block_table') is not None
                and kw.get('causal') is True and kw.get('dynamic_causal') is None
                and kw.get('mask_mod') is None and kw.get('s_aux') is None and kw.get('alibi_slopes') is None
                and kw.get('scheduler_metadata') is None):
            n = q.shape[0]
            if not state['logged']:
                logger.warning('b70_fa_multiq: verifier attention in one pass (paged_decode_multiq, v_tile %d, max_q %d, key length > %d); '
                               'per-row decode calls when the rows straddle a %d-key tile', v_tile, max_q, min_k, kv_tile)
                state['logged'] = True
            key_len = int(kw['seqused_k'][0])
            if key_len != kw['max_seqlen_k']:
                state['mismatch'] += 1
                if debug or state['mismatch'] == 1:
                    logger.warning('b70_fa_multiq: seqused_k[0]=%d differs from max_seqlen_k=%d (n=%d); the precondition uses seqused_k',
                                   key_len, kw['max_seqlen_k'], n)
            if (key_len - 1) % kv_tile >= n - 1:
                state['multiq'] += 1
                out = multiq_call(**kw)
            else:
                state['rows'] += 1
                out = rows_call(**kw)
            total = state['multiq'] + state['rows']
            if total % 20000 == 0:
                logger.warning('b70_fa_multiq: %d one-pass calls, %d per-row fallbacks, %d max_seqlen_k mismatches',
                               state['multiq'], state['rows'], state['mismatch'])
            return out
        return original(*args, **kw)

    fa.flash_attn_varlen_func = wrapped
    fa._b70_fa_multiq = True
