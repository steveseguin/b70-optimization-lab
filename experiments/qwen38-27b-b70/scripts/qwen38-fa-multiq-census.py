#!/usr/bin/env python3
"""Multi-query decode census: paged_decode_multiq vs per-row decode calls, bitwise + timing.

Operator diagnostic only. The verifier-rows overlay (b70_fa_verify_rows.py) makes an
MTP verify step bit-identical to no-MTP decode by issuing one single-query decode call
per verified row, which costs one full KV pass per row. The new
`torch.ops._vllm_fa2_C.paged_decode_multiq` op does the same arithmetic in one KV pass:
row j of a q_len window attends to seqused_k - (q_len-1-j) tokens, with the KV tiles
loaded once and a separate accumulator/mask per row.

For Qwen3.8-27B one-card attention shapes (24 query heads, 4 KV heads, head 256,
832-token pages, interleaved K/V cache views, expanded float32 descales) this compares,
for several KV lengths and both contiguous and scattered block tables:
  * every row of the multi-query call against the same row computed alone with
    seqused_k = L-(q_len-1-r), issued exactly as the overlay issues it, bitwise;
  * wall time of the multi-query call against the q_len single-row calls.

KV lengths that violate the op's precondition -- (seqused_k - 1) % kv_tile >= q_len - 1,
i.e. all rows must end in the same KV tile -- are expected to be refused by the op; they
are exercised too so the refusal is part of the census.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

Q_HEADS, KV_HEADS, HEAD, PAGE = 24, 4, 256, 832
KV_TILE = 64  # page 832 is a multiple of 64 -> kv_tile 64 policy


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=20260917)
    ap.add_argument('--q-len', type=int, default=6)
    # Lengths that satisfy (L-1) % 64 >= q_len-1: multiples of 64 give 63, the
    # +10 variants exercise a partial last KV tile.
    ap.add_argument('--kv-lens',
                    default='2048,2058,4096,4106,8192,12288,12298,16384,24576,32768,40000')
    # Lengths that violate the precondition ((L-1) % 64 < q_len-1): expect a refusal.
    ap.add_argument('--bad-kv-lens', default='2049,4100,8195')
    ap.add_argument('--layouts', default='contiguous,scattered')
    ap.add_argument('--repeats', type=int, default=20)
    ap.add_argument('--num-splits', type=int, default=None,
                    help='force a split count on both paths (default: let each path pick)')
    ap.add_argument('--skip-host-check', action='store_true',
                    help='set VLLM_XPU_MULTIQ_HOST_CHECK=0 (no host sync in the op; '
                         'the precondition refusals are then not exercised)')
    args = ap.parse_args()

    if args.skip_host_check:
        os.environ['VLLM_XPU_MULTIQ_HOST_CHECK'] = '0'

    import torch
    import vllm  # noqa: F401
    import vllm._xpu_ops  # noqa: F401
    from vllm.v1.attention.backends.fa_utils import (flash_attn_varlen_func,
                                                     get_flash_attn_version)

    q_len = args.q_len
    dev = torch.device('xpu:0')
    fa_version = get_flash_attn_version()
    gen = torch.Generator().manual_seed(args.seed)
    kv_lens = [int(x) for x in args.kv_lens.split(',') if x]
    bad_kv_lens = [int(x) for x in args.bad_kv_lens.split(',') if x]
    pages_total = max(1, -(-max(kv_lens + bad_kv_lens) // PAGE))

    report = dict(schema='neural.download.qwen38-fa-multiq-census.v1',
                  classification='operator-diagnostic-only', fa_version=fa_version,
                  q_len=q_len, kv_tile=KV_TILE, page=PAGE, pages_total=pages_total,
                  repeats=args.repeats, num_splits=args.num_splits,
                  host_check=not args.skip_host_check, cases=[], refusals=[])
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Match the served call: key/value are interleaved views of one
    # [pages, 832, 4, 512] cache (value at offset 256), descales are expanded
    # float32 ones [1, KV_HEADS].
    storage = (torch.randn((pages_total, PAGE, KV_HEADS, 2 * HEAD), generator=gen) * 0.5
               ).to(torch.float16).to(dev)
    key_cache, value_cache = storage[..., :HEAD], storage[..., HEAD:]
    descale = torch.ones((1, 1), dtype=torch.float32, device=dev).expand(1, KV_HEADS)
    scale = HEAD ** -0.5

    def row_call(query, out, seq_len, block_table):
        """One single-query decode call, issued exactly as b70_fa_verify_rows does."""
        flash_attn_varlen_func(
            q=query, k=key_cache, v=value_cache, out=out,
            cu_seqlens_q=torch.tensor([0, 1], dtype=torch.int32, device=dev), max_seqlen_q=1,
            seqused_k=torch.tensor([seq_len], dtype=torch.int32, device=dev),
            max_seqlen_k=seq_len,
            softmax_scale=scale, causal=True, alibi_slopes=None, window_size=[-1, -1],
            block_table=block_table, softcap=0, scheduler_metadata=None, fa_version=fa_version,
            q_descale=None, k_descale=descale, v_descale=descale, dynamic_causal=None,
            num_splits=0 if args.num_splits is None else args.num_splits,
            s_aux=None, mask_mod=None, aux_tensors=None)

    def rows(query, kv_len, block_table, out=None):
        """The overlay's path: q_len independent single-query decode calls."""
        if out is None:
            out = torch.zeros((q_len, Q_HEADS, HEAD), dtype=torch.float16, device=dev)
        for r in range(q_len):
            back = q_len - 1 - r
            row_call(query[r:r + 1].contiguous(), out[r:r + 1], kv_len - back, block_table)
        return out

    def multiq(query, kv_len, block_table, out=None):
        if out is None:
            out = torch.zeros((q_len, Q_HEADS, HEAD), dtype=torch.float16, device=dev)
        torch.ops._vllm_fa2_C.paged_decode_multiq(
            query, key_cache, value_cache, out,
            torch.tensor([0, q_len], dtype=torch.int32, device=dev),
            torch.tensor([kv_len], dtype=torch.int32, device=dev),
            block_table, q_len, kv_len, descale, descale, scale, args.num_splits)
        return out

    def timed(fn, repeats):
        fn()
        torch.xpu.synchronize()
        t0 = time.perf_counter()
        for _ in range(repeats):
            fn()
        torch.xpu.synchronize()
        return (time.perf_counter() - t0) / repeats * 1e3

    def write():
        args.out.write_text(json.dumps(report, indent=1))

    rng = random.Random(args.seed)
    for layout in args.layouts.split(','):
        order = list(range(pages_total))
        if layout != 'contiguous':
            rng.shuffle(order)
        block_table = torch.tensor([order], dtype=torch.int32, device=dev)

        for kv_len in kv_lens:
            query = (torch.randn((q_len, Q_HEADS, HEAD), generator=gen) * 0.5
                     ).to(torch.float16).to(dev)
            ref = rows(query, kv_len, block_table)
            got = multiq(query, kv_len, block_table)
            torch.xpu.synchronize()
            rows_equal = [bool(torch.equal(got[r], ref[r])) for r in range(q_len)]
            max_abs = float((got.float() - ref.float()).abs().max())
            repeat_equal = bool(torch.equal(got, multiq(query, kv_len, block_table)))
            case = dict(layout=layout, kv_len=kv_len,
                        precondition_ok=((kv_len - 1) % KV_TILE >= q_len - 1),
                        rows_equal=rows_equal, all_equal=all(rows_equal), max_abs=max_abs,
                        multiq_repeat_equal=repeat_equal,
                        ms_rows=timed(lambda: rows(query, kv_len, block_table), args.repeats),
                        ms_multiq=timed(lambda: multiq(query, kv_len, block_table),
                                        args.repeats))
            case['speedup'] = case['ms_rows'] / case['ms_multiq'] if case['ms_multiq'] else None
            report['cases'].append(case)
            write()
            print(json.dumps(case), flush=True)

        for kv_len in bad_kv_lens:
            query = (torch.randn((q_len, Q_HEADS, HEAD), generator=gen) * 0.5
                     ).to(torch.float16).to(dev)
            entry = dict(layout=layout, kv_len=kv_len,
                         precondition_ok=((kv_len - 1) % KV_TILE >= q_len - 1))
            try:
                multiq(query, kv_len, block_table)
                torch.xpu.synchronize()
                entry.update(refused=False, error=None)
            except Exception as exc:  # noqa: BLE001 - the refusal is the datum
                entry.update(refused=True, error=str(exc).splitlines()[0][:300])
            report['refusals'].append(entry)
            write()
            print(json.dumps(entry), flush=True)

    write()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
