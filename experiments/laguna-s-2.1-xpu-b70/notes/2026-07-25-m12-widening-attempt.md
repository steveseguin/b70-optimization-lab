# Laguna M=12 verifier widening — first attempt, exactness negative

Date: 2026-07-25 America/Toronto

Status: **exactness negative, cleanly isolated. Not promoted. No throughput
claim.** Decode rate remains **93.990 tok/s** measured.

## Why M was being widened

Measured this session: throughput is acceptance (r = 0.999), cycle time is flat
at ~31 ms, and the conditional acceptance chain does not decay (63.9-82.4% at
every depth) while 32.5% of cycles accept zero. The draft's top-2 covers the
target argmax **84.2%** of the time against **72.2%** for top-1, a +12.0 point
gain that the M=8 budget cannot spend: buying width costs depth, and the best
shape inside 8 slots is +1.3% against the +9.7% needed. At M=12 the projection
is +14.3% (~107 tok/s).

## What was built

`VLLM_XPU_LAGUNA_EXACT_MAX_M` (vLLM `724c8c31d`), default 8, bounded 1..16,
driving both the batched-M1 linear guard and the Laguna batched-exact MoE gate.
At the default every gate evaluates exactly as before, so the record path is
untouched. The exactness mechanism in the batched path is a stride-zero BMM
giving each row an independent M=1 GEMM in the batch dimension, which is
M-generic — the 1..8 cap was a contract boundary, not a kernel limit.

## Result: widening the cap alone is not exact

Eager arms, 13 real cold prompts, 128 tokens, `cached_tokens=0`, comparing
token-id hashes. M=8 is already proved exact against the canonical q=1 teacher,
so equality with M=8 would establish M=12 exactness transitively.

| comparison | exact |
| --- | ---: |
| M=8 fused vs M=8 with M8-only fusions off | **13/13** |
| M=8 vs M=12, all else matched | **1/13** |
| M=8 vs M=12, MoE fast paths off (per-row serialized) in both | **1/13** |

The first row rules out a confound: the M8-only fusions (shared elementwise,
QKNorm/RoPE) are bitwise-neutral, so disabling them for the wider arm does not
itself change output. They also carry an init-time contract pinning speculation
to depth 7, which is why they must be disabled at any other width.

The third row is the important one. **Serializing the MoE per row does not
restore exactness at M=12**, so the M-dependence is not confined to the batched
MoE. Something in the attention or verifier path is M-dependent as well.

## What this means for the plan

Widening is still the only measured route to 100 tok/s, but it is not a
guard-relaxation. At minimum it requires finding and fixing the M-dependence in
the attention/verifier path, then re-proving exactness, before the MoE question
is even reached. The earlier estimate of "days" was made before this negative
and should be treated as a floor.

## Next

Localize the residual M-dependence in the attention/verifier path. The eager
arms above isolate it from graph capture and from the MoE fast paths, so a
per-layer parity probe between an M=8 and an M=12 verifier step should identify
the first divergent tensor. `VLLM_XPU_LAGUNA_PARITY_PROBE` already exists for
this purpose.
