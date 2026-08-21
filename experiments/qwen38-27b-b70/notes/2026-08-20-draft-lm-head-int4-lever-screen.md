# Draft LM head INT4: the one open speed lever, op-level screen

2026-08-20. Context: the measuring host closed every flag lever with
engagement proofs (GDN capture −2.2, SPEC_GREEDY_TOP_IDS −2.2,
LOCAL_ARGMAX_DECODE cannot engage under MTP, RMSNorm BI neutral) and
reported the honest margin-free figure: **101.170 tok/s all-25** (median of
three arms; 21-22/25 self-determinism outstanding). Their ranked list
named draft-head cost and MTP acceptance as unscreened structural candidates.
This note first quantified INT8-to-INT4 head cost, then corrected the record
identity and narrowed the live opportunity to margin-assisted acceptance.

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
repair of near-tie draft rows. Its intended value is acceptance-side: it
moves the draft argmax closer to the full-FP16 draft head. That does not
mathematically guarantee unchanged or better acceptance against the
separately quantized target head, so real accepted/drafted counts and
end-to-end throughput remain required evidence.

**Margin-as-implemented is too slow to enable blindly** (measured on GPU 0
at the real shape, `../data/2026-08-20-int4-fallback-margin-cost.json`):

| component (as written) | cost per draft head call |
| --- | --- |
| `torch.topk(k=2)` over [M,124160] fp32 | **320.8 µs** (full sort on XPU) |
| exact fallback per flagged row: full-vocab fp16 `F.linear` | **2237.7 µs** |

At MTP5 the topk alone is 5 × 321 ≈ 1.6 ms/step — over half of what the
INT4 head banks (2.75 ms/step) — plus 2.2 ms per near-tie event.

**The first cheap-margin prototype is preserved but is not TP2-safe**:
`../patches/vllm-qwen38-draft-head-int4-cheap-margin-20260820.patch`
(vLLM tree was kept clean when it was recorded). It replaces the full sort
and full-vocabulary repair with a thresholded candidate repair, but it decides
whether to repair from each TP shard's local top-two gap before the normal
logits all-gather. A global near tie can be split across ranks even when both
local gaps are large, so the 40/40 synthetic single-shard proof does not
authorize a TP2 server run.

The TP-safe diagnostic successor is
`../patches/vllm-qwen38-draft-head-int4-tp-safe-margin-qualification-20260820.patch`.
Every TP rank repairs its approximate local winner plus all local columns
within the margin before the ordinary gather. If every logit's absolute INT4
error is strictly below `margin / 2`, each exact local winner is in its rank's
candidate set; consequently the gathered repaired argmax equals the gathered
full-FP16 argmax. The diagnostic also records gathered approximate, repaired,
and full-FP16 token choices and per-rank candidate/error evidence. It must pass
that real TP2 qualification before any full-25 performance screen. Its dynamic
`nonzero` and selected-column matmul costs are not covered by the original
`~60 + ~50 us` component estimate, so throughput remains empirical.

The measurements below remain valid as the quantification of what the
record already banks by using draft INT4 instead of INT8.

## Measurement (GPU 0, triple-fix staged build, production TP2-local shape)

LM head GEMM: [M, 5120] × [5120, 124160] (vocab 248320, TP-local half).
Weight-streaming dominated; both kernels sit at the HBM roofline:

| head op | M=1 | M=6 | effective weight BW |
| --- | --- | --- | --- |
| INT8 W8A8 (comparison control; the record skips it for the draft head) | 1103.6 µs | 1118.0 µs | 568-576 GB/s |
| INT4 W4A16 (`VLLM_XPU_DRAFT_LM_HEAD_INT4`, off by default) | 553.5 µs | 565.7 µs | 562-574 GB/s |

Activation quant for the INT8 pair is negligible (5.5 µs/call). Saving per
draft head call: **~550 µs**, purely from halved weight bytes; no kernel
risk, both at roofline.

For the corrected TP-safe margin repair, every rank repairs at least its own
local winner on every draft-head call; it is not a rare-fallback path. The
existing selected-column estimate implies an optimistic floor near
`5 * 107.8 us = 539 us` per speculative step, before the unmeasured dynamic
`nonzero`/indexing synchronization. At a roughly 35.3 ms step emitting about
3.6 tokens, break-even therefore needs approximately 0.055 more accepted token
per step (about 1.10 percentage points averaged over five draft positions).
A genuine 1% end-to-end gain needs about 0.092 more token per step (about 1.83
percentage points), before the extra dynamic cost. The server screen must clear
that empirical hurdle; correctness qualification alone does not make it a win.
Reaching `105 tok/s` from the honest `101.170` anchor with this lever alone
would require roughly 0.19 additional accepted token per step, or about 3.9
percentage points averaged across five draft positions, after paying the
optimistic repair cost. This makes the qualification worth doing, but it is a
high acceptance hurdle rather than a projected win.

## Historical INT8-to-INT4 projection (already banked)

- 5 sequential draft forwards per step, each running the head at M=1:
  5 × 1103.6 = **5518 µs** → 5 × 553.5 = **2768 µs**. Saving ≈
  **2.75 ms/step**.
- Margin-free 101.170 tok/s at ~3.5 accepted+1 tokens/step ⇒ ~34.6 ms
  step ⇒ the already-banked saving is about 8% of step time. It is not an
  additional margin-path projection.
- Target/verifier head stays INT8 (M=6, once per step) — target-visible
  logits are untouched; visible tokens remain target-verified.

## Why TP2 qualification comes first

The corrected path repairs every TP shard's approximate local winner and all
columns within 0.25 of it, then lets the normal logits all-gather occur. The
qualification independently computes the full local FP16 head on both ranks,
gathers approximate/repaired/exact logits, and requires every repaired global
argmax to match exact FP16 with observed maximum absolute error strictly below
0.125. It also requires both rank-local repair markers and per-rank proof that
the exact local winner was in the selected candidate set. This establishes the
bounded TP2 argument only; it does not predict agreement with the quantized
target or an acceptance gain. The INT4 head weight is derived at load time
("Prepared experimental XPU INT4 draft lm_head" log); no checkpoint changes.

## Interaction with today's determinism fixes

- Draft head INT4 at M=1..6: swept bitwise deterministic today (0/100 per
  width, `2026-08-20-decode-path-determinism-audit.json`, draft head
  5120×37984; the N=124160 shape is the same kernel family at roofline —
  re-sweep at the real shape server-side or op-level before promotion).
- Prefill widths landing in the int4 dirty band [129,448] are padded by
  the determinism pad (head included — the pad rule covers all int4 GEMMs
  with 128<M<512).

## Authorized next run

Only the bounded TP2 qualification is authorized now: the frozen three-prompt
subset, margin 0.25, smoke and quality disabled, diagnostic full-head/gather
evidence enabled, and the existing sealed cache/model/runtime identity. Its
throughput is invalid because instrumentation computes the full FP16 head,
performs three extra full-vocabulary gathers, copies tensors to CPU, and writes
JSONL. Any missing/malformed evidence, repaired/exact mismatch, maximum error
of 0.125 or greater, cache/source/identity drift, or arm failure stops the
candidate. A full-25 performance campaign requires a separate preregistration,
the passing qualification artifact and SHA, removal of diagnostic overhead,
and a newly frozen production-only source patch. No margin sweep is authorized.

## Caveats

- n=1 op-level screen on GPU 0; per-call times at steady state.
- The historical +8 projection described INT8-to-INT4 conversion that the
  current anchor already uses; it is not available headroom.
- Does not address determinism by itself; it rides on the triple-fix build
  and the page-cache resolution.
