# TP4 ring/MHC consumer overlap feasibility

Date: 2026-07-15

## Outcome

The two-stream hardware upper bound passes twice. Across 87 TP4 BF16 `[4096]`
rings and 85 independent MHC post/pre kernels, serial execution measured
`5.706` and `5.655 ms`. Submitting the MHC stream first reduced this to `5.063`
and `5.043 ms`, hiding `0.642` and `0.612 ms`. All reduced tensors and all four
MHC outputs were bitwise identical.

Submitting the communication stream first was neutral (`5.708` and
`5.654 ms`). The viable implementation is therefore not two ordinary commands:
it is a persistent MHC consumer submitted first, waiting on per-wire readiness
while the unchanged LL256 ring progresses.

This is a feasibility result, not a model speed result. The current screen uses
independent work to measure Xe2 concurrency; the real consumer must preserve
the dependency on the reduced output.

## Hard implementation gate

The test-only implementation must:

- leave ring reduction and forwarding arithmetic unchanged;
- release-publish epoch-tagged readiness after each of the nine active wires;
- enqueue a bounded-timeout persistent consumer on a second in-order queue
  before the ring;
- preserve canonical MHC accumulation order;
- pass bitwise equality for the reduced value and all four MHC outputs over at
  least 40 changing epochs on every rank;
- add no more than `1 us` notification tax;
- save at least `6 us` per boundary at the slowest rank, projecting at least
  `0.51 ms` over 85 boundaries.

Anything below that closes the lane before model integration. A component pass
still requires at least `0.50 ms/token` in the complete decode graph, then the
strict quality suite.

## Zero-code protocol checks

Two cheaper protocols were screened before starting source work:

- raising `CCL_SYCL_ALLREDUCE_LL_THRESHOLD` from 4096 to 8192 saved only
  `0.169312 ms` over the long 87-call chain (`5.397964 -> 5.228652 ms`), below
  the `0.50 ms` gate;
- `CCL_SYCL_ALLREDUCE_ARC=1` corrupted all 64 measured epochs on every rank,
  beginning at the second tensor (`flat_index=4096`) with 19,264 mismatched
  elements and maximum absolute error 342.

Keep threshold 4096 and ARC disabled.

Evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/ring-mhc-two-stream-gate-20260715T030148Z`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/ll-protocol-87-gate-20260715T030323Z`;
- `../data/tp4-ring-mhc-two-stream-gate-20260715.json`;
- `../data/tp4-ll-protocol-87-gate-20260715.json`;
- `../scripts/tp4-ring-mhc-two-stream-upper-bound.py`.
