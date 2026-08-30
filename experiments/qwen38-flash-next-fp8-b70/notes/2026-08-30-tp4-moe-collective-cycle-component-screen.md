# Qwen3.8 Flash-Next FP8 TP4 collective-cycle component screen

Date: 2026-08-30
Status: bit-exact small component win; no endpoint promotion

The decode-like TP4/EP4 gate models one token per rank, four global tokens,
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

This closes an exact, low-risk opportunity but not the model's primary speed
gap. It is smaller than the separate M4 MoE warps-8 component result, which
projects to 5.8--6.1 ms per target step. No runtime source or protected speed
claim changes here. After A25, a source candidate may expose direct-output
reduce-scatter only as an opt-in endpoint arm and must pass the full short/4K
authority, semantic, needle, repeatability, and fresh-start gates.

Structured result:
[`20260830-tp4-moe-collective-cycle-component-screen.json`](../data/20260830-tp4-moe-collective-cycle-component-screen.json)
