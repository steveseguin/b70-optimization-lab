# Qwen3.8 Q8 shape-selective FFN crossed-DP4A experiment

Date: 2026-08-18

Status: closed performance-negative; exact, not promoted

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

1. The final isolated source was
   `/mnt/fast-ai/src/llama.cpp-q38-q8-ffn-cross-dp4a-seeded-20260818`. It was a
   reflinked copy of the checksum-verified accepted build, so only `mmvq.cpp`
   was recompiled before the bounded BMG device link. The candidate source was
   byte-identical to the clean reconstruction in the originally recorded path.
2. The allocator-bounded TP2 `p0/n1` verifier smoke visibly reached the exact
   gate/up and down shapes on both devices and ended at `verified=1980` with
   `VERIFY_MISMATCH=0`.
3. The position-balanced same-binary `p64/n512/r3` control/treatment bracket
   completed in `A-B-B-A` order.
4. The treatment failed the direct performance gate, so the fixed endpoint
   suite was correctly skipped.

Any Xe fault, reset, hang, timeout, device-lost event, host-memory pressure, or
quality mismatch stops the experiment without promotion.

## Results

The treatment door was the only runtime difference. Both treatment processes
announced the fused `5120x8704+8704` gate/up pair and the standalone
`8704x5120` down projection on both B70s. Recurrent SG24, attention, and output
head kernels retained the accepted schedule.

| Position | Arm | Decode tok/s |
| ---: | --- | ---: |
| 1 | control | `36.821069` |
| 2 | treatment | `36.752955` |
| 3 | treatment | `36.734964` |
| 4 | control | `36.743819` |

Pooled arm means were `36.782444` control and `36.7439595 tok/s` treatment, a
`-0.104627%` regression. This is resolution-class small but points the wrong
way in a fully position-balanced gate, so no endpoint or semantic-suite run was
warranted.

Artifact identities:

- accepted SYCL library:
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`;
- candidate SYCL library:
  `6a2fd5772a9b41c0d20ad33986428e602ee2221d9cedad0a18460d24d522869d`;
- candidate `mmvq.cpp.o`:
  `6072936c852624fe50a127dbb697cb41edf42b4ff7126b7ccef9c02b3b27eb17`;
- host `llama-bench`:
  `74e7d48905196285f6e7cd8c8d0b20a8e25cf3f4731b1e2f0f5f6c49ad8d8865`.

The exact source increment is
[`q8-ffn-cross-dp4a-negative-20260818.diff`](../patches/q8-ffn-cross-dp4a-negative-20260818.diff).
Structured evidence is
[`2026-08-18-q8-ffn-cross-dp4a-negative.json`](../data/2026-08-18-q8-ffn-cross-dp4a-negative.json).
Raw logs remain under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260818-ffn-cross-dp4a/`.

One preliminary smoke used comma-separated `-dev SYCL0,SYCL1`; llama-bench
correctly produced two independent one-card cases, so that run is explicitly
invalid as TP2 evidence. The valid direct-benchmark spelling is
`-dev SYCL0/SYCL1`; server syntax separately remains comma-separated. This
mistake was caught before timing and is retained in the raw log to prevent a
repeat.

Both GPUs passed the repository post-run health gate. No new Xe/GuC fault,
reset, hang, timeout, device-lost event, or kernel panic occurred.
