# Late TP4 collective and expert-placement gates

Date: **2026-07-15**

## Outcome

Three cheap paths are closed without changing the trustworthy **34.0671 tok/s**
record: LL256 workgroup geometry, TP4 recursive doubling, and round-robin
expert placement. The first two are exact but fail the performance gate. The
third reaches the intended interleaved layout but fails the first arithmetic
replay, so it was not speed-tested.

The record also used the virtual-environment oneCCL library, not the configured
USB build. `/proc` mappings identify
`/home/steve/.venvs/deepseek-v4-xpu/lib/libccl.so.1`, package
`oneccl==2021.17.2`, SHA-256
`ace144a390a53720b2743844decf127661c942b56f3b414900b9d8c11461acc3`.
The launcher now records runtime library identity separately from the source
worktree head.

## LL256 geometry

oneCCL commit `c6aec66` added the default-off `B70_ONECCL_LL_THREADS` sweep.
All exact BF16 `[4096]` chains passed. Across 87 ordered reductions, 8 threads
was best at `5.526326 ms`, but the two 64-thread controls were `6.106464` and
`5.665504 ms`. That is only `0.360 ms` against their mean and `0.139 ms`
against the reverse control—below the required `0.50 ms` model-integration
gate. The result is too order-sensitive to promote.

## Recursive doubling

oneCCL commit `bef2321` adds a guarded
`CCL_SYCL_ALLREDUCE_LL=recursive_doubling` protocol. It uses two XOR exchanges
and the existing in-band LL256 sequence messages. All 24 changed-input epochs
on all four ranks were exact. Paired max-rank 87-call device medians were:

- ring control A: `5.579730 ms`;
- recursive doubling: `5.644860 ms`;
- ring control B: `5.578872 ms`.

The candidate is `0.0656 ms` slower than the control mean. Fewer readiness
phases do not compensate for sending the full 8 KiB payload twice. Keep the
code as negative evidence; retain ring in production.

## Round-robin experts

vLLM commit `62b8bed9` passes the existing global-to-local expert map into the
XPU fused-MoE runtime and guards the otherwise unsupported interleaved path.
The server log confirms rank 0 owned experts `0,4,8,...,156`, with analogous
placement on the other ranks. The first changed-input gate returned
`1369 -> 361 -> 1369` instead of `1073 -> 437 -> 1073`, all with
`cached_tokens=0`.

The XPU kernel can consume an arbitrary expert map, but the complete packed
MXFP4 loading/post-processing path is not map-clean. Some state still assumes
40 contiguous global experts per rank. Because placement changes model
semantics, this lane is correctness-rejected before speed testing. Do not use
the CLI option alone: upstream vLLM silently falls back to linear placement
for this backend.

## Rank-skew trace limitation

The current graph identity produced four approximately 94 MiB traces with
exactly 87 oneCCL all-reduce events per rank. Raw cross-device timestamps are
not usable: profiler startup delayed the first collective by tens of seconds,
serialized work, and made one rank appear to execute microsecond collectives
while peers took milliseconds. This confirms the collective count, not normal
rank-arrival skew. Future skew measurement must use low-overhead in-ring epoch
instrumentation or device-local deltas, not profiler timestamps across GPUs.

Structured evidence is in
[`../data/late-tp4-gates-20260715.json`](../data/late-tp4-gates-20260715.json).
The only remaining collective direction with a measured positive upper bound
is the resident per-wire MHC consumer described in the earlier overlap note.
Its readiness-marker prerequisite subsequently passed at a conservative
`0.446 us` tax per boundary; see
[`2026-07-15-ring-readiness-marker-gate.md`](2026-07-15-ring-readiness-marker-gate.md).
