# Laguna exact QKNorm + RoPE fusion: ABBA crossover inconclusive

Date: 2026-07-22 America/Toronto (completed after 00:00 UTC)

## Result first

The preregistered A-B-B-A crossover produced strong directional evidence that
the exact M=8 Q/K RMSNorm + RoPE fusion reduces target-cycle time, but it did
**not** pass the frozen promotion gates and is **not a record**.

All four fresh starts were bitwise exact against the canonical q=1 teacher
13/13, exact across starts 13/13, cache-zero 13/13, long-then-next exact 2/2,
and rollover exact 1/1. The fusion candidate beat its adjacent control in both
headline and normalized cycle time:

| Leg | Treatment | Median tok/s | Cycle ms | Draft cycles | Accepted |
|---|---|---:|---:|---:|---:|
| A1 | control | 32.942323 | 92.960307 | 1,719 | 4,643 |
| B1 | fusion | 33.440373 | 91.019299 | 1,719 | 4,643 |
| B2 | fusion | 33.302984 | 89.981714 | 1,720 | 4,642 |
| A2 | control | 31.173546 | 93.909673 | 1,720 | 4,642 |

However:

- the per-position DFlash acceptance histograms differed in every paired
  comparison, violating the preregistered identical-speculation-work gate;
- the machine/run drift remained very large, including a 1.768777 tok/s
  difference between the two controls; and
- the candidate's lower start, 33.302983624 tok/s, was 0.135943052 tok/s
  (-0.4065413%) below the approved 33.438926676 tok/s record.

The selector therefore remains default-off. No fifth run was used, no
LocalMaxxing payload was staged, and nothing was submitted.

## Frozen protocol and identity

The protocol was committed before any generation in
`2026-07-22-qknorm-rope-crossover-preregistration.md`. The valid block used:

- order: A1 control, B1 candidate, B2 candidate, A2 control;
- a new server process and fixed 60-second device-free interval per leg;
- vLLM `d503073ec3573c6208cc2a06339815ec040ee984`;
- XPU kernels `9525343e74b1a434b6af7d05583e1385a891c919`;
- the installed binary hashes already recorded by the earlier component gate;
- TP4 + EP4, one active sequence, eager exact target, BF16 KV;
- exact DFlash depth 7, seed 1, `enable_thinking=false`;
- the approved fused-W1/route-W2 and route-interleave stack; and
- fixed suite SHA256
  `9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`.

The only treatment change was:

```text
A: VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0
B: VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
```

An earlier block name, `qknorm-rope-abba-20260723T025538Z`, was invalidated
before service startup because the harness's benchmark-SHA literal omitted its
last character. That zero-generation failure and driver log remain preserved;
the hash was corrected in commit `93f597715`, and the complete block used a
new name.

## Paired performance

| Pair | Headline delta | Cycle delta | Candidate row wins | Median paired delta |
|---|---:|---:|---:|---:|
| B1 vs A1 | +1.511884% | -2.087997% | 12/13 | +2.119627% |
| B2 vs A2 | +6.830911% | -4.182700% | 11/13 | +4.370462% |

Those signs are consistent with the isolated component result, which reduced
144 launches to 48 and improved the repeated component by 1.134039 ms/cycle.
They are useful evidence for retaining the fusion as a future stacking
candidate. They are not promoted as a causal endpoint result because the
frozen work-identity gate failed.

The two matched pairs had equal *total* cycle/draft/accepted counts internally,
but not equal accepted-position histograms:

```text
A1: [1271, 936, 710, 566, 468, 391, 301]
B1: [1272, 938, 710, 566, 467, 392, 298]
B2: [1271, 935, 710, 567, 469, 391, 299]
A2: [1273, 936, 709, 565, 468, 391, 300]
```

This matters because the accepted-length trajectory changes context lengths
and attention work even when total cycles and accepted tokens agree.

## Quality and honesty evidence

All four legs passed:

- teacher token arrays: 13/13;
- cross-leg token arrays: 13/13;
- `cached_tokens=0`: 13/13;
- 512-token long-then-next: 2/2;
- 863-input/512-output rollover: 1/1;
- one fixed unique prompt request per suite row; and
- the fixed realistic final gate.

Combined evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-abba-20260723T030000Z/all-vs-canonical-teacher.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-abba-20260723T030000Z/cross-leg-exactness.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-abba-20260723T030000Z/analysis.json
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-abba-20260723T030000Z/analysis.md
```

Each leg directory contains the benchmark JSON/stdout, server log, full
identity and binary hashes, metrics before/after the suite, teacher comparison,
and post-stop XPU process check.

Tracked compact result:

```text
data/laguna-s-2.1-m8-qknorm-rope-abba-inconclusive-20260722.json
```

## Disposition and next lever

The earlier claim that fusion was simply a speed negative was too strong. The
crossover shows it is plausibly beneficial but still too noisy and too slow in
its lower start to publish. Keep the exact source and binary, leave the flag
default-off, and retest it only as part of a predeclared future stack—not by
selectively adding more starts to this block.

The next bounded experiment is a Laguna-only XPU auxiliary stream for the
complete shared-expert MLP. It preserves the existing BF16 BMMs, SiLU,
multiplication, down projection, addition, and fixed-rank reduction while
attempting to overlap roughly 1.013 ms/cycle with routed expert work. A
component byte-parity/race gate must precede endpoint testing. The smaller
router BF16-load/FP32-sigmoid path remains a roughly 0.25-0.30% fallback.

