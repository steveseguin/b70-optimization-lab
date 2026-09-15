"""Diagnostic overlay: record the arguments of paged flash-attention calls (never for serving).

Enabled only with B70_FA_TRACE=<jsonl path>. Wraps the flash_attn_varlen_func
global used by vllm.v1.attention.backends.flash_attn and records, for the first
B70_FA_TRACE_LIMIT calls whose query has at most 16 rows, every scalar argument,
tensor shapes/dtypes/strides/storage offsets, and the small index tensors
(cu_seqlens_q, seqused_k, first block-table entries). Values are never modified.
"""
import json
import os

_COUNT = {'n': 0}


def register():
    path = os.environ.get('B70_FA_TRACE', '')
    if not path:
        return
    import torch
    from vllm.v1.attention.backends import flash_attn as fa

    if getattr(fa, '_b70_fa_trace', False):
        return
    limit = int(os.environ.get('B70_FA_TRACE_LIMIT', '200'))
    original = fa.flash_attn_varlen_func

    def describe(value):
        if isinstance(value, torch.Tensor):
            record = dict(shape=list(value.shape), dtype=str(value.dtype), stride=list(value.stride()),
                          storage_offset=value.storage_offset(), ptr_mod_64=value.data_ptr() % 64)
            if value.numel() <= 64 and value.dtype in (torch.int32, torch.int64, torch.bool):
                record['values'] = value.detach().cpu().flatten().tolist()
            elif value.dim() == 2 and value.dtype in (torch.int32, torch.int64):
                record['head'] = value[:, :4].detach().cpu().tolist()
            return record
        if isinstance(value, (list, tuple)):
            return [describe(v) for v in value]
        return value if isinstance(value, (int, float, str, bool, type(None))) else repr(value)

    def traced(*args, **kwargs):
        q = kwargs.get('q', args[0] if args else None)
        if isinstance(q, torch.Tensor) and q.shape[0] <= 16 and _COUNT['n'] < limit:
            _COUNT['n'] += 1
            with open(path, 'a') as log:
                log.write(json.dumps(dict(call=_COUNT['n'], args=[describe(a) for a in args],
                                          kwargs={k: describe(v) for k, v in kwargs.items()})) + '\n')
        return original(*args, **kwargs)

    fa.flash_attn_varlen_func = traced
    fa._b70_fa_trace = True
