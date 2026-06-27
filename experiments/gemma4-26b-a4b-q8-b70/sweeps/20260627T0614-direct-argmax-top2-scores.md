# 2026-06-27T06:14Z Direct-Argmax Top2 Score Channel

## Question

Can the direct-argmax MTP draft path expose enough real confidence signal
(top1/top2 ids and logits) to make deeper fresh-response unrolls useful for the
Gemma 4 26B Q8 target?

This is a follow-up to `20260627T0538-currentstack-mtp-profile.md`, which found
that the promoted direct-unroll path used synthetic confidence
(`avg_top1_p=1.0`, zero gap data). The patch adds a compact score side channel
to `ggml_mul_mat_argmax` so the draft path can return:

- `top1_id`;
- `top2_id`;
- `top1_logit` bitcast into the compact integer record;
- `top2_logit` bitcast into the compact integer record.

The goal is still **>150 tok/s fresh-response**, not warmed/history-accelerated
throughput. All headline rows below use the harness row0 policy with reported
`cached_tokens=0`.

## Patch / Build State

Source tree: `/home/steve/src/llama.cpp-gemma-record-stack`

Primary code changes:

- `ggml_mul_mat_argmax_top2()` / score compact record support in `ggml.c`;
- SYCL top2 compact-output path in `ggml-sycl.cpp`;
- `llama_set_mtp_draft_direct_argmax_ids()` so the driver can disable compact
  output after final eligibility checks instead of trusting raw env state;
- score mode guard now requires the fused assistant output-argmax lane;
- score consumer checks both top1 and top2 logits are finite;
- shape guard restricts the compact argmax op to the 2D RHS shape it actually
  supports.

Patch snapshot should be kept under
`patches/gemma4-26b-a4b-q8-b70/20260627-llamacpp-direct-argmax-top2-scores.patch`.
Harness/env-capture changes are preserved separately under
`patches/gemma4-26b-a4b-q8-b70/20260627-results-harness-direct-argmax-top2-scores-env-capture.patch`.

## Validation Smoke

Run:
`data/gemma4-q8-gpu0-top2scores-smoke-20260627T061436Z`

- target: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- GPU: one B70 (`GPU_INDEX=0`)
- direct unroll: `7`
- score channel: `LLAMA_MTP_DRAFT_DIRECT_ARGMAX_SCORES=1`
- canary: `32/32` rows pass
- fresh row0 after TTFT: `99.2603124608467 tok/s`
- cached tokens: `0`

Interpretation: the score path is runtime-valid, but it is not a speed win by
itself versus the promoted `104.22626983476746 tok/s` record.

After adding robustness fixes, the rebuilt binary passed:

- `data/gemma4-q8-gpu0-top2scores-rebuild-smoke-20260627T063000Z`:
  score path on, canary `16/16`, cached row0 `0`, short diagnostic row0
  `97.39137140758113 tok/s`;
- `data/gemma4-q8-gpu0-top2scores-fallback-no-fastargmax-20260627T063057Z`:
  env requested compact IDs/scores, but `LLAMA_MTP_DRAFT_FAST_ARGMAX=0` made
  the direct path ineligible; server log confirmed `draft_direct_argmax_ids=0`
  and `draft_direct_argmax_scores=0`; canary `8/8`;
- `data/gemma4-q8-gpu0-top2scores-fallback-no-fusedout-20260627T063142Z`:
  direct IDs remained enabled but fused assistant output-argmax was disabled;
  server log confirmed `draft_direct_argmax_ids=1` and
  `draft_direct_argmax_scores=0`; canary `8/8`.

These are safety/guard validations, not record attempts.

## Four-GPU Score-Gated Depth Sweep

Shared setup: current record stack plus top2 score channel, Q8 target, Q4_0 MTP
draft, one model replica per B70, `CANARY_REPEATS=32` (`128` canary rows),
`BENCH_REPEATS=3`, `PROMPT_TOKENS=512`, `MAX_TOKENS=512`, row0 fresh headline
with `cached_tokens=0`.

| Run | GPU | Direct Unroll | Score Gate | Canary | Fresh Row0 Tok/s | Mean Tok/s After TTFT | Cached |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| `data/gemma4-q8-gpu0-top2scores-n8-p070-20260627T061643Z` | 0 | 8 | `p_min=0.70` | pass `128/128` | `67.8348832083336` | `67.52338005453568` | 0 |
| `data/gemma4-q8-gpu1-top2scores-n10-p080-20260627T061643Z` | 1 | 10 | `p_min=0.80` | pass `128/128` | `76.65766144894653` | `76.94228285789569` | 0 |
| `data/gemma4-q8-gpu2-top2scores-n12-p085-20260627T061643Z` | 2 | 12 | `p_min=0.85` | pass `128/128` | `84.58980110621081` | `84.88932061451193` | 0 |
| `data/gemma4-q8-gpu3-top2scores-n12-p090-20260627T061643Z` | 3 | 12 | `p_min=0.90` | pass `128/128` | `79.46361039855266` | `80.59627964538707` | 0 |

Best score-gated row was `n=12, p_min=0.85` at
`84.58980110621081 tok/s` fresh row0. This is valid, but far below the current
fresh record (`104.22626983476746 tok/s`) and nowhere near the `>150 tok/s`
target.

## Interpretation

Status: **valid loss / keep patch for diagnostics, not record path**.

Real top2 confidence did not make deeper direct-unroll MTP economical. The
server logs show long accepted runs in the benchmark rows, but throughput still
falls because the deeper draft/verifier work costs more than the extra accepted
tokens save.

This result strengthens the earlier conclusion: simply increasing MTP depth
cannot reach `>150 tok/s` on this implementation. The next useful work needs to
change the economics, for example:

- reduce verifier target work for speculative rows;
- avoid or fuse more target MoE/LM-head work while preserving exact greedy
  validation;
- make the draft path substantially cheaper, not merely more selective;
- use a fresh-valid speculation source that can predict multiple tokens without
  learning from previous benchmark repeats.

Do not submit these results to LocalMaxxing. They are fresh-valid but not
records.
