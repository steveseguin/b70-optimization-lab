# Draft LM head INT4: the one open speed lever, op-level screen

2026-08-20. Context: the measuring host closed every flag lever with
engagement proofs (GDN capture −2.2, SPEC_GREEDY_TOP_IDS −2.2,
LOCAL_ARGMAX_DECODE cannot engage under MTP, RMSNorm BI neutral) and
reported the honest margin-free figure: **101.170 tok/s all-25** (median of
three arms; 21-22/25 self-determinism outstanding). Their ranked list
named two unscreened structural candidates: draft-head cost (INT8 today)
and MTP acceptance. This note screens the first at op level on this host.

## Status correction (same day, measuring host commit ad34b9db4)

**The draft head is already INT4 in the record config**:
`identity.env:38 draft_lm_head_int4=1`, and the server log shows the draft
head prepared in packed INT4 group layout (640x124160, 40 group scales)
while the target head is INT8 (vocab_parallel_embedding.py:94-95 skips INT8
prep for the MTP head when draft-INT4 is on). The ~2.75 ms/step computed
below is therefore **already banked**, not new headroom; the earlier repo
audit line claiming "the draft head is INT8" was wrong.

The actual unscreened variant is the **fallback margin**
(`VLLM_XPU_DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN`, default 0): exact fp16
repair of near-tie draft rows. Its value is acceptance-side (draft argmax
closer to fp16 ⇒ acceptance unchanged-or-better), not cost-side.

**Margin-as-implemented is too slow to enable blindly** (measured on GPU 0
at the real shape, `../data/2026-08-20-int4-fallback-margin-cost.json`):

| component (as written) | cost per draft head call |
| --- | --- |
| `torch.topk(k=2)` over [M,124160] fp32 | **320.8 µs** (full sort on XPU) |
| exact fallback per flagged row: full-vocab fp16 `F.linear` | **2237.7 µs** |

At MTP5 the topk alone is 5 × 321 ≈ 1.6 ms/step — over half of what the
INT4 head banks (2.75 ms/step) — plus 2.2 ms per near-tie event.

**Cheap-margin patch shipped**:
`../patches/vllm-qwen38-draft-head-int4-cheap-margin-20260820.patch`
(vllm tree kept clean; apply to use). Gap via two `max` reductions +
`scatter` (~60 µs, 5.3×); exact repair of ONLY the columns within margin
of top1 (~2 columns; ~50 µs marginal) instead of full-row recompute. With
margin ≥ 2× the int4 logit error bound this is argmax-exact vs the
original full-row repair: validated 40/40 synthetic trials, masks
identical, argmax identical (`qwen38-det-margin_equiv` harness). Fixed
cost at MTP5 ≈ 5 × 60 = 300 µs/step (0.87%) + rare ~50 µs events.

Recommended server screen: margin-free baseline vs
`DRAFT_LM_HEAD_INT4_FALLBACK_MARGIN=0.25` with the cheap patch — compare
acceptance per depth and 25/25 self-determinism, not just tok/s.

The measurements below remain valid as the quantification of what the
record already banks by using draft INT4 instead of INT8.

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
