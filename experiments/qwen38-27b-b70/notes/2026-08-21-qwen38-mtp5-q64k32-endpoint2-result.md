# Qwen3.8 MTP5 Q64xK32 endpoint2 campaign result

Date: 2026-08-22 (campaign of 2026-08-21)

Classification: **stopped terminal at b1: the qualified operator candidate is
not endpoint-deployable as built (kernel-farm coverage), not a policy
performance or correctness rejection.** Per the frozen contract no b2 or a2
ran and no same-root retry is permitted.

Preregistration:
[`2026-08-21-qwen38-mtp5-q64k32-endpoint-prereg.md`](2026-08-21-qwen38-mtp5-q64k32-endpoint-prereg.md).

## Arm a1 (stock control): PASS

Runner exit 0, sealed TP2 gates `passed`, quality battery passed, control
marker count 0, and the bench median reproduced the lane anchor:
**`101.947837`** helper / **`100.928359 tok/s`** conventional. Root
`qwen38-q64k32-endpoint2-a1-20260821` is preserved and usable as the control
anchor for a future endpoint3.

## Arm b1 (first candidate): infrastructure-terminal

The candidate server failed engine-core initialization on both workers with

```text
RuntimeError: Worker failed with error 'Chunk prefill kernel not compiled
for this configuration.'
```

zero engagement markers (the policy dispatch was never reached), runner exit
2, no bench/quality artifacts, root preserved.

**Mechanism.** The candidate stage's `libattn_kernels_xe_2.so` is `607,896`
bytes versus the stock stage's `1,517,994,352` bytes: the isolated,
memory-scoped operator build compiled essentially only the new Q64xK32
translation unit plus dispatch, not the full AOT chunk-prefill configuration
farm. The r2 dispatch predicate itself is exactly scoped (fp16, varlen,
paged, causal, batch 1, `total_seqlen_q==6`, heads 12/2, head 256, block 64,
policy env gated) — but every non-matching shape falls through to the
library's own configuration table, which is empty in the 0.6 MB build. The
operator campaign could never observe this: its candidate arms exercise only
the one qualified shape. First server-side stock-shape call at warmup hit
the hole.

## Disposition and required next steps

1. The r3 **operator qualification stands for the policy** (kernel geometry
   and math), but it binds the exact DSO identity; endpoint deployment
   requires an **integration build**: the full graphfa-composite
   configuration farm plus the Q64xK32 TU and dispatch in one library.
2. After that build: a fresh sealed stage, a fresh (cheap) eight-arm
   operator requalification on the new DSO identity, and only then an
   endpoint3 preregistration reusing this campaign's design and the
   preserved a1 anchor rules (fresh arms throughout).
3. Both endpoint2 roots are preserved; the two infrastructure false starts
   of this campaign (sealed-mode allowlist refusal; vLLM WIP identity
   refusal) are recorded in the preregistration.

The durable lesson, now twice-proven today with the fp-model finding:
**operator-level qualification of an artifact is not deployability** — the
endpoint contract must always re-prove the artifact inside the full serving
identity before any speed claim.
