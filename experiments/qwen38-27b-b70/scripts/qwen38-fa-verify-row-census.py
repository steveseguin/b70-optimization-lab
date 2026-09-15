#!/usr/bin/env python3
"""Attention verify-row census: q_len=6 verify chunk vs q_len=1 decode rows over long paged KV.

Operator diagnostic only. One-card depth-5 serving matches no-MTP on short
prompts but flips a near-tie after a 12,288-token prompt. GDN state is fixed
size, so the context-length-dependent candidate is paged flash attention. For
Qwen3.8-27B one-card attention shapes (24 query heads, 4 KV heads, head 256,
832-token pages), compare row r of one causal 6-query call against the same
query computed alone with seqused_k = L-5+r, at several KV lengths, with
contiguous and scattered block tables.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

Q_HEADS, KV_HEADS, HEAD, PAGE, VERIFY = 24, 4, 256, 832, 6


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=20260915)
    ap.add_argument('--kv-lens', default='64,512,833,2048,4096,8192,12288,13312,16000')
    ap.add_argument('--layouts', default='contiguous,scattered')
    args = ap.parse_args()
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    from vllm.v1.attention.backends.fa_utils import flash_attn_varlen_func, get_flash_attn_version

    dev = torch.device('xpu:0')
    fa_version = get_flash_attn_version()
    gen = torch.Generator().manual_seed(args.seed)
    report = dict(schema='neural.download.qwen38-fa-verify-row-census.v1', classification='operator-diagnostic-only',
                  fa_version=fa_version, cases=[])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pages_total = 26
    # Match the served call: key/value are interleaved views of one [pages, 832, 4, 512] cache (strides
    # 1703936/2048/512/1, value at offset 256), descales are expanded float32 ones [1, KV_HEADS], and the
    # block table is 26 pages wide.
    storage = (torch.randn((pages_total, PAGE, KV_HEADS, 2 * HEAD), generator=gen) * 0.5).to(torch.float16).to(dev)
    key_cache, value_cache = storage[..., :HEAD], storage[..., HEAD:]
    descale = torch.ones((1, 1), dtype=torch.float32, device=dev).expand(1, KV_HEADS)
    scale = HEAD ** -0.5

    def attend(query, seq_len, q_len, block_table):
        out = torch.zeros((q_len, Q_HEADS, HEAD), dtype=torch.float16, device=dev)
        flash_attn_varlen_func(
            q=query, k=key_cache, v=value_cache, out=out,
            cu_seqlens_q=torch.tensor([0, q_len], dtype=torch.int32, device=dev), max_seqlen_q=q_len,
            seqused_k=torch.tensor([seq_len], dtype=torch.int32, device=dev), max_seqlen_k=seq_len,
            softmax_scale=scale, causal=True, alibi_slopes=None, window_size=[-1, -1], block_table=block_table,
            softcap=0, scheduler_metadata=None, fa_version=fa_version, q_descale=None, k_descale=descale,
            v_descale=descale, dynamic_causal=None, num_splits=0, s_aux=None, mask_mod=None, aux_tensors=None)
        torch.xpu.synchronize()
        return out

    for layout in args.layouts.split(','):
        order = list(range(pages_total)) if layout == 'contiguous' else [7, 2, 15, 0, 11, 4, 19, 9, 13, 1, 17, 5, 3, 18, 8, 12, 6, 16, 10, 14, 20, 25, 21, 24, 22, 23]
        block_table = torch.tensor([order], dtype=torch.int32, device=dev)
        for kv_len in [int(x) for x in args.kv_lens.split(',')]:
            query = (torch.randn((VERIFY, Q_HEADS, HEAD), generator=gen) * 0.5).to(torch.float16).to(dev)
            chunk = attend(query, kv_len, VERIFY, block_table)
            rows = []
            for r in range(VERIFY):
                single = attend(query[r:r + 1].contiguous(), kv_len - (VERIFY - 1 - r), 1, block_table)
                rows.append(dict(row=r, equal=bool(torch.equal(single[0], chunk[r])),
                                 max_abs=float((single[0].float() - chunk[r].float()).abs().max())))
            repeat_equal = bool(torch.equal(chunk, attend(query, kv_len, VERIFY, block_table)))
            case = dict(layout=layout, kv_len=kv_len, rows_equal=[x['equal'] for x in rows],
                        max_abs=max(x['max_abs'] for x in rows), chunk_repeat_equal=repeat_equal)
            report['cases'].append(case)
            args.out.write_text(json.dumps(report, indent=1))
            print(json.dumps(case), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
