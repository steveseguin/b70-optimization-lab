# Late nonspeculative upper-bound closures

Date: 2026-07-15

## Outcome

Two final candidates were rejected by four-card hardware gates before a TP4
model integration: exact routed GEMM2 epilogue/reduction fusion and next-weight
L2 prefetch. Neither contains a credible `0.50 ms/token` saving at the current
43.766673 tok/s nonspeculative record.

## GEMM2 epilogue plus direct gather

The graph-replay gate compares the unchanged direct GEMM2 with direct GEMM2
plus the complete slot-order weighted gather. For the representative three-
local-expert route, deleting the entire gather node projects only:

| GPU | Deleted boundary us/layer | Projected ms/token |
| ---: | ---: | ---: |
| 0 | 3.515 | 0.1511 |
| 1 | 3.635 | 0.1563 |
| 2 | 3.900 | 0.1677 |
| 3 | 3.649 | 0.1569 |

Even the unrepresentative six-local case peaks at 0.230 ms/token. This is an
optimistic deletion-only ceiling. An exact fused implementation would have to
process slots 0 through 5 in order, preserve each GEMM2 result's BF16 rounding
point, multiply by its FP32 weight, accumulate in the existing FP32 order, and
round once to final BF16. Atomics or reassociation are not exact, while a
single N-tile workgroup would serialize slot GEMMs and reduce the ceiling.

Decision: close this boundary. Do not build the epilogue fusion unless it is
part of a materially larger, separately gated architecture.

Evidence:

- script: `scripts/bench-m1-direct-gather-upper-bound.py`;
- raw results:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m1-direct-gather-upper-bound-20260715T2245Z`.

## Next-weight L2 prefetch

A benchmark-only finite SYCL operator issued cache hints for the actual 4 MiB
shared-gate/up, 6 MiB fused-WQA/WKV, and 8 MiB WQ_B weight shapes. Both a
64-byte grid and a coarser 1 KiB grid were tested independently on all four
B70s after a 64 MiB cache-eviction pass.

The valid 1 KiB gate preserved every output exactly, but prefetch itself cost
71.2-84.6 us and changed projected consumer time by only -0.239 to +0.027
ms/token. A direct cold consumer versus the immediately repeated warm consumer
differed by only 0.884 us. The unchanged oneDNN W8A16 path therefore has no
meaningful cache-warming pool for the prefetch to expose; an overlap gate
cannot recover a saving that the consumer does not show.

The failed source is preserved at XPU-kernel commit `5a7f39e9`; its explicit
revert is `46bdf344`. The rebuilt package restores the record `_xpu_C` SHA-256
`3d07d85ce15a418d4355b0eaf5686c9cf6c7af92c9d5bf15b3884e9758161bf2`.

Decision: close next-weight prefetch without model integration.

Evidence:

- script: `scripts/bench-next-weight-l2-prefetch.py`;
- raw 64-byte results:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/next-weight-l2-prefetch-isolated-20260715T2250Z`;
- raw valid 1 KiB results:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/next-weight-l2-prefetch-isolated-1k-valid-20260715T2300Z`.

## Frontier consequence

The current measured backlog contains no remaining nonspeculative exact source
candidate above the 0.50 ms/token gate. Small gather, scheduler, MHC geometry,
recording-path, threshold, and cache changes have now been bounded or tested.
Further nonspeculative work needs a genuinely new decoder architecture, not a
smaller fusion around the existing graph.

The productive next step is to carry the 43.766673 base improvements and the
wide-epoch oneCCL repair into the separate row-exact MTP1 record lane, then
requalify the target verifier and acceptance economics. The 100/200 tok/s
objectives remain open.
