# BF16 synchronized profile and SLM direct v2

Date: 2026-08-12

## Decision

Keep synchronized profiling as a diagnostic tool. Preserve the SLM-tiled
direct BF16 kernel as a default-off negative result; do not advance scalar
tiling further. The next direct-kernel attempt must use XMX/joint-matrix or a
library batched primitive.

Drafter training remains closed by operator direction. No drafter weights or
training artifacts changed.

## Synchronized operation profile

Source commit `4dad88ad4` adds `GGML_SYCL_OP_PROFILE=2`. Unlike mode 1, mode 2
waits for the main device queue before and after each generic operation. It is
intentionally intrusive and its throughput is not a benchmark result, but it
prevents queue backpressure from being charged to a later unrelated op.

A 64-token diagnostic JSON completion exposed six target verification passes.
The cumulative batch-16 BF16 bucket contained 4,296 GEMM calls and 470,725 us,
or exactly 716 calls and about 78.45 ms of synchronized BF16 GEMM time per
target pass. This identifies small-batch BF16 projection execution as the
dominant device target. The diagnostic log is:

`/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sync-op-profile-20260812.log`

The 55.21 tok/s reported by this synchronized 64-token JSON-only request is
not comparable to the fixed three-class suite and must not be promoted.

## SLM direct v2

Source commit `efb0017c6` replaces the original scalar direct kernel with an
SLM-tiled prototype. Each 1024-thread work-group stages a 1024-by-N activation
tile once and shares it across 32 output rows. The path is still default-off
behind `GGML_SYCL_BF16_DIRECT=1` and is restricted to N=2 through N=16.

The implementation removes the v1 full-activation re-read per output row, but
its scalar BF16 arithmetic and large work-groups remain far slower than XMX.

| Arm | Prose | Code | JSON | Arithmetic mean |
| --- | ---: | ---: | ---: | ---: |
| primitive-cache control | 44.710 | 64.619 | 78.081 | 62.470 |
| SLM direct v2 | 15.375 | 22.381 | 26.285 | 21.347 |
| candidate/control | 0.344x | 0.346x | 0.337x | **0.342x** |

The candidate changes the prose hash from `914f754747d0edaa` to
`a71ceb1ecf6a3e43`, while code and JSON remain `cf2b2c4fd9e36fe5` and
`4f813a9706abc163`. Its speculative output still matches the previously
observed oneMKL reduction identity; it is not incumbent-byte-identical.

Raw result:

- `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/bf16-direct-slm-v2-ab-20260812.jsonl`;
- SHA-256 `197a6e6ff82111ccc05f15aa039a570708ad438a0128f22ca38a5a7a63d67d82`.

Production was restarted on the incumbent binary after both diagnostic
windows. Neither profiling nor the direct kernel is enabled in production.

## Next action

Inspect existing SYCL XMX/joint-matrix kernels and oneMKL grouped/batched GEMM
interfaces. A viable kernel must retain matrix-engine execution while reducing
the 716 small-batch dispatches or improving their bandwidth utilization.
