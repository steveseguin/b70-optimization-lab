#!/usr/bin/env python3
"""Time the XPU prompt-attention kernel alone, at the shapes one card sees on the two-card 27B FP8 context server.

One prompt step of `--step` query tokens reads a paged FP16 cache of `context` earlier tokens plus itself (causal):
12 query heads, 2 key/value heads, head size 256 (Qwen3.8-27B on TP2), cache pages of `--page` tokens. Reports the
time per call and the attention FLOP rate (4 x step x (context + step/2) x 256 x 12 per call, the useful work).
Also checks that two calls on the same inputs give bitwise equal outputs.

Runs inside the R314 image on one card, nothing else on that card:
  docker run --rm --device /dev/dri:/dev/dri --group-add render --memory 6g -e ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    -v $PWD/bench-chunk-prefill-attn.py:/tmp/b.py:ro -v $OUT:/out --entrypoint python3 <image> /tmp/b.py --out /out/x.json
"""
import argparse
import json
import time

import torch
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

ap = argparse.ArgumentParser()
ap.add_argument("--steps", default="832,1280,2048,4096")
ap.add_argument("--contexts", default="0,25000,50000,100000,150000,200000")
ap.add_argument("--page", type=int, default=0, help="cache page size; 0 = the step size (as on the exact-cache server)")
ap.add_argument("--reps", type=int, default=5)
ap.add_argument("--out", required=True)
a = ap.parse_args()

HQ, HKV, D = 12, 2, 256
dev = "xpu"
torch.manual_seed(0)
rows = []
for step in [int(x) for x in a.steps.split(",")]:
    page = a.page or step
    for ctx in [int(x) for x in a.contexts.split(",")]:
        total = ctx + step
        nblk = (total + page - 1) // page
        kc = torch.randn(nblk, page, HKV, D, dtype=torch.float16, device=dev)
        vc = torch.randn(nblk, page, HKV, D, dtype=torch.float16, device=dev)
        q = torch.randn(step, HQ, D, dtype=torch.float16, device=dev)
        bt = torch.arange(nblk, dtype=torch.int32, device=dev).view(1, nblk)
        cu_q = torch.tensor([0, step], dtype=torch.int32, device=dev)
        used = torch.tensor([total], dtype=torch.int32, device=dev)

        def call():
            out = torch.empty_like(q)
            flash_attn_varlen_func(out=out, q=q, k=kc, v=vc, cu_seqlens_q=cu_q, seqused_k=used, max_seqlen_q=step,
                                   max_seqlen_k=total, softmax_scale=D ** -0.5, causal=True, block_table=bt,
                                   window_size=(-1, -1))
            return out

        o1 = call()
        torch.xpu.synchronize()
        times = []
        for _ in range(a.reps):
            t0 = time.perf_counter()
            o2 = call()
            torch.xpu.synchronize()
            times.append(time.perf_counter() - t0)
        same = bool(torch.equal(o1, o2))
        t = sorted(times)[len(times) // 2]
        flops = 4.0 * step * (ctx + step / 2) * D * HQ
        r = dict(step=step, page=page, context=ctx, median_ms=round(t * 1e3, 3), min_ms=round(min(times) * 1e3, 3),
                 tflops=round(flops / t / 1e12, 1), repeat_bitwise_equal=same)
        rows.append(r)
        print(json.dumps(r), flush=True)
        del kc, vc, q, o1, o2
        torch.xpu.empty_cache()
json.dump(dict(device=torch.xpu.get_device_name(0), heads_q=HQ, heads_kv=HKV, head_size=D, rows=rows),
          open(a.out, "w"), indent=1)
