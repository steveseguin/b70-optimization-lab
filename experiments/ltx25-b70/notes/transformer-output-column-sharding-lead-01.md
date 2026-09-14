# Larger sampler lead: split linear outputs, preserve full reductions

2026-09-14. Research queue only. No implementation, native call, numerical
qualification or speed estimate. The current encoder ownership and C++
dispatch qualification stay ahead of this lead.

Saved confirmation events place about3.54s in the two samplers. The current
`ltx_layer_shard.py` assigns consecutive blocks21/27 to GPU0/1. Each block
depends on the preceding block, so that arrangement solves weight residency
without making one block's computation parallel across those cards. This is
also identified in the existing [plan](../PLAN.md).

Investigate an output-channel partition of selected native linear operations
across those same two GPUs. Each partition would consume the complete original
input/reduction dimension and its original contiguous rows of the weight
matrix. Concatenate the output partitions in their original order before the
unchanged attention, normalization or activation. Launch independent work on
both devices before waiting for the required combined output.

Do not split the reduction dimension and sum partial products: that introduces
a different floating-point reduction. Preserving the full reduction dimension
is necessary for this proposed gate, but **does not prove byte equality**.
Changing output width/layout may select a different vendor GEMM algorithm or
tile shape. The hypothesis must first pass actual native operation parity on
representative stage1/stage2 shapes and several nontrivial inputs; a CPU
algebraic demonstration cannot establish XPU equality.

Before implementing a full block, measure the matched linear operations and
all required input/output transfers. Communication, synchronization and extra
launches can outweigh parallel execution. Native tests need explicit parameter
ownership, memory accounting and restoration; no weight precision change,
additional GPU workload, reserve override or power setting change. Keep
initialization costs separate. Full-block and four-output clip byte gates
remain mandatory before any speed claim.

Packet10 source identity for the current layer placement:
`source/scripts/ltx_layer_shard.py`, SHA256
`0c836c2c19ef678360c4e5dddb09173d60e0fd011e44430370485abd63336d3b`.
The observed timing inputs are preserved in
`data/na-axis-confirm-timing-attribution-01.json`. Neither proves the proposed
partition is feasible or faster. This note preserves the lead for a later
bounded experiment, not a scheduled application reload.
