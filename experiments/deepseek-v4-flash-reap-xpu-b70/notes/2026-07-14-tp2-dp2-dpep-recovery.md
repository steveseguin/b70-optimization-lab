# TP2+DP2+EP4 XPU DPEP Recovery

Date: 2026-07-14

## Outcome

TP2+DP2+EP4 now produces correct native DeepSeek V4 K160 output on four B70s,
but none of the safe collective paths is remotely competitive. The best fresh
64-token screen was `2.495917 tok/s` after TTFT, versus the valid TP4 frontier
of `33.433875 tok/s`. Close this topology as a performance lane until there is
a true fast crossed-communicator implementation.

This work is still important: it localizes the original stall to oneCCL's
fast-SYCL handling of alternating disjoint TP pairs and crossed DP pairs. vLLM's
rank construction, device binding, and DPEP tensor semantics are not the root
cause.

## Fixed construction

- Model: `0xSero/DeepSeek-V4-Flash-180B` K160 revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`.
- Runtime branch: `/home/steve/src/deepseek-v4-vllm-clean`.
- XPU kernels: `fa530f5fe9a95cf06251f3af7c1c8cb9a0d76846`.
- Topology: TP2, DP2, EP4, rank-to-device `0,1,2,3`.
- TP groups: `[0,1]`, `[2,3]`; crossed DP groups: `[0,2]`, `[1,3]`.
- Manual FP8 KV allocation: 64 MiB/card, 160 tokens.
- Model memory: about 26.65 GiB/card.
- Eager execution and synchronous scheduling were used to isolate collectives.

## Root-cause sequence

1. The original equal-size XPU `all_gatherv` incorrectly passed a one-element
   output list to `dist.all_gather`. Commit `baf52ea19` changed it to
   `all_gather_into_tensor`; commit `143b90182` padded uneven rows before the
   same tensor collective.
2. Byte-alignment, mixed-dtype packing, and serialized-metadata attempts
   (`88f1afca7`, `7990eda2e`, `3dab8a600`) either lost the device during profile
   or still stalled. Each attempt was preserved and then reverted by
   `cf8cc6974`, `7b87d361f`, and `f47ec156b`.
3. Commit `0ed491252` added a byte-exact CPU/Gloo bootstrap: one packed D2H
   transfer, a Gloo gather/reduction, and one H2D transfer. This returned exact
   `42` and proved DPEP tensor construction was correct. A console 64-token
   screen reached only `2.484515 tok/s` after TTFT.
4. Commit `ae19c7b3b` emulated gather/reduce-scatter with device all-reduces.
   It stalled. Standalone probes in
   `../scripts/probe-xccl-crossed-subgroups.py` showed each communicator works
   independently, including vLLM's subgroup creation order.
5. The remaining cycle was communicator switching: one rank could enter the
   crossed DP communicator while its peer still waited in a disjoint TP
   communicator. Local synchronization (`d18ce5d0d`) was insufficient.
   A global Gloo rendezvous plus device fence before and after every DPEP
   exchange (`0f0b1ff13`) returned exact `42`, proving the dependency cycle,
   but a console 64-token screen reached only `2.221380 tok/s`.
6. Commit `5e02991f3` exposed a no-barrier native lane. With global
   `CCL_ENABLE_SYCL_KERNELS=0`, exact `42` passed and the first fresh 64-token
   row reached `2.466376 tok/s`; two-row support median was `2.494586 tok/s`.
7. The final no-rebuild split kept fast-SYCL eligible for TP all-reduce while
   forcing only `CCL_ALLGATHER=naive`, `CCL_ALLGATHERV=naive`, and
   `CCL_REDUCE_SCATTER=naive` through generic schedules. Exact `42` passed,
   cached tokens were zero, and the fresh 64-token row reached
   `2.495917 tok/s`. Generic per-layer DPEP remains the dominant cost.

## Evidence

- CPU/Gloo correctness bridge:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp2-dp2-ep4-cpu-dpep-eager-20260714T2034Z`
- Global-rendezvous native path:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp2-dp2-ep4-switch-rendezvous-eager-20260714T2049Z`
- Globally generic native path:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp2-dp2-ep4-generic-ccl-native-eager-20260714T2130Z/screen-64x2.json`
- Fast-TP/generic-DPEP path:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/tp2-dp2-ep4-fasttp-genericdpep-eager-20260714T2103Z/screen-64x1.json`
- Structured summary: `../data/tp2-dp2-dpep-recovery-20260714.json`.

## Decision

Do not spend time tuning generic `naive` versus `ring`; the result is more than
12 times slower than the TP4 record. Do not enable the CPU, all-reduce,
rendezvous, or native diagnostic paths by default.

A credible retry requires one of:

- oneCCL fast-SYCL scratch, IPC pointers, barriers, and counters made
  communicator-scoped;
- a dedicated fused XPU DPEP transport that combines routing metadata and
  hidden-state exchange without alternating global communicator state; or
- enough MoE compute/collective fusion to amortize one crossed exchange over
  multiple layers, if the model semantics permit it.

Until then, resume the strict TP4 W8A8/selective-W8A16 lane and attack producer
quantization plus the ordered collective producer/consumer boundary.
