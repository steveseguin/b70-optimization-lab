#!/usr/bin/env python3
"""Does padding a few-row FP8 W8A16 GEMM to 6 rows give the same rows, faster? (R314, one card; b70-w8a16-pad-rows)

For each weight shape K x N (default: the MLP down projection at TP2, 8704 x 5120, and at TP1, 17408 x 5120), with
the server's layout (FP8 e4m3 weight [N, K] passed as its [K, N] view; float32 128 x 128 block scales passed as the
contiguous [K/128, N/128] buffer) and the op the server calls (`torch.ops._xpu_C.fp8_gemm_w8a16`):
  rows     row r of an M-row call equals row r of the 8-row call, every M in 1..8, bitwise
  padded   for M < 6: the M real rows of the call padded to 6 with zero rows, and with random rows, equal the M-row
           call bitwise
  repeat   the same call twice gives the same bits
  timing   median device time (events, 200 calls after 20 warm-up) at M = 1, 2, 4, 5, 6, 8 and padded M = 1
Weights and activations are made on the card (no host upload). Operator diagnostic only.
"""
import argparse
import json
import statistics

import torch
import vllm._xpu_ops  # noqa: F401  (loads _xpu_C)

ap = argparse.ArgumentParser()
ap.add_argument('--shapes', default='8704x5120,17408x5120')
ap.add_argument('--pad-to', type=int, default=6)
ap.add_argument('--out', required=True)
ap.add_argument('--seed', type=int, default=20261017)
a = ap.parse_args()
dev = torch.device('xpu:0')
torch.manual_seed(a.seed)
op = torch.ops._xpu_C.fp8_gemm_w8a16


def timed(fn, n=200, warm=20):
    for _ in range(warm):
        fn()
    torch.xpu.synchronize()
    out = []
    for _ in range(n):
        s, e = torch.xpu.Event(enable_timing=True), torch.xpu.Event(enable_timing=True)
        s.record()
        fn()
        e.record()
        e.synchronize()
        out.append(s.elapsed_time(e) * 1e3)
    return round(statistics.median(out), 1)


report = {'schema': 'b70-w8a16-pad-rows-census.v1', 'torch': torch.__version__, 'pad_to': a.pad_to, 'shapes': []}
ok_all = True
with torch.no_grad():
    for item in a.shapes.split(','):
        k, n = (int(x) for x in item.lower().split('x'))
        w = (torch.randn(n, k, device=dev, dtype=torch.float16) * 0.05).to(torch.float8_e4m3fn)
        scale = torch.rand(n // 128, k // 128, device=dev, dtype=torch.float32) + 0.5
        scale_kn = scale.t().contiguous()
        bt = w.t()
        x = torch.randn(8, k, device=dev, dtype=torch.float16)
        ref = {m: op(x[:m].contiguous(), bt, scale_kn, None) for m in range(1, 9)}
        rows = {m: all(torch.equal(ref[m][r], ref[8][r]) for r in range(m)) for m in range(1, 9)}
        pad_zero, pad_rand = {}, {}
        for m in range(1, a.pad_to):
            z = torch.cat([x[:m], x.new_zeros((a.pad_to - m, k))])
            r = torch.cat([x[:m], torch.randn(a.pad_to - m, k, device=dev, dtype=torch.float16)])
            pad_zero[m] = torch.equal(op(z, bt, scale_kn, None)[:m], ref[m])
            pad_rand[m] = torch.equal(op(r, bt, scale_kn, None)[:m], ref[m])
        repeat = all(torch.equal(op(x[:m].contiguous(), bt, scale_kn, None), ref[m]) for m in (1, 2, 5, 6, 8))
        times = {str(m): timed(lambda m=m: op(x[:m].contiguous(), bt, scale_kn, None)) for m in (1, 2, 4, 5, 6, 8)}
        one = x[:1].contiguous()
        times['1_padded'] = timed(lambda: op(torch.cat([one, one.new_zeros((a.pad_to - 1, k))]), bt, scale_kn, None)[:1])
        ok = all(rows.values()) and all(pad_zero.values()) and all(pad_rand.values()) and repeat
        ok_all &= ok
        row = {'K': k, 'N': n, 'rows_equal_8row_call': rows, 'padded_zero_equal': pad_zero,
               'padded_random_equal': pad_rand, 'repeat_deterministic': repeat, 'median_us': times, 'ok': ok}
        report['shapes'].append(row)
        print(json.dumps({'K': k, 'N': n, 'ok': ok, 'median_us': times}), flush=True)
report['ok'] = ok_all
open(a.out, 'w').write(json.dumps(report, indent=1) + '\n')
print('census ok' if ok_all else 'census MISMATCHES')
raise SystemExit(0 if ok_all else 1)
