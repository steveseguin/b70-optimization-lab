# DSpark M7 IPC + DPAS Bundle Closure

Date: **2026-07-18**

Status: **exact component improvement; endpoint rejected**

## Outcome

The complete fixed-M7 experiment is closed as an endpoint loss. A new Xe2
BF16 DPAS kernel makes the real sharded DSpark W2 projection bit-exact and
1.68x faster in isolation. The combined transaction removes the base-logit
gather, seven Markov-bias gathers, Python loop, generic embeddings, and
intermediate token copies. It is exact on all ranks and reduces the seven-stage
block from **1.520 ms to 0.526 ms**, saving **0.994 ms**.

That saving does not survive the actual PIECEWISE endpoint. The strict cold
suite reaches only **67.227723 tok/s**, versus the unchanged record of
**80.820052 tok/s**. All 12 realistic prompts are unique and cache-zero, and
the ordered exact canaries pass 12/12 before and after the suite. This is a
runtime rejection, not a correctness failure. No LocalMaxxing submission was
made.

## What was built

1. `deepseek_markov_m1_bf16_dpas_out` uses Xe2 XMX/DPAS on an offline-packed
   contiguous `[256,32320]` BF16 W2 shard. Real checkpoint outputs and final
   argmax tokens are bit-identical to oneDNN. TPI=2 measures **64.872 us ->
   38.642 us**, a **1.679x** speedup.
2. A token-addressed DPAS variant reads W1 directly from the device token,
   eliminating the generic embedding kernel and intermediate vector.
3. `dspark_tp4_markov7_event_out` executes all seven dependent stages through
   one native call, uses local base-logit partitions, consumes seven unique
   one-shot Level Zero IPC events, and writes winners into the draft buffer.
4. vLLM reserves seven events atomically, computes the local LM-head partition
   without gathering full logits, and keeps the candidate default-off behind
   an eager graph break.

The first service integration exposed that vLLM's anchor token is `int32`
while generated tokens are `int64`. The native DPAS loader now consumes either
type directly. A four-card changing-anchor gate proved exact `int32` behavior
before restart.

## Why the endpoint loses

The Level Zero event primitive is fast only as isolated transport. In the real
breakable graph, one-shot reservation, native command-list appends,
queue-to-Level-Zero event wrapping, and the eager segment remain a costly
synchronization boundary. Bundling improves the rejected standalone-event
endpoint from **65.627712** to **67.227723 tok/s**, but does not recover the
promoted collective/graph path.

Preserve this as evidence against predicting endpoints from favorable native
microbenchmarks. The DPAS arithmetic is reusable; this one-shot event
architecture is not. Do not reload this lane without reusable fixed-address
command lists or a whole-cycle gate that includes graph breaks.

## Evidence

- W2 DPAS: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-markov-w2-dpas-20260718Tresume/summary.json`;
- pre-DPAS bundle: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-markov7-ipc-bundle-20260718Tresume2/summary.json`;
- final component: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-markov7-direct-anchor-20260718Tresume/summary.json`;
- `int32` gate: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-markov7-int32-anchor-20260718Tresume/summary.json`;
- dtype-failure endpoint: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-ipc-bundle-dpas-candidate-20260718T2030Z`;
- final endpoint: `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-ipc-bundle-dpas-candidate-20260718T2040Z`;
- vLLM `80f1ad820706103d11f095c8a97e42c624c8bad3`;
- XPU kernels `585a4bc105f73407414c40461adcc60ac6311eb0`;
- oneCCL `48fda4f0e074db005596d6899d5227d3f0316c12`.

## Decision

Keep the exact DPAS source and all negative evidence, but leave the bundle
default-off. The next boundary must delete collective or device work without a
new cross-GPU synchronization architecture.
