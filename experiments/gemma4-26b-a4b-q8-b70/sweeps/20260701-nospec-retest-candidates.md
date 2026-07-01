# 2026-07-01 No-Spec Retest Candidate Audit

Status: audit note. This lists recent Gemma 26B Q8 results that were closed or
down-ranked while their measured movement was inside the current MTP
same-recipe non-confidence band (`~4.4%` p90 pairwise delta). The new no-spec
calibration lane can resolve only target-side runtime changes; it cannot judge
MTP/verifier-only changes.

## Retest With No-Spec Calibration

These are target-side changes, so disabling MTP/speculation removes unrelated
pipeline variance while still exercising the changed code.

| Candidate | Prior readout | Why retest |
| --- | ---: | --- |
| Per-layer post-norm residual fusion (`LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`) | `+0.87%` average primary, GPU-pair-dependent | Clean target-side graph fusion; small positive is invisible in MTP noise. |
| Attention post-norm residual fusion (`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1`) | `-2.18%` primary, `+2.30%` full-output | Primary loss and full-output win disagree; no-spec can tell if the target graph itself improved. |
| Final + attention + per-layer norm combo | `-0.03%` average primary | Exact tie under MTP. Lower priority than testing individual flags, but eligible. |
| Packed GEGLU all (`LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE=all`) | `-1.54%` average primary | Correctness-safe target MoE path; small negative could be MTP/scheduler variance. |
| VDR2 selected-down rowpack=2 | strict128 `+0.52%`; full512 primary `-3.34%`; full512 after-TTFT `+1.96%` | Mixed early/full-output signal, all inside noise. Needs patch reapplied, but it is a strong service/target-kernel retest candidate. |
| LM-head Q8 one-column subgroups (`16`, maybe `2`) | `16` near-tie; `2` had best candidate screen but no same-GPU control advantage | Launch-geometry target-side patch. Current evidence is not paired enough; no-spec calibration should be cleaner. |
| UBATCH/BATCH `1152/1152` | pre-finalpost full512 `+2.67%` vs controls; post-finalpost average `-3.90%` | Config-only target/runtime shape. Lower priority because the latest promoted-stack screen was worse, but no-spec can settle whether target decode likes it. |

## Service / Prompt-Processing Retest, Not Short-Record Retest

These are real target-side ideas, but they mainly affect prompt processing or
long-context service behavior. Use long-context/no-spec service gates, then
rerun the normal short MTP guard.

| Candidate | Prior readout | Retest condition |
| --- | ---: | --- |
| GQA8 middle ubatch balance (`UB1280`) | long prefill `+3.8%` over UB1024, short decode `118.73` vs `123.68` record | Retest only for balanced service/default, not short headline. |
| KV-min/SWA left-bound family | long prefill `+4.7%` to `+6.1%`; short guard deltas around `-1.3%` to `-1.9%` for early variants | Continue only in prompt-processing lane; no-spec short calibration can help prove no decode regression. |
| Host-derived SWA left-bound (`MIN_Q=2048`) | service-lane win with short guard flat/positive | Already more promising than mask-scan KV-min. Keep as service lane, not LocalMaxxing short headline. |

## Do Not Retest With No-Spec Calibration

These are MTP/speculation/verifier-only or clearly large losses. No-spec would
disable the changed path or fail to answer the question.

| Candidate | Prior readout | Reason |
| --- | ---: | --- |
| Accept-prefix argmax prototype | `-6.99 tok/s` vs same-build control | Verifier/MTP-only and a large loss. |
| Accept-prefix v2 multirow mask | `-17.72 tok/s` vs control | Verifier/MTP-only and a large loss. |
| Late-head fused SPEC_HEAD | `-6.78 tok/s` vs control | Verifier/MTP-only. |
| `p_min` threshold gap screen | candidates below matching `p_min=0.0475` controls | Speculation policy; no-spec disables it. |
| GEGLU down matmul epilogue current flag | `-38` to `-42 tok/s` vs controls | Large target-side loss, not a variance-class result. |

## Suggested Order

1. Run no-spec paired A/B for per-layer post-norm fusion and attention
   post-norm fusion, because they are already built, default-off, and cheap.
2. Run packed GEGLU all in no-spec calibration; close it for good if it remains
   neutral/negative.
3. Reapply rowpack=2 and test no-spec only if service/full-output remains a
   priority.
4. Revisit LM-head subgroup `2`/`16` only after the source patch is confirmed
   present and the no-spec wrapper records the knob cleanly.

If a candidate shows a no-spec target-side win, it still must pass the normal
MTP realistic final gate before promotion or LocalMaxxing submission.

## Paired No-Spec Results

Generated artifacts:

- `data/gemma4-q8-nospec-attnpost-ab-20260701T140828Z.json`
- `data/gemma4-q8-nospec-attnpost-ab-20260701T140828Z.md`
- `data/gemma4-q8-nospec-packedgeglu-ab-20260701T140828Z.json`
- `data/gemma4-q8-nospec-packedgeglu-ab-20260701T140828Z.md`
- `data/gemma4-q8-nospec-postnormcombo-ab-20260701T140828Z.json`
- `data/gemma4-q8-nospec-postnormcombo-ab-20260701T140828Z.md`
- `data/gemma4-q8-nospec-lmheadsg2-ab-20260701T140828Z.json`
- `data/gemma4-q8-nospec-lmheadsg2-ab-20260701T140828Z.md`

All analyzed runs passed the fixed realistic final gate with `cached_tokens=0`.
The no-spec calibration resolved the target-side candidates as follows:

| Candidate | Median paired ratio 95% CI | Decision | Action |
| --- | ---: | --- | --- |
| Attention post-norm residual fusion | `+0.431% / +0.804% / +1.119%` | `inconclusive_positive` | Target-side positive but below the `+1%` lower-bound promotion rule. Do not submit. If revisited, use one MTP same-window A/B only, not config roulette. |
| Final + attention + per-layer post-norm combo | `+0.744% / +1.014% / +1.292%` | `inconclusive_positive` | Strongest no-spec signal, still below the `+1%` lower-bound promotion rule. Eligible for one controlled MTP confirmation window because it may stack with the promoted final-postnorm path, but not a standalone claim. |
| Packed GEGLU all | `-1.046% / -0.858% / -0.570%` | `no_win` | Closed negative. Do not retest for short decode. |
| LM-head one-column `SUBGROUPS=2` | `-0.649% / -0.338% / -0.073%` | `no_win` | Closed negative. Do not retest the LM-head subgroup/DMMV/no-reorder family unless the kernel shape changes. |

Interpretation: no-spec calibration is doing its job. It can detect sub-1%
target-side changes with much lower variance than MTP full512, but the promotion
rule remains conservative. The only candidate worth a bounded short-record
follow-up is the post-norm combo, and even that must beat same-window MTP
controls clearly before it can affect the promoted recipe.


## MTP Follow-Up

The only eligible bounded follow-up from this no-spec batch was the final +
attention + per-layer post-norm combo. It was tested in a four-GPU same-window
MTP full512 window and remained **not promotable**:

- controls: `116.787`, `113.962` tok/s;
- combo-on: `117.227`, `115.861` tok/s;
- paired median-ratio 95% CI: `-2.754% / +0.395% / +3.346%`;
- all lanes passed the fixed realistic final gate with `cached_tokens=0`;
- absolute medians stayed below the current `124.97714084813418 tok/s` record.

Evidence: `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-postnormcombo-mtp-followup.md`.
