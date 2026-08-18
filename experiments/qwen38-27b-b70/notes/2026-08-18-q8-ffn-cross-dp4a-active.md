# Qwen3.8 Q8 shape-selective FFN crossed-DP4A experiment

Date: 2026-08-18

Status: active and claimed on the reference two-ASRock-B70 host; not promoted

## Hypothesis

The previously validated global crossed two-chain DP4A schedule improved the
deep direct decode gate by `0.758%` and the full 512-token endpoint rate by
`0.463%`, but it was neutral on the repository's primary first-100 endpoint
metric. This experiment narrows that exact schedule change to the dominant
dense feed-forward projections:

- fused gate/up pair: `K=5120`, `N=8704+8704`;
- down projection: `K=8704`, `N=5120`.

Recurrent GDN, attention, and output-head Q8 kernels retain the promoted
striped `0->2 / 1->3` DP4A2 schedule. The candidate is materially different
from rerunning the global crossed arm: it tests whether its deep-decode gain
originated in the large dense FFN tensors while avoiding any countervailing
schedule change in the other kernel families.

## Exactness and scope

The treatment regroups four signed-byte DP4A integer partials from the accepted
striped chains to crossed `0->3 / 1->2` chains. Every weight word remains paired
with the same activation word. The four exact `int32` partials are added before
the unchanged FP32 scale and accumulation boundary, so represented weights,
tensor split, KV type, graph, and floating-point operation order do not change.
A runtime door, `GGML_SYCL_MMVQ_Q8_FFN_CROSS_DP4A=1`, selects only the two exact
FFN shapes above; unset or `0` is the control in the same binary.

No speculation, MTP, DFlash, cache reuse, peer write, profiler, PCI policy,
power-management setting, firmware, driver, or kernel setting is involved.
The experiment inherits the accepted Q8 TP2 configuration: equal split,
F16 KV, FlashAttention, `b1024/ub256`, `level_zero:1,0`, `SYCL0/SYCL1`, and
oneAPI 2026.1.1 AOT for `bmg_g31`.

## Planned gates

1. Build the isolated source at
   `/mnt/fast-ai/src/llama.cpp-q38-q8-ffn-cross-dp4a-20260818` with `-j2`
   inside the repository's 6/8 GiB build limit.
2. Run an allocator-bounded TP2 `p0/n1` verifier smoke. Promotion requires the
   runtime door to be visibly reached and `VERIFY_MISMATCH=0`.
3. Run a position-balanced same-binary `p64/n512/r3` control/treatment bracket.
4. Only if the direct result clears ordinary noise, run the fixed unique-prompt,
   cache-zero endpoint oracle and compare complete-output hashes.
5. Record the result, exact patch and binary/library hashes, close this claim,
   then commit and push before selecting another candidate.

Any Xe fault, reset, hang, timeout, device-lost event, host-memory pressure, or
quality mismatch stops the experiment without promotion.
