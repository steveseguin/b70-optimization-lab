# Qwen3.8 official-FP8 TP1 strict target-control preregistration

## Trigger and question

The official-FP8 TP2 target remained nondeterministic after three bounded
causal controls: byte-identical compiled caches, eager graph-off execution,
and eager execution with the lab W8A16 dispatch disabled. The default-off
eager TP2 pair matched only `8/12` complete outputs.

Does the same official-FP8/default-dispatch/eager target reproduce all 12
complete outputs when tensor parallelism and cross-rank collectives are
removed?

## Frozen one-card profile

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- exact `f01e-kernel-1e90-w8a16-r122` image with the W8A16 environment gate
  omitted, one B70 (`ZE_AFFINITY_MASK=0`), TP1, MTP0, FP16/auto KV;
- eager execution, graph and compilation disabled, 0.96 GPU-memory budget,
  1,024-token capacity, one sequence, and 1,024 max batched tokens;
- two fresh containers and new empty non-prompt cache directories;
- unchanged full 12-prompt/six-class/512-cap/cache-zero workload and post-suite
  objective canaries.

The 1,024-token shape is not a fit gamble: the prior pinned-image TP1 eager
campaign established an 8,448-token service capacity. It is still a distinct
one-card operating profile and cannot inherit TP2 speed or quality evidence.

## Decision

Require both attempts to pass the workload/canary gates and match `12/12`
complete token arrays. If TP1 passes while TP2 default-off eager remains
`8/12`, TP2/cross-rank execution is required on this observed instability
surface. If TP1 also fails, TP2 is not required and diagnosis remains inside
the one-rank official-FP8 target/runtime path.

This control has no authority to fill the TP2 headline, MTP1 32K, or any
aggregate cell. Preserve failures; do not weaken equality or replace the full
suite with a shorter diagnostic.
