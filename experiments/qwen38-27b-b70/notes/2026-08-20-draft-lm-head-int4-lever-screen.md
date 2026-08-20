# Draft LM head INT4: the one open speed lever, op-level screen

2026-08-20. Context: the measuring host closed every flag lever with
engagement proofs (GDN capture −2.2, SPEC_GREEDY_TOP_IDS −2.2,
LOCAL_ARGMAX_DECODE cannot engage under MTP, RMSNorm BI neutral) and
reported the honest margin-free figure: **101.170 tok/s all-25** (median of
three arms; 21-22/25 self-determinism outstanding). Their ranked list
named two unscreened structural candidates: draft-head cost (INT8 today)
and MTP acceptance. This note screens the first at op level on this host.

## Measurement (GPU 0, triple-fix staged build, production TP2-local shape)

LM head GEMM: [M, 5120] × [5120, 124160] (vocab 248320, TP-local half).
Weight-streaming dominated; both kernels sit at the HBM roofline:

| head op | M=1 | M=6 | effective weight BW |
| --- | --- | --- | --- |
| INT8 W8A8 (current draft head; `VALIDATION_LM_HEAD_INT8=1` scope `all`) | 1103.6 µs | 1118.0 µs | 568-576 GB/s |
| INT4 W4A16 (`VLLM_XPU_DRAFT_LM_HEAD_INT4`, off by default) | 553.5 µs | 565.7 µs | 562-574 GB/s |

Activation quant for the INT8 pair is negligible (5.5 µs/call). Saving per
draft head call: **~550 µs**, purely from halved weight bytes; no kernel
risk, both at roofline.

## Step-level projection (MTP5)

- 5 sequential draft forwards per step, each running the head at M=1:
  5 × 1103.6 = **5518 µs** → 5 × 553.5 = **2768 µs**. Saving ≈
  **2.75 ms/step**.
- Margin-free 101.170 tok/s at ~3.5 accepted+1 tokens/step ⇒ ~34.6 ms
  step ⇒ saving is ~8% of step time ⇒ **projected ≈ +8 tok/s
  (≈109 all-25)** if acceptance is unchanged.
- Target/verifier head stays INT8 (M=6, once per step) — target-visible
  logits are untouched; visible tokens remain target-verified.

## Why acceptance should hold

`VLLM_XPU_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN`
(vocab_parallel_embedding.py:341-365) recomputes exact fp16 logits
row-selectively for near-tie rows (top1 − top2 < margin) via `F.linear`
against the full-precision weight. With margin set above the int4 logit
error bound (~0.1-0.2 at group 128; measure once server-side), draft
argmax tokens become nearly bitwise-identical to the fp16 head — strictly
*more* faithful than today's unrepaired INT8 head (error ~0.079 per logit,
~0.112 on the gap, unrepaired). Acceptance rate should be unchanged or
slightly better. The int4 head weight is derived at load time ("Prepared
experimental XPU INT4 draft lm_head" log); no checkpoint change.

## Interaction with today's determinism fixes

- Draft head INT4 at M=1..6: swept bitwise deterministic today (0/100 per
  width, `2026-08-20-decode-path-determinism-audit.json`, draft head
  5120×37984; the N=124160 shape is the same kernel family at roofline —
  re-sweep at the real shape server-side or op-level before promotion).
- Prefill widths landing in the int4 dirty band [129,448] are padded by
  the determinism pad (head included — the pad rule covers all int4 GEMMs
  with 128<M<512).

## What the measuring host should run

1. Baseline arm: margin-free MTP5, triple-fix build, direct-verified model,
   pinned compile cache — this is the determinism reference.
2. Treatment: same + `VLLM_XPU_DRAFT_LM_HEAD_INT4=1` +
   `VLLM_XPU_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN=0.25` (start; sweep
   0.1/0.25/0.5 if acceptance moves).
3. Gates: all-25/selection-12 tok/s, acceptance rate per depth,
   25/25 token-ID self-determinism across two arms, and the Qwen3.8
   target-only quality oracle. Acceptance drop > noise without the margin
   means the margin is too small; with margin ON, draft tokens should be
   near-identical and acceptance flat.

## Caveats

- n=1 op-level screen on GPU 0; per-call times at steady state.
- The +8 projection assumes the draft head runs once per draft token per
  step (5×) — verify against the runner's step structure server-side.
- Does not address determinism by itself; it rides on the triple-fix build
  and the page-cache resolution.
