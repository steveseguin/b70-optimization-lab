# Laguna exact QKNorm + RoPE fusion crossover preregistration

Date registered: 2026-07-22 America/Toronto

Status at registration: no crossover leg has been launched.

## Question

The exact M=8 Q/K RMSNorm + RoPE fusion reduced its isolated component from
1.719706 to 0.585667 ms per target cycle and passed 256/256 component checks,
but its earlier two fresh starts had a 3.14% endpoint spread. Those two starts
did not include contemporaneous controls, so they cannot distinguish a fusion
effect from machine/run drift. This crossover tests that causal question.

## Frozen identity

- target: poolside Laguna S 2.1 INT4;
- draft: Laguna DFlash INT4, greedy, depth 7;
- hardware: four Intel Arc Pro B70;
- execution: TP4 + EP4, one active sequence, eager target, BF16 KV cache;
- vLLM source: `d503073ec3573c6208cc2a06339815ec040ee984`;
- XPU-kernel source: `9525343e74b1a434b6af7d05583e1385a891c919`;
- fixed suite SHA256:
  `9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`;
- canonical q=1 teacher:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json`;
- request: seed 1, greedy model policy, `enable_thinking=false`,
  `max_tokens=512`, return token IDs; and
- primary metric: median generated-token throughput for tokens 1-100 after
  TTFT over the fixed 13 unique prompts.

Every leg keeps the approved record stack enabled:

```text
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1
VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0
VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0
LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7
```

The only treatment difference is:

```text
A control:   VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0
B candidate: VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
```

## Frozen order and stopping rule

Run exactly four fresh starts in this order:

1. A1 control;
2. B1 candidate;
3. B2 candidate;
4. A2 control.

Each leg starts a new service, captures metrics before the suite, sends every
fixed prompt exactly once, captures metrics after the suite, runs the teacher
comparison, and stops the service. There is no warm-up generation, prompt
repetition, response reuse, prefix caching, history/ngram acceleration, or
concurrent request. A fixed 60-second device-free interval separates adjacent
legs. No fifth run will be added to rescue either outcome.

Stop the crossover immediately on a source/binary identity mismatch, service
failure, freshness failure, or token-exactness failure. Preserve the failed
leg and classify it; do not silently rerun it under the same leg name.

## Correctness and honesty gates

All four legs must satisfy all of the following:

- the realistic-suite final gate passes;
- 13/13 prompt identities match the canonical teacher;
- 13/13 full returned token-ID arrays match the canonical teacher bitwise;
- `cached_tokens=0` for 13/13 prompts;
- the 512-token long-then-next check passes 2/2;
- the 863-input/512-output rollover check passes 1/1;
- all four legs match one another 13/13; and
- draft count, drafted-token count, accepted-token count, and accepted-token
  position histogram are identical across legs.

Any failure is a hard rejection regardless of speed.

## Predeclared performance interpretation

The existing approved LocalMaxxing record is
`33.438926675602126 tok/s` (`cmrwot89400gqnz014oodtlbp`).

Call the fusion a reproducible endpoint win only if all of these are true:

1. B1 primary throughput is greater than A1, and B2 is greater than A2.
2. In both adjacent pairs (A1/B1 and B2/A2), the candidate wins at least 9 of
   13 prompt rows and the median paired per-prompt percentage change is
   positive.
3. For both adjacent pairs, aggregate request decode seconds divided by DFlash
   draft cycles is lower for the candidate. Because the speculation-work gate
   requires identical counts, this is a like-for-like cycle comparison.
4. The lower of B1 and B2 exceeds both the lower of A1 and A2 and the existing
   approved record.

If exactness passes and the cycle-level effect is repeatable but the endpoint
record gates do not all pass, retain the fusion default-off as a scientifically
supported stacking candidate; do not promote or submit it. If all gates pass,
the lower candidate start is the publishable headline, subject to the normal
payload audit. If the causal gates fail, preserve the result as a negative.

## Pre-launch operational invalidation

The first driver invocation, under block name
`qknorm-rope-abba-20260723T025538Z`, stopped in the fail-closed preflight
before creating A1, starting a service, or sending a generation. The harness's
literal expected SHA256 for `scripts/bench-openai-realistic-suite.py` omitted
its final `a`; the reported actual hash was the already registered correct
hash. The failed driver log is preserved at:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/qknorm-rope-abba-20260723T025538Z/01-A1-driver.log
```

This is an operationally invalid, zero-generation block, not a measured leg.
The hash literal was corrected before launching a newly named complete ABBA
block. No order, gate, source, binary, prompt, or performance criterion changed.
