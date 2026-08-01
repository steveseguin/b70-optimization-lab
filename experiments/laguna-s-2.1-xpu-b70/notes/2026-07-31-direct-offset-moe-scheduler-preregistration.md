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

## Result

Status: **closed exact component negative; do not integrate or endpoint-run.**

The candidate source is kernel commit
`fabf61f6dd5ea95157db7b1401543ce2c8586480`. The sealed DSO is
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/builds/direct-offset-fabf61f/libgrouped_gemm_xe_2.so`
with SHA-256
`9690f49d531e0fb6149ae37a33cac0f41533124d4d862d2c8b4db753cf5157a8`.
The build completed in 16:42.97 with 106,881,836 KiB maximum RSS and zero
swaps.

Static BMG inspection found the intended separately named 128-GRF kernel. It
retained the exact arithmetic body (2 DPAS and 32 BF16 multiplies). Its final
ISA had 562 instructions and 2/3 spill store/load flags, compared with 679 and
4/5 for the persistent transposed-scale control. That justified measurement,
but did not predict runtime value.

The frozen changed-input component gate used one B70, the same DSO for both
arms, 200 warmups, 15 samples, and 40 launches per sample:

| shape | persistent control | direct offsets | speedup |
| --- | ---: | ---: | ---: |
| W13 | 0.320920100 ms | 0.344646275 ms | 0.931158x |
| W2 | 0.183373325 ms | 0.197750650 ms | 0.927296x |
| sum | 0.504293425 ms | 0.542396925 ms | **0.929750x** |

All six changed-input raw-BF16 comparisons were bitwise exact. Performance
missed the preregistered `1.05x` gate by a wide margin, so production remap
integration and endpoint measurement are forbidden by this experiment.

The durable lesson is that fewer scheduler instructions and fewer compiler
spill markers did not translate to lower latency. On these small, sparse MoE
shapes, replacing the persistent work distributor with a fixed expert grid
cost about 7%. Supplying prefix offsets removed the losing prefix scan from the
earlier expert-indexed candidate, yet made that candidate only marginally
different (`0.974647x` to `0.929750x`) and did not recover the persistent
scheduler. Future scheduler work must preserve dynamic compact work
distribution; another fixed grid over all 64 experts is not justified.

Raw result:
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/direct-offset-component-fabf61f-20260801T065500Z/summary.json`.
