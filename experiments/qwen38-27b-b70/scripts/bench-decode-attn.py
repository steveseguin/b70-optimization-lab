#!/usr/bin/env python3
"""Time the XPU attention calls of one writing step, at the shapes one card sees on the two-card 27B FP8 server.

With MTP5 the target model checks 6 tokens per step (`--qlen 6`): `flash_attn_varlen_func` sends a uniform batch of
q_len <= 16 to the split-K decode kernel as 6 one-token decodes, each reading the whole cache (the "spec-decode fast
path"); the drafter's MTP layer decodes one token per pass (`--qlen 1`). 12 query heads, 2 key/value heads, head size
256, FP16 paged cache of `--pages`-token pages (832 on the agent server, 1,280 for long documents).

Per point: median time of `--reps` calls, the rate at which the call reads the cache's unique bytes (context x 2 kv
heads x 256 x 2 bytes x K and V), and two exactness facts: two calls on the same inputs are bitwise equal, and each of
the 6 checked rows equals a one-token decode at that row's own length (what plain decoding would compute).
Arms: `fast` = the default path; `chunk` = the same 6-token call with the fast path off (chunk-prefill kernel).

  docker run --rm --device /dev/dri:/dev/dri --group-add render --memory 6g -e ONEAPI_DEVICE_SELECTOR=level_zero:0 \
    -v $PWD/bench-decode-attn.py:/tmp/b.py:ro -v $OUT:/out --entrypoint python3 <image> /tmp/b.py --out /out/x.json
"""
import argparse
import json
import time

import torch
from vllm_xpu_kernels import flash_attn_interface as fai
from vllm_xpu_kernels.flash_attn_interface import flash_attn_varlen_func

ap = argparse.ArgumentParser()
ap.add_argument("--contexts", default="1000,25000,50000,100000,137000,200000,246000")
ap.add_argument("--pages", default="832,1280")
ap.add_argument("--qlen", type=int, default=6, help="tokens checked per step (MTP depth + 1)")
ap.add_argument("--reps", type=int, default=21)
ap.add_argument("--out", required=True)
a = ap.parse_args()

HQ, HKV, D = 12, 2, 256
dev = "xpu"
FAST = fai._SPEC_DECODE_MAX_QLEN
torch.manual_seed(0)


def timed(fn, reps):
    o1 = fn()
    torch.xpu.synchronize()
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        o2 = fn()
        torch.xpu.synchronize()
        times.append(time.perf_counter() - t0)
    return o1, o2, sorted(times)[len(times) // 2], min(times)


rows = []
for page, ctx in [(int(p), int(c)) for p in a.pages.split(",") for c in a.contexts.split(",")]:
    total = ctx + a.qlen
    nblk = (total + page - 1) // page
    kc = torch.randn(nblk, page, HKV, D, dtype=torch.float16, device=dev)
    vc = torch.randn(nblk, page, HKV, D, dtype=torch.float16, device=dev)
    bt = torch.arange(nblk, dtype=torch.int32, device=dev).view(1, nblk)
    unique_bytes = total * HKV * D * 2 * 2

    def call(q, n_q, used):
        out = torch.empty_like(q)
        cu_q = torch.tensor([0, n_q], dtype=torch.int32, device=dev)
        seq = torch.tensor([used], dtype=torch.int32, device=dev)
        flash_attn_varlen_func(out=out, q=q, k=kc, v=vc, cu_seqlens_q=cu_q, seqused_k=seq, max_seqlen_q=n_q,
                               max_seqlen_k=used, softmax_scale=D ** -0.5, causal=True, block_table=bt,
                               window_size=(-1, -1))
        return out

    qs = torch.randn(a.qlen, HQ, D, dtype=torch.float16, device=dev)
    arms = [("decode1", 1), ("fast", a.qlen), ("chunk", a.qlen)]
    singles = None
    for name, n_q in arms:
        fai._SPEC_DECODE_MAX_QLEN = 0 if name == "chunk" else FAST
        if name == "decode1":
            q = qs[-1:].contiguous()
            fn = lambda: call(q, 1, total)
        else:
            fn = lambda: call(qs, a.qlen, total)
        o1, o2, t, tmin = timed(fn, a.reps)
        r = dict(context=ctx, page=page, arm=name, qlen=n_q, median_ms=round(t * 1e3, 4),
                 min_ms=round(tmin * 1e3, 4), unique_gbps=round(unique_bytes / t / 1e9, 1),
                 repeat_bitwise_equal=bool(torch.equal(o1, o2)),
                 kernel_missing_fallback=sorted(fai._warned_missing_configs))
        if name != "decode1":
            if singles is None:
                fai._SPEC_DECODE_MAX_QLEN = FAST
                singles = [call(qs[j:j + 1].contiguous(), 1, total - (a.qlen - 1 - j)) for j in range(a.qlen)]
            r["rows_equal_plain_decode"] = sum(bool(torch.equal(o1[j:j + 1], singles[j])) for j in range(a.qlen))
        rows.append(r)
        print(json.dumps(r), flush=True)
    fai._SPEC_DECODE_MAX_QLEN = FAST
    del kc, vc
    torch.xpu.empty_cache()
json.dump(dict(device=torch.xpu.get_device_name(0), heads_q=HQ, heads_kv=HKV, head_size=D, pages=a.pages,
               qlen=a.qlen, spec_decode_max_qlen=FAST, rows=rows), open(a.out, "w"), indent=1)
