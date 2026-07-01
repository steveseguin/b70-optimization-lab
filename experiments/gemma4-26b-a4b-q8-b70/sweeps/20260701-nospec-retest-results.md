# 2026-07-01 No-Spec Retest Results

Status: diagnostic target-side calibration, not a headline throughput claim and
not a LocalMaxxing submission.

This retest pass used the no-spec calibration wrapper:

- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-nospec-calibration.sh`
- stamp: `20260701T140828Z-nospec-retest`
- model: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- hardware shape: one model copy per B70, four independent lanes
- spec/MTP disabled by wrapper
- prompt/KV cache accelerators disabled with `--parallel 1 --cache-ram 0 --ctx-checkpoints 0`
- fixed realistic suite, each prompt once, `cached_tokens=0`
- primary metric: median generated tok/s for tokens 1-100 after TTFT

The goal was to retest target-side candidates whose prior MTP movement was
inside the current noisy band, using a lower-variance no-spec lane. These
numbers are useful for ranking target runtime work; any positive candidate must
still pass the normal MTP final gate before promotion.

## Summary

| Candidate | Validity | Paired median ratio 95% CI | Readout |
| --- | --- | ---: | --- |
| Attention + per-layer postnorm combo | all runs valid | `+0.744% / +1.014% / +1.296%` | Best candidate. Strong diagnostic target-side win; retest under MTP. |
| Attention postnorm only | all runs valid | `+0.431% / +0.804% / +1.119%` | Useful target-side win; likely main contributor to combo. |
| Per-layer postnorm only | all runs valid | `+0.009% / +0.391% / +0.747%` | Weak positive. Keep only as part of combo unless MTP proves it stacks. |
| UBATCH/BATCH `1152/1152` | all runs valid | `+0.005% / +0.357% / +0.727%` | Weak positive, not enough to prioritize over postnorm combo. |
| Packed GEGLU all | all runs valid | `-1.046% / -0.858% / -0.570%` | Real no-spec loss. Close/reject for this stack. |
| LM-head Q8 one-column subgroup `16` | screen valid | GPU0 control `77.047`, GPU1 subgroup16 `77.064` | Flat. No focused follow-up. |
| LM-head Q8 one-column subgroup `2` | screen valid | GPU2 control `76.605`, GPU3 subgroup2 `76.548` | Slight loss. No focused follow-up. |
| VDR2 selected-down rowpack=2 | skipped | n/a | Active source did not expose the rowpack knob in this checkout. |

`Validity` means realistic gate passed, canaries passed, and all realistic-suite
rows reported `cached_tokens=0`.

## Key Result: Postnorm Combo

The combined attention + per-layer postnorm run was tested twice: first with
candidates on GPUs 1/3 and controls on GPUs 0/2, then crossed over with
candidates on GPUs 0/2 and controls on GPUs 1/3.

Combined analyzer:

- JSON: `data/gemma4-q8-nospec-postnormcombo-combined-ab-20260701T140828Z-nospec-retest.json`
- Markdown: `data/gemma4-q8-nospec-postnormcombo-combined-ab-20260701T140828Z-nospec-retest.md`
- control run medians: `77.001`, `76.685`, `76.486`, `77.028`
- candidate run medians: `77.372`, `77.636`, `77.815`, `77.537`
- control mean-of-run-medians: `76.799779`
- candidate mean-of-run-medians: `77.589824`
- crude run-median delta: `+1.029%`
- paired prompt median ratio CI: `+0.744% / +1.014% / +1.296%`

Interpretation:

- This survives GPU cross-over and is the strongest no-spec target-side signal
  in this pass.
- It should be the next MTP final-gate candidate, but it is not itself a
  promoted throughput result because speculation is disabled here.
- The combo should be tested before spending more time on lower-confidence
  target-side micro-changes.

## Individual Results

### Attention Postnorm

- JSON: `data/gemma4-q8-nospec-attnpost-ab-20260701T140828Z-nospec-retest.json`
- Markdown: `data/gemma4-q8-nospec-attnpost-ab-20260701T140828Z-nospec-retest.md`
- control mean-of-run-medians: `77.063442`
- candidate mean-of-run-medians: `77.619680`
- paired prompt median ratio CI: `+0.431% / +0.804% / +1.119%`

This is a good standalone diagnostic win. If the combo regresses under MTP, test
attention postnorm by itself under the normal MTP final gate.

### Per-Layer Postnorm

- JSON: `data/gemma4-q8-nospec-perlayer-ab-20260701T140828Z-nospec-retest.json`
- Markdown: `data/gemma4-q8-nospec-perlayer-ab-20260701T140828Z-nospec-retest.md`
- control mean-of-run-medians: `76.636258`
- candidate mean-of-run-medians: `76.918641`
- paired prompt median ratio CI: `+0.009% / +0.391% / +0.747%`

This is a weak positive. It is worth keeping inside the postnorm combo, but not
worth prioritizing alone unless MTP combo testing shows interference.

### UBATCH/BATCH 1152

- JSON: `data/gemma4-q8-nospec-ub1152-ab-20260701T140828Z-nospec-retest.json`
- Markdown: `data/gemma4-q8-nospec-ub1152-ab-20260701T140828Z-nospec-retest.md`
- control mean-of-run-medians: `76.725591`
- candidate mean-of-run-medians: `76.992056`
- paired prompt median ratio CI: `+0.005% / +0.357% / +0.727%`

This is also a weak positive. It is not a discard, but it is below the postnorm
combo and should not drive the next MTP run unless batch-shape work becomes the
active lane.

### Packed GEGLU All

- JSON: `data/gemma4-q8-nospec-packedgeglu-ab-20260701T140828Z-nospec-retest.json`
- Markdown: `data/gemma4-q8-nospec-packedgeglu-ab-20260701T140828Z-nospec-retest.md`
- control mean-of-run-medians: `77.147353`
- candidate mean-of-run-medians: `76.500593`
- paired prompt median ratio CI: `-1.046% / -0.858% / -0.570%`

This is a clean negative result. Do not keep retesting `LLAMA_GEMMA4_MOE_GATEUP_GEGLU_EPILOGUE=all`
on this stack unless the implementation changes.

### LM-Head Q8 One-Column Subgroups

This was a screen, not a full paired value-by-value A/B.

| Lane | Median | p10 | Mean | Readout |
| --- | ---: | ---: | ---: | --- |
| GPU0 control | `77.046797` | `76.896517` | `77.021008` | reference for subgroup16 |
| GPU1 subgroup16 | `77.063668` | `76.920703` | `77.032754` | effectively flat |
| GPU2 control | `76.605175` | `76.514574` | `76.595048` | reference for subgroup2 |
| GPU3 subgroup2 | `76.547923` | `76.417449` | `76.535468` | slight loss |

Do not spend another full focused pass on subgroup `2` or `16` unless a later
LM-head patch changes the implementation.

## Next Action

Run the normal MTP realistic final gate with:

```bash
LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1
LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1
```

Compare against the current MTP record recipe using the strict fresh-response
policy:

- fixed realistic prompt suite;
- each prompt once as a cold first response;
- `cached_tokens=0` every row;
- no prefix/KV cache reuse, response reuse, context checkpoints, or warmed
  repeated-prompt averaging;
- keep target model and quantization unchanged;
- MTP/speculation allowed only with target-model verification.

Only promote if the MTP final gate passes and the speed gain survives the normal
fresh-response validation.
