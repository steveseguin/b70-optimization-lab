# Laguna TP4 rank-sum plus add-RMSNorm fusion

Date: 2026-07-31 America/Toronto

Status: **preregistered component screen; no model endpoint authorized.**

## Evidence and hypothesis

The exact BF16-KV record is `125.4619731637751 tok/s`; 130 requires about
`1.1 ms` less average verifier-cycle latency at unchanged acceptance. The
target performs 96 fixed-rank BF16 reductions whose materialized result is
immediately consumed by fused add-RMSNorm:

- 48 attention output reductions followed by post-attention normalization;
- 47 MoE output reductions followed by the next layer's input normalization;
- one final MoE output reduction followed by the model's final normalization.

The record implements each exact reduction as a TP4 all-gather, a local
rank-0-to-rank-3 BF16 sum kernel, and then the existing fused add-RMSNorm
kernel. A one-card baseline on the real `[4,12,3072]` and `[12,3072]` shapes
measured a stable-region median near `0.0270 ms` per pair, or `2.59 ms` for 96
pairs. A fused local finalizer has enough measured scope to close the gap if it
removes about `0.0115 ms` per boundary.

This treatment does **not** reduce, combine, capture, or reorder collectives.
The all-gather remains unchanged. It only fuses the local deterministic sum
with its immediately following normalization and removes the intermediate
sum write/read and one device submission.

## Frozen arithmetic

Add a separately named XPU operator for exactly this sequence:

1. load contiguous BF16 `gathered[4,M,H]`;
2. add rank 1 to rank 0 and round to BF16;
3. add rank 2 and round to BF16;
4. add rank 3 and round to BF16;
5. add BF16 `residual[M,H]` with the same BF16 expression as the incumbent
   fused add-RMSNorm and store the updated residual;
6. use the incumbent workgroup mapping, FP32 square accumulation,
   `reduce_over_group`, `rsqrt`, BF16 conversion, and BF16 weight multiply to
   write normalized output `[M,H]`.

The first implementation is narrow: TP size 4, BF16, contiguous tensors,
`1 <= M <= 12`, `H=3072`, aligned vector-width-8 storage, and the current
epsilon. Invalid shapes, dtypes, aliasing, or alignment fail closed. The op is
callable for component testing but no model path selects it by default.

## Gates and stop rules

1. Build the operator in an isolated kernel worktree against oneAPI 2025.3.
   Inspect the source diff, exported schema, ELF dependencies, and hash before
   device execution.
2. On one healthy idle B70, compare the incumbent
   `rank_order_bf16_sum` plus `fused_add_rms_norm` chain against the fused op
   on deterministic changed gathered/residual/weight inputs at `M=12,H=3072`.
   Use fresh processes or balanced arm order, 200 warmups, and at least 15
   timing samples of 100 launches. Require raw-BF16 equality of both normalized
   output and updated residual for every changed input.
3. Stop before model integration if the stable component saving is below
   `0.010 ms` per pair, if timing ordering is unclear, or if any exactness or
   contract check fails. The `0.010 ms` floor represents only `0.96 ms` over
   96 pairs and is already marginal for the 130-tok/s goal.
4. A component pass authorizes a separate default-off model integration and
   endpoint preregistration. Integration must keep exactly 97 target
   all-gather callbacks, 146/145 target graph topology, 14/13 draft topology,
   BF16 KV, width 12 / DFlash 11, the canonical q1 teacher, cached tokens zero,
   one active generation, cold suite, and the first-valid-score rule.

No target/draft/KV precision change, teacher change, prompt change, warmed
generation, retry, metric substitution, collective-count change, reset,
reboot, or privileged recovery is authorized by this component screen.
