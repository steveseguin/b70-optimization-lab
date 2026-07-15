# TP4 ring readiness marker gate

Date: **2026-07-15**

## Outcome

The prerequisite for a resident MHC consumer passes. oneCCL commit
`1edec4576f6424f645fcee8b18df6844c636423c` adds the default-off
`CCL_SYCL_ALLREDUCE_LL=ring_markers` route. The production ring arithmetic and
forwarding remain unchanged. After each final local wire writeback, the ring
release-publishes its current epoch in storage reserved from the unused tail of
the LL scatter buffer.

All four ranks passed an exact smoke test and 24 changing epochs. Paired
slowest-rank device times across 87 BF16 `[4096]` reductions were:

- ring control A: `5.165472 ms`;
- ring plus readiness markers: `5.204264 ms`;
- ring control B: `5.395494 ms`.

The conservative comparison is against the faster control. Marker publication
therefore adds `0.038792 ms / 87`, or **`0.446 us` per boundary**, below the
hard `1 us` gate. Against the two-control mean, the candidate is faster by
`0.076219 ms`; that is measurement noise, not a claimed speedup.

## Why it matters

The earlier two-stream screen hid `0.612-0.642 ms` only when independent MHC
work was resident before communication. A real MHC consumer cannot begin from
an ordinary post-ring dependency: it must already be resident and learn when
individual reduced wire ranges are locally complete. This gate proves the
ring can expose that information without consuming the overlap budget.

This is not yet a decode or collective speed result. The next experiment must
have a second-queue consumer acquire-wait on the epochs, compute canonical MHC
post work per ready wire, converge, then execute canonical MHC pre. It must
preserve bitwise changed-state output and save at least `6 us` per boundary at
the slowest rank before any full-model integration.

Raw evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/ring-markers-smoke-20260715T0352Z.json`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/ring-markers-control-a-20260715T0353Z.json`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/ring-markers-candidate-20260715T0353Z.json`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/ring-markers-control-b-20260715T0353Z.json`.

The tested library SHA-256 is
`eb77b800754754c9f9ede04bff6ab0850a8e82a398c0c23baa2d38a10bbaef3f`.
