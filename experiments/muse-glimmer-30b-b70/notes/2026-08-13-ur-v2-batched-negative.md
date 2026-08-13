# Unified Runtime Level Zero V2 batched queues: startup stall

Date: 2026-08-13

## Rationale

B70 already defaults to Intel's redesigned Unified Runtime Level Zero V2
adapter. V2 normally creates immediate in-order queues. Its experimental
`UR_L0_V2_FORCE_BATCHED=1` mode instead records regular in-order command lists
and appends each batch through an immediate list. In principle, the TP
collective event boundaries could close one batch per subgraph while reducing
the number of lower-level submissions inside each subgraph.

Primary source audit: oneapi-src/unified-runtime commit
`1443d4037f93134b9324484708838fe2a481349f`,
`source/adapters/level_zero/v2/queue_create.cpp` and
`source/adapters/level_zero/v2/queue_batched.cpp`.

## Result

The single 64-token falsification arm did not reach server health. After 2.5
minutes the process was still active but had produced no log progress beyond
model metadata load at startup second 0.9; the normal immediate V2 path reaches
health in roughly 35--45 seconds. No benchmark row was written.

The runner was interrupted once. Its server child exited, the canonical GPU
lock released, and production subsequently reloaded without device recovery or
reboot. There was no evidence of a driver or GuC wedge.

Evidence:

- config:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-ur-v2-force-batched-smoke64.json`;
- empty result file:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/ur-v2-force-batched-smoke64-20260813.jsonl`;
- server log:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-ur-v2-force-batched-smoke64-20260813-v2-force-batched.log`,
  SHA-256 `3b140eb8e9c66f8c94910ac07f36b50565cd6bb179d8e5e2826b03afc13b6917`.

## Decision

Reject and do not retry this mode on the current oneDNN/SYCL stack. V2
immediate in-order queues remain the runtime baseline.
