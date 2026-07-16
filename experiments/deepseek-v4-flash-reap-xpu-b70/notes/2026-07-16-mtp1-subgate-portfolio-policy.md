# MTP1 sub-gate portfolio policy and first crossover

Date: **2026-07-16**

Status: **method validated; first bundle positive but not promoted**

## Decision

The `0.50 ms/cycle` integration threshold now applies to a predeclared,
compatible optimization portfolio, not necessarily to every exact component
in isolation. This is the supported way to evaluate small improvements without
lowering the gate or benchmark-shopping.

The first portfolio combined:

1. M=2 fused QNorm/RoPE/direct-FP8-KV insertion; and
2. the ordered N128 small-M MXFP4 verifier policy.

The same-binary B-A-B crossover was positive, but neither bundle run exceeded
the qualified **63.349928 tok/s** record. Keep the record recipe at M=1 for the
QNorm selector and N64 for MXFP4. No LocalMaxxing submission was made.

## Portfolio admission rule

A bundle may receive a TP4 service load only when all of the following hold:

- every component preserves the frozen model, target verification, speculative
  semantics, and one-active-generation benchmark contract;
- every changed boundary has changed-input eager and fixed-address graph-replay
  correctness evidence;
- components are source-compatible and do not duplicate the same projected
  saving;
- the sum of conservative measured lower bounds is at least `0.50 ms/cycle`;
- known service regressions and collective-interaction risks are excluded;
- the variants are frozen before the service results are revealed; and
- the comparison uses one portfolio binary with component flags, in B-A-B
  order, with fresh cached-zero strict suites.

A bundle can establish that sub-gate changes add up, but promotion still
requires a new qualified record, exact canaries, and the normal reproducibility
and quality gates. One favorable row is not sufficient.

## Frozen portfolio identity

- vLLM: `4a6fd874725312c53883b1d53970af1d0eccfc3f`;
- XPU kernels: `3e600bf5dc8c96ca5a1bc4156c78cf7c10c08b36`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- XPU branch: `codex/deepseek-v4-m2-portfolio`;
- QNorm bundle flag: `VLLM_XPU_V4_FUSED_QNORM_ROPE_KV_INSERT_MAX_M=2`;
- MXFP4 bundle flag: `VLLM_XPU_MXFP4_SMALL_M_N=128`;
- control values: QNorm maximum M=1 and MXFP4 N64.

The clean rebuild produced package-identical artifacts:

- `_xpu_C.abi3.so`: `d24308602f8360771aff5c66ffcf7202d763a3b95a56c4cef3bca20833910be6`;
- `_moe_C.abi3.so`: `490f687d9fae4747d4e2477c9293ec5458e12c8584c2a38c21ba0272acfaed01`;
- `libgrouped_gemm_xe_2.so`: `9184bcd85b91fc5b92fe4f61c0458123e139c8235742484be5aee3aae95fc1a3`.

## Hardware gates

The prior M=2 QNorm gate passed 40/40 changed eager inputs and 8/8 graph
replays on each B70. It projected `1.68-1.90 ms/cycle` saved over 43 layers.

The portfolio rebuild repeated the N128 gate on all four cards. Every card
passed 48/48 bitwise-exact route cases. Projected savings versus N64 were:

| Physical B70 | Saved ms / 43 layers |
| --- | ---: |
| 0 | 0.3111 |
| 1 | 0.2782 |
| 2 | 0.2961 |
| 3 | 0.2677 |

The measured combined range is therefore approximately `1.95-2.21 ms/cycle`.
This clears the portfolio gate even though N128 does not clear it alone.

Raw N128 summaries are in
`../../../data/deepseek-v4-reap-m2-portfolio-20260716/`.

## Same-binary service crossover

All three suites used the fixed 12-prompt realistic suite once per prompt,
returned token IDs, generated 128 tokens, and reported zero cached prompt
tokens.

| Order | Variant | Median tok/s | p10 tok/s | Mean tok/s |
| --- | --- | ---: | ---: | ---: |
| B1 | QNorm M2 + N128 | 62.446116 | 59.707219 | 62.918715 |
| A | QNorm M1 + N64 | 61.895036 | 58.898587 | 62.193886 |
| B2 | QNorm M2 + N128 | 62.767570 | 59.935732 | 63.137313 |

The two bundle medians average **62.606843 tok/s**, `+0.711806 tok/s` over
the same-binary control. Their p10 average is **59.821475**, `+0.922888` over
control. The direction is positive, but both bundle medians remain below the
63.349928 record. This is useful evidence for the portfolio method, not a
promotable speed record.

Raw service evidence:

- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-portfolio-qnorm2-n128-screen-20260716TportfolioB1`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-portfolio-control-qnorm1-n64-20260716TportfolioA`;
- `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/mtp1-m2-portfolio-qnorm2-n128-confirm-20260716TportfolioB2`.

After B2, 10/10 ordered exact capture suites passed: 60/60 expected answers,
all cached-zero.

## What this changes

Do not discard exact micro-wins solely because each is below `0.50 ms`. Keep a
portfolio ledger and combine only compatible candidates whose conservative,
non-overlapping lower bounds clear the threshold. Do not revive candidates
with negative service evidence merely to inflate the projected sum.

The next useful portfolio should add a newly measured exact component to this
method, then repeat a frozen same-binary crossover. The present two-component
bundle is closed below the record and should not be rerun until another
non-overlapping component materially raises its conservative ceiling.
