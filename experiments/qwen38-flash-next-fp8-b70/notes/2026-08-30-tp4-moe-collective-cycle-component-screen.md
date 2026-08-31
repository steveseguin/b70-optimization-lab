# Qwen3.8 Flash-Next FP8 TP4 collective-cycle component screen

Date: 2026-08-30
Status: bit-exact component result for a nonproduction dispatch shape

The TP4/EP4 gate models one token per rank, four global tokens,
and all 48 MoE layers. Each layer gathers the FP8 activation, FP32 top-k
weights, int32 top-k ids, and FP32 activation scales, then combines the BF16
expert result with reduce-scatter. Every mode passed exact rank-order and
reduce-scatter oracles and retained one output hash through 100 repeated cycles
per process start.

Across three fresh four-rank process starts with 21 timed 48-layer batches, the
slowest-rank median was:

- current allocation-and-final-copy pattern: 748.464 us/layer;
- reused collective buffers with the final copy retained: 736.662 us/layer;
- reused buffers with reduce-scatter writing directly to the final output:
  722.777 us/layer.

The direct-output form was 3.43% below the current-pattern median and projects
to only 1.23 ms per 48-layer target step if the isolated gain transfers. The
initial 11-batch screen showed a larger 9.49% difference, so process-start
variation is material and the three-start bracket governs interpretation.

A28 later proved that this all-gather/reduce-scatter cycle is not the current
single-sequence production decode path. Production enters the routed expert
kernel at M1 and performs a 5,120-byte BF16 allreduce after local expert work;
it does not dispatch M1 to M4 and reduce-scatter on every layer. The measured
component result remains valid for this synthetic collective shape, but its
1.23 ms endpoint projection is withdrawn and it must not be implemented in the
current endpoint. The next relevant collective gate is the exact production
`[1,2560]` BF16 allreduce protocol test.

Structured result:
[`20260830-tp4-moe-collective-cycle-component-screen.json`](../data/20260830-tp4-moe-collective-cycle-component-screen.json)
