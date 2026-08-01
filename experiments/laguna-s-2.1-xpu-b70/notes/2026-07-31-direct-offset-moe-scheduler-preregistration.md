# Laguna direct-offset expert scheduler preregistration

Date: 2026-07-31 America/Toronto

Status: preregistered before source change, build, or device execution.

## Distinct mechanism

Two exact deterministic schedulers are already closed:

- the flattened maximum grid was `0.916350x` the persistent control because
  thousands of empty workgroups scanned and returned;
- the expert-indexed grid improved to `0.974647x`, but every workgroup still
  scanned preceding expert counts to reconstruct its packed-row offset.

The remap stage already computes the exclusive expert prefix offsets in SLM to
place every routed row. This experiment gives the expert-indexed grouped GEMM
those offsets directly. Each workgroup derives `expert_id` from its fixed grid,
reads exactly `offset[expert]` and `offset[expert+1]`, and invokes the unchanged
tile body for that expert. It removes both the persistent atomic/barrier and
the losing candidate's per-workgroup prefix scan without changing expert
grouping, row order, weight reuse, K order, dequantization, BF16 scale, DPAS,
accumulation, or store.

For the component screen, the host creates the same 65-element exclusive
offset vector from the frozen row-count corpus. That isolates scheduler value.
Production integration is authorized only after a component pass and must
have the existing remap kernel emit the same offsets into a preallocated,
fixed-address buffer—no extra launch or host synchronization.

## Gates

1. Build from exact expert-indexed commit `6baa9606700523680b342b2f5fe8b414cbbaa19d`
   with a new default-off selector and separately named GRF128 kernel.
2. Use the same DSO for persistent control and direct-offset candidate on the
   same changed-input physical-transposed-scale W13/W2 corpus. Require 6/6 raw
   BF16 equality, stable 200-warmup/15x40 timing, no shape regression over 1%,
   and at least `1.05x` summed W13+W2 speedup.
3. Stop before vLLM/model integration if the component misses 1.05x. Preserve
   the patch and result as a scheduler negative.
4. A pass authorizes fused-remap integration and topology smoke only. Smoke
   must retain 146/145 target, 14/13 draft, cache-zero, normal acceptance, and
   clean teardown on all ranks.
5. Only a passed smoke authorizes one cold frozen 13-prompt endpoint leg. The
   first valid result stands.

No model, INT4 weights, BF16 KV, speculative width/depth, verification,
sampling, prompts, teacher, cache, metric, retry, warmup generation, graph
capture window, or scoring window may change. No reboot, reset, FLR, driver
reload, or privileged recovery is authorized.
