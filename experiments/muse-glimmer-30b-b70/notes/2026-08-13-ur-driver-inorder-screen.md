# Unified Runtime driver in-order lists: exact, not promoted

Date: 2026-08-13

## Rationale

The installed Intel Unified Runtime defaults to adapter-managed ordering for
the SYCL in-order queues. `UR_L0_USE_DRIVER_INORDER_LISTS=1` requests native
Level Zero in-order command lists instead. This is materially broader than an
individual graph fusion: it applies below oneDNN and native SYCL submissions
without changing model arithmetic.

The upstream Unified Runtime reference defines the flag for this purpose, and
the adapter source enables it only on an explicitly requested in-order queue.
The installed `1.15.38308` driver is newer than the adapter's documented
passing threshold. Source audit reference: oneapi-src/unified-runtime commit
`1443d4037f93134b9324484708838fe2a481349f`,
`scripts/core/LEVEL_ZERO.rst` and
`source/adapters/level_zero/common/platform.cpp`.

## Result

The retained TP4 stack completed an exact 64-token control/candidate/control:

| arm | prose | code | JSON | arithmetic mean |
|---|---:|---:|---:|---:|
| control before | 68.895 | 114.758 | 219.975 | 134.543 |
| driver in-order | 68.995 | 115.101 | 221.065 | 135.054 |
| control after | 69.586 | 115.024 | 219.943 | 134.851 |

Hashes, proposals, and acceptance were identical. Candidate round-time deltas
against the interpolated controls were `+0.204 / -0.092 / -0.243 ms` for
prose/code/JSON, only about `-0.044 ms/round` on the simple class average. The
throughput mean improved `0.265%` against pooled controls, but prose lost to
the interpolation and the effect is at the observed drift floor.

Evidence:

- config:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-ur-driver-inorder-cac64.json`;
- JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/ur-driver-inorder-cac64-20260813.jsonl`,
  SHA-256 `aafc79184e649f4371e3dea8adfb4fac1b0eb72e7f1518986e4523c1ed707ed8`.

## Decision

Do not change the production runtime or spend a full canonical packet on this
signal. Keep it as an exact, unpromoted runtime screen. It is at least two
orders of magnitude smaller than the current functional DDTree century gap.
