# Ornith 1.5 35B-A3B: beta-sigmoid MMVQ epilogue is negative

Date: 2026-08-23 EDT

Status: **CLOSED NEGATIVE — exact, live, and substantially slower**

## Why this Qwen transfer was tested

Ornith 1.5 inherits Qwen3.5's recurrent beta projection. In an MTP1
verification graph, 30 Q4_K `ssm_beta.weight` projections each produce two
columns of 32 FP32 values, followed by a standalone sigmoid before Gated Delta
Net. The post-stack dispatch census therefore exposed 30 removable launches
per verification cycle.

An earlier exact beta-sigmoid/GDN fusion was server-neutral. This candidate
tested a different placement: preserve the stock reordered Q4_K MMVQ reduction
and apply the stock FP32 sigmoid expression as its write epilogue. It writes
directly into the original sigmoid output allocation, avoiding any raw-beta
lifetime extension. A default-off matcher requires the exact 2048-to-32,
two-token `ssm_beta.weight -> reshape -> sigmoid -> GDN` chain, unique consumers,
contiguous FP32 tensors, and no exposed intermediates.

## Bounded result

The fixed-seed 128-token continuation was byte-identical in every arm. Both
candidate forms reported exactly 2,490 live fusions (30 per verification cycle).

| Arm | Generation | Delta vs control |
| --- | ---: | ---: |
| accepted control | `65.2 tok/s` | — |
| sigmoid computed before the leader store | `58.9 tok/s` | `-9.66%` |
| sigmoid inside the subgroup-leader store | `59.4 tok/s` | `-8.90%` |

The second form removed redundant source-level evaluation, but SYCL still
issues the transcendental instruction at SIMD subgroup granularity. MMVQ maps
each output row to a subgroup, whereas the standalone elementwise sigmoid
packs many beta values into each subgroup. Fusing the arithmetic therefore
trades one small launch for far more subgroup-level `exp` issue and loses
decisively.

The full position-balanced and fresh-server screens were intentionally stopped:
both exact candidates were roughly nine percent below the matched control, far
outside run noise. The accepted source and binaries were restored. The
incremental negative patch is preserved as
`../patches/llamacpp-ornith15-beta-sigmoid-mmvq-negative-20260823.patch` so this
producer-side form is not rediscovered. Raw outputs and the structured decision
are under `../data/2026-08-23-ornith35b-beta-sigmoid-mmvq-*`.
