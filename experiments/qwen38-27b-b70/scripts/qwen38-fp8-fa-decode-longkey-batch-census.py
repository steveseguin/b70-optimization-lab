#!/usr/bin/env python3
"""Batch-invariance census of the full-attention paged decode kernel with LONG keys (2026-10-04).

The R151 census (qwen38-fp8-gdn-attention-decode-batch-census.py) found this kernel batch-invariant, but with key
lengths of 40 to 229 tokens. Multi-user serving puts sequences of very different lengths, thousands of tokens long, in
one decode call, and the call's `max_seqlen_k` is then the longest of them. This asks the same question at the
lengths the multi-user long-prompt suite uses: is each sequence's one-query output bitwise equal to its own
single-sequence call when it shares the call with others?

Run inside the lane image on one card, as the other census scripts are. Operator diagnostic only.
"""
import argparse
import json
import math
from pathlib import Path

import torch
import vllm_xpu_kernels._xpu_C  # noqa: F401
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

DEV = torch.device("xpu:0")
DT = torch.float16


def census(seed, kv_lens, num_splits):
    torch.manual_seed(seed)
    heads, kv_heads, hd, block = 12, 2, 256, 64
    nseq = len(kv_lens)
    blocks_per_seq = max(kv_lens) // block + 2
    nblocks = nseq * blocks_per_seq + 8
    kc = torch.randn((nblocks, block, kv_heads, hd), dtype=DT, device=DEV)
    vc = torch.randn((nblocks, block, kv_heads, hd), dtype=DT, device=DEV)
    q = torch.randn((nseq, heads, hd), dtype=DT, device=DEV)
    table = torch.arange(nseq * blocks_per_seq, dtype=torch.int32, device=DEV).view(nseq, blocks_per_seq)
    scale = 1.0 / math.sqrt(hd)

    def call(idx, max_k=None):
        B = len(idx)
        t = torch.tensor(idx, device=DEV)
        out = torch.empty((B, heads, hd), dtype=DT, device=DEV)
        seqused = torch.tensor([kv_lens[i] for i in idx], dtype=torch.int32, device=DEV)
        flash_attn_varlen_func(q=q[t].contiguous(), k=kc, v=vc, out=out,
                               cu_seqlens_q=torch.arange(B + 1, dtype=torch.int32, device=DEV), max_seqlen_q=1,
                               seqused_k=seqused, max_seqlen_k=int(max_k or seqused.max()), softmax_scale=scale, causal=True,
                               block_table=table[t].contiguous(), num_splits=num_splits, fa_version=2)
        torch.xpu.synchronize()
        return out

    single = [call([i]) for i in range(nseq)]
    rows = []
    for B in sorted({2, 4, 8, 16, nseq} & set(range(2, nseq + 1))):
        idx = list(range(B))
        out = call(idx)
        differ = [i for i in idx if not torch.equal(out[i:i + 1], single[i])]
        rows.append({"B": B, "sequences_differing_from_single": differ, "kv_lens_differing": [kv_lens[i] for i in differ],
                     "max_abs": max((float((out[i:i + 1].float() - single[i].float()).abs().max()) for i in differ), default=0.0),
                     "repeat_equal": bool(torch.equal(out, call(idx)))})
    # one sequence alone, but told the call's longest key is another sequence's length: isolates max_seqlen_k
    solo_longmax = []
    for i in range(nseq):
        out = call([i], max_k=max(kv_lens))
        if not torch.equal(out, single[i]):
            solo_longmax.append(kv_lens[i])
    return {"num_splits": num_splits, "kv_lens": kv_lens, "rows": rows,
            "all_batch_invariant": all(not r["sequences_differing_from_single"] for r in rows),
            "single_sequence_changes_with_larger_max_seqlen_k": solo_longmax}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--boundary", action="store_true",
                    help="instead of the three standard cases, sweep key lengths between the measured-invariant short "
                         "range and the long range, 64 sequences per case, to find where batch invariance ends")
    a = ap.parse_args()
    if a.boundary:
        report = {"schema": "qwen38-fp8-fa-decode-longkey-batch-census.v1", "torch": torch.__version__,
                  "device": torch.xpu.get_device_name(0), "cases": {}}
        cases = [("spread_86_to_229", [86 + (143 * i) // 63 for i in range(64)])]
        cases += [(f"all_{n}", [n] * 64) for n in (96, 128, 160, 192, 224, 229, 230, 240, 256, 320, 384, 512, 640, 768, 832, 833, 1024, 1280, 1645)]
        for label, lens in cases:
            for splits in (0, 1):
                r = census(a.seed, lens, splits)
                report["cases"][f"{label}/num_splits_{splits}"] = r
                print(label, "num_splits", splits, "batch-invariant:", r["all_batch_invariant"],
                      [(x["B"], len(x["sequences_differing_from_single"])) for x in r["rows"]], flush=True)
        a.out.write_text(json.dumps(report, indent=1) + "\n")
        return
    short = [40 + 3 * i for i in range(16)]
    mixed = [1645, 2434, 3300, 3981, 5770, 6524, 8104, 6412, 1700, 2500, 3400, 4100, 5900, 6600, 8200, 6500]
    same = [6524] * 16
    report = {"schema": "qwen38-fp8-fa-decode-longkey-batch-census.v1", "torch": torch.__version__,
              "device": torch.xpu.get_device_name(0), "cases": {}}
    for label, lens in (("short_40_to_85", short), ("mixed_1.6k_to_8.2k", mixed), ("all_6524", same)):
        for splits in (0, 1):
            r = census(a.seed, lens, splits)
            report["cases"][f"{label}/num_splits_{splits}"] = r
            print(label, "num_splits", splits, "batch-invariant:", r["all_batch_invariant"],
                  [(x["B"], len(x["sequences_differing_from_single"]), x["max_abs"]) for x in r["rows"]],
                  "solo changes with larger max_seqlen_k:", r["single_sequence_changes_with_larger_max_seqlen_k"], flush=True)
    a.out.write_text(json.dumps(report, indent=1) + "\n")


if __name__ == "__main__":
    main()
