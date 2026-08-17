# Qwen3.8 27B Q8 TP2 compile-time FFN MMVQ shapes

Date: 2026-08-16

Status: active on the two-ASRock-B70 reference host; do not duplicate unchanged.

## Hypothesis

The accepted reordered-Q8 SG16 kernels receive `ncols`, `nrows`, block counts,
scale-plane offsets, loop limits, and fused-pair matrix dimensions as runtime
arguments. Qwen3.8 repeatedly uses two dominant local TP2 FFN shapes:

- down projection: K=`8704`, N=`5120`, standalone reordered Q8 MMVQ;
- gate/up projections: K=`5120`, N=`8704` plus N=`8704`, fused pair.

These three matrices carry most of the dense model's weight bytes. Dedicated
template instantiations can make their loop bounds, block/scale strides, and
pair boundary compile-time constants while retaining the accepted weight
layout, one-chain integer DP4A order, per-lane FP32 block accumulation, SG16
reduction, launch geometry, and output stores.

This is materially different from the closed fixed-WG128 experiment: that arm
only annotated a workgroup size and left matrix geometry dynamic. It is also
different from row interleaving, two-row activation reuse, DPAS/ESIMD, and
subgroup-count sweeps.

## Contract

- isolated source/build derived from the accepted Qwen3.8 Q8 source stack;
- same binary mode 0 control and an explicit default-off runtime selector;
- specialize only exact admitted shapes; every other shape falls through to
  the accepted kernel unchanged;
- liveness log per device and family plus treatment-scoped poison control;
- normal fixed-shape output must match the accepted oracle; poison must differ;
- first use a bounded `p64/n256/r3` position-balanced screen;
- advance only a repeatable positive result to the complete 12-prompt
  cache-zero oracle, semantic canaries, long-context needle, and health gate;
- build at no more than two jobs under the established 8 GiB host-memory cap.

No claim is made until the candidate compiles, proves reachability and exact
output, and wins a position-balanced measurement.
