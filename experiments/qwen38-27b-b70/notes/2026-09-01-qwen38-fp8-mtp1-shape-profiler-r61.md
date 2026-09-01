# Qwen3.8 FP8 TP2 MTP1 shape profiler R61

Date: 2026-09-01

Status: **diagnostic complete; 20 KiB collective variants rejected**.

R61 reran the selected R55C image with Torch shape recording enabled. The
bounded request used unrepeated technical prose, returned 96 tokens, and
reported zero cached tokens. This was diagnosis, not a performance run; trace
durations include profiler overhead and must not be quoted as ordinary latency.

Across eight profiled worker iterations, each rank executed 2,080 block-W8A16
GEMMs and 1,056 TP all-reduces. Every all-reduce carried one FP16 `[2,5120]`
tensor: exactly 20,480 bytes. Exact shape-to-kernel correlation also exposed
two full-vocabulary FP16 projections per iteration on each rank:

- drafter: `[1,5120] @ [5120,124160]`, about 2.13 ms in the trace;
- verifier: `[2,5120] @ [5120,124160]`, about 2.13 ms in the trace.

The profiler made the all-reduces look much slower than an isolated call, so
R61 did not infer a collective win from those absolute trace durations. It
instead ran the exact 20 KiB operation 10,000 times per arm on two B70s, with
three order-rotated repeats:

| oneCCL treatment | repeated average |
| --- | --- |
| selected ring, LL threshold 4,096 | `0.016 ms`; 1.27/1.29/1.28 GB/s |
| ring, LL threshold 32,768 | `0.016 ms`; 1.26/1.27/1.26 GB/s |
| two-shots, LL threshold 32,768 | `0.017 ms`; 1.20/1.22/1.19 GB/s |

Raising the threshold did nothing, and two-shots was consistently slower.
The Flash-Next TP4 collective setting therefore does not transfer to this TP2
payload. The selected ring settings remain unchanged and no endpoint load was
justified.

The narrower next target is the draft-only full-vocabulary projection. A
candidate may change draft-token proposals and acceptance, but the FP8 target
verifier must remain byte-for-byte on the selected path. Promotion still
requires the complete strict varied-prompt output contract, determinism,
cache-zero receipts, canaries, and a material endpoint speed win.

Reproduce the shape census from retained traces with:

```bash
experiments/qwen38-27b-b70/scripts/summarize-torch-xpu-shape-trace.py \
  /path/to/rank0.pt.trace.json.gz /path/to/rank1.pt.trace.json.gz \
  --output /path/to/shape-summary.json
```

Structured evidence:
[`2026-09-01-qwen38-fp8-mtp1-shape-profiler-r61-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-shape-profiler-r61-result.json).
