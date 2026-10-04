"""One attention decode call per sequence when contexts are long (research overlay). Enabled with B70_FA_DECODE_PER_SEQ=1.

Why: the XPU paged flash-attention decode kernel (one query per sequence) is bitwise batch-invariant for short keys
(40-229 tokens, census R151) but not for long ones. Census 2026-10-04
(scripts/qwen38-fp8-fa-decode-longkey-batch-census.py, data/2026-10-04-fp8-multiuser/census/): with keys of 1.6K to
8.2K tokens a sequence's output moves by one FP16 ulp once four or more sequences share the call, and a lone
sequence's output also changes when the call is told a larger `max_seqlen_k` than its own length. Sixteen users with
long prompts hit both, and an exact logit tie can then fall the other way.

It also covers a speculative verify step for several requests (a few query rows per sequence, at most
B70_FA_DECODE_PER_SEQ_MAX_Q, default 8): each sequence is handed, alone, to whatever the module's attention function
currently is, so the verify-rows overlay then treats it exactly as it treats a lone user's verify step.

What this does: for a multi-sequence decode call (one query per sequence, `max_seqlen_q == 1`) whose longest key
exceeds B70_FA_DECODE_PER_SEQ_MIN_K (default 229, the longest length the census proved invariant), it issues one
call per sequence with exactly the arguments a lone request's decode step uses: that sequence's query, its row of
the block table, its own key length as both `seqused_k` and `max_seqlen_k`. Shorter contexts, prefill chunks and
single-sequence calls pass through unchanged. No arithmetic is changed; the per-sequence lengths are read back to the
host once per call.
"""
import os


def register():
    if os.environ.get('B70_FA_DECODE_PER_SEQ', '').strip() != '1':
        return
    import torch
    from vllm.logger import init_logger
    from vllm.v1.attention.backends import flash_attn as fa

    if getattr(fa, '_b70_fa_decode_per_seq', False):
        return
    logger = init_logger('b70_fa_decode_per_seq')
    min_k = int(os.environ.get('B70_FA_DECODE_PER_SEQ_MIN_K', '229'))
    original = fa.flash_attn_varlen_func
    single_cu = {}
    multi_cu = {}
    max_q = int(os.environ.get('B70_FA_DECODE_PER_SEQ_MAX_Q', '8'))
    state = {'logged': False, 'calls': 0}

    def wrapped(*args, **kw):
        q = kw.get('q')
        cu = kw.get('cu_seqlens_q')
        used = kw.get('seqused_k')
        table = kw.get('block_table')
        if (not args and isinstance(q, torch.Tensor) and q.shape[0] >= 2
                and isinstance(kw.get('max_seqlen_q'), int) and 1 <= kw['max_seqlen_q'] <= max_q
                and isinstance(cu, torch.Tensor) and cu.shape[0] >= 3
                and isinstance(used, torch.Tensor) and used.shape[0] == cu.shape[0] - 1
                and isinstance(table, torch.Tensor) and table.shape[0] == cu.shape[0] - 1
                and isinstance(kw.get('max_seqlen_k'), int) and kw['max_seqlen_k'] > min_k
                and kw.get('out') is not None and kw.get('causal') is True
                and kw.get('dynamic_causal') is None and kw.get('mask_mod') is None and kw.get('s_aux') is None
                and kw.get('alibi_slopes') is None and kw.get('scheduler_metadata') is None):
            out = kw['out']
            dev = q.device
            one = single_cu.get(dev)
            if one is None:
                one = single_cu[dev] = torch.tensor([0, 1], dtype=cu.dtype, device=dev)
            lengths = used.tolist()
            if kw['max_seqlen_q'] == 1:
                for i, length in enumerate(lengths):
                    row = dict(kw)
                    row.update(q=q[i:i + 1], out=out[i:i + 1], cu_seqlens_q=one, seqused_k=used[i:i + 1],
                               max_seqlen_k=int(length), block_table=table[i:i + 1])
                    original(**row)
            else:
                # Several query rows per sequence (a speculative verify step for several requests). Hand each
                # sequence to the module's CURRENT function, so the verify-rows overlay, whichever order the two
                # were installed in, sees the same one-request call it sees for a lone user.
                bounds = cu.tolist()
                for i, length in enumerate(lengths):
                    start, end = bounds[i], bounds[i + 1]
                    if end <= start:
                        continue
                    key = (dev, end - start)
                    cu_i = multi_cu.get(key)
                    if cu_i is None:
                        cu_i = multi_cu[key] = torch.tensor([0, end - start], dtype=cu.dtype, device=dev)
                    row = dict(kw)
                    row.update(q=q[start:end], out=out[start:end], cu_seqlens_q=cu_i, max_seqlen_q=end - start,
                               seqused_k=used[i:i + 1], max_seqlen_k=int(length), block_table=table[i:i + 1])
                    fa.flash_attn_varlen_func(**row)
            state['calls'] += 1
            if not state['logged']:
                logger.warning('b70_fa_decode_per_seq: multi-sequence decode attention issued one sequence per call '
                               '(first: %d sequences, longest key %d > %d)', q.shape[0], kw['max_seqlen_k'], min_k)
                state['logged'] = True
            return out
        return original(*args, **kw)

    fa.flash_attn_varlen_func = wrapped
    fa._b70_fa_decode_per_seq = True
    logger.warning('b70_fa_decode_per_seq: enabled (keys longer than %d)', min_k)
