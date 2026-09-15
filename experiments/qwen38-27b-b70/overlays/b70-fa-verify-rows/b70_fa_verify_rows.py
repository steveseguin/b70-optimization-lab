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
"""
import os


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
    original = fa.flash_attn_varlen_func
    single_cu = {}
    state = {'logged': False}

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
                               '(max_q %d, key length > %d)', max_q, min_k)
                state['logged'] = True
            return rows_call(**kw)
        return original(*args, **kw)

    fa.flash_attn_varlen_func = wrapped
    fa._b70_fa_verify_rows = True
    logger.warning('b70_fa_verify_rows: enabled')
