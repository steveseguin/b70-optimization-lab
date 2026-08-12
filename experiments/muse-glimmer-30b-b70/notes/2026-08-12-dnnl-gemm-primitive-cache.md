# oneDNN GEMM primitive cache: exact first-pass win

Date: 2026-08-12

## Decision

Keep and advance the default-off oneDNN GEMM primitive cache. It improves the
exact three-class BF16 TP4 comparator by 11.1% while preserving all output
hashes and accepted-token counts. Production was restored on the incumbent
binary; this candidate has not yet been promoted.

Drafter training remains closed by operator direction. No drafter weights or
training artifacts changed.

## Root cause and implementation

The incumbent BF16 `MUL_MAT` path reconstructed a oneDNN memory descriptor,
matmul primitive descriptor, matmul primitive, and argument map for every
logical call. The existing host profiler measured about 23.7 us per BF16
batch-16 submission, roughly five times the other operation classes.

Source checkpoint `934d6e3cf` adds a per-SYCL-backend-context cache keyed by
queue, dimensions, strides, data types, and batch dimensions. A cache hit
reuses the same oneDNN matmul primitive and memory descriptors, while binding
the current input/output pointers for execution. The device primitive,
BF16/BF16/F32 types, accumulation path, and output layout remain unchanged.

The feature is default-off and controlled by
`GGML_SYCL_DNNL_GEMM_CACHE=1`. The direct oneMKL candidate was disabled for
this A/B (`GGML_SYCL_BF16_MKL=0`).

## Exact A/B

- source: `/home/steve/src/llama.cpp-muse-100` at `934d6e3cf`;
- isolated build: `build-sycl-b70-aot-bmg-g31-bf16mkl-icpx`;
- four Arc Pro B70 GPUs, tensor parallel, KV mirroring off;
- BF16 two-part target and stock BF16 DFlash drafter;
- `-ngl 99 -c 32768 --parallel 1 -b 1024 -ub 1024 --threads 8 -fa on`;
- DFlash `n_max=15`, `p_min=0.15`;
- sequential greedy prose/code/JSON requests, 256 generated tokens,
  `cache_prompt=false`;
- only changed variable: `GGML_SYCL_DNNL_GEMM_CACHE=0/1`.

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| control | 39.485 | 57.182 | 69.933 | 55.533 |
| primitive cache | 44.262 | 63.670 | 77.154 | 61.695 |
| improvement | +12.10% | +11.35% | +10.33% | **+11.10%** |

Output hashes were identical in all three classes:

- prose: `914f754747d0edaa`;
- code: `cf2b2c4fd9e36fe5`;
- JSON: `4f813a9706abc163`.

Accepted-token counts were also identical: prose 172, code 197, JSON 207.
JSON draft attempts differed by two (`674` control versus `672` candidate),
but the accepted count and generated text were identical.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dnnl-gemm-cache-ab-20260812.jsonl`;
- SHA-256 `22f9da21e94c5c4c3ee2a69088b618e6cfc7bb7b1eac27ca369d7d506e7a57ac`.

## Failed graph prototype

The preceding cached TP SYCL-command-graph prototype is preserved in source
commit `e1cfa74a2` and reverted by `4a9a59fcf`. Its first completion failed
before output because oneDNN SDPA attempted to add an external dependency
event to the recorded graph:

`Graph nodes cannot depend on events from outside the graph.`

This disproves whole-meta-subgraph capture with the current oneDNN path.
Any later graph work must segment around oneDNN/library calls; it is not the
next campaign priority.

## Operations and next action

Production was restored after both controlled windows. The model list,
cache-zero 512-token code canary, and red-image routing canary all passed.
Production remains on the original binary and does not enable the cache.

## Follow-up: bounded cache, residual profile, and RoPE fusion

Source commit `09c84b991` limits cached GEMM shapes to `N <= 16`. This retains
the complete decode/verification target while preventing arbitrary prompt
remainders from growing the per-context cache indefinitely.

The post-cache host profile measured 43.207 / 62.296 / 75.194 tok/s
(60.232 mean) under instrumentation. BF16 batch-16 host submission fell from
about 23.7 us/call to 19.48 us/call (4,332,937 us over 222,436 calls). The
large apparent ADD and GLU totals are not device timings: the profiler records
host wall time and queue backpressure moved waits into later submissions.
Therefore it is not sound to rank new device kernels from those shifted totals.

The same source commit wires the existing SYCL fused
`ROPE -> VIEW -> SET_ROWS` kernel behind the default-off
`GGML_SYCL_ROPE_SET_ROWS_FUSION=1` gate. Adjacent same-binary A/B with the
primitive cache enabled measured:

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| cache control | 44.959 | 64.558 | 78.200 | 62.572 |
| RoPE/cache-write fusion | 44.987 | 64.513 | 78.596 | 62.699 |
| improvement | +0.06% | -0.07% | +0.51% | **+0.20%** |

All three output hashes and accepted-token counts were identical. The result
is correct but inside run noise, so the gate remains off and this is not a
claimed throughput win. Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/rope-setrows-fusion-ab-20260812.jsonl`;
- SHA-256 `fed30a943f526b2d29d39fd04d515c67261dddc71f063c96c5b3bf83a38c7e22`.

Production was restored on the incumbent binary after the window. The model
list, cache-zero 512-token code canary, and red-image routing canary passed.

Next: target duplicated activation conversion in consecutive FFN gate/up BF16
projections, while separately validating whether a no-training speculative
branch/tree can raise accepted tokens per target weight pass. Micro-fusion
alone does not have enough measured launch-overhead headroom to reach 100
tok/s.
