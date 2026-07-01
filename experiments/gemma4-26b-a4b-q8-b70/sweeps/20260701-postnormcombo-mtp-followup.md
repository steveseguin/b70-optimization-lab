# Gemma 4 26B Q8 Post-Norm Combo MTP Follow-Up

Date: 2026-07-01

Status: valid same-window follow-up; **not promoted**.

## Purpose

No-spec calibration found small target-side positives for attention post-norm
fusion and the final + attention + per-layer post-norm combo. The combo was the
only bounded follow-up worth checking under the normal MTP full512 record gate.
This run tested whether that no-spec signal survived the real speculative decode
pipeline.

## Run Window

Same-window four-GPU window:

- controls:
  - `data/gemma4-q8-gpu0-postnormcombo-mtp-control-full512-20260701TactiveA/summary.json`
  - `data/gemma4-q8-gpu2-postnormcombo-mtp-control-full512-20260701TactiveA/summary.json`
- candidates (`LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1` and
  `LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`, with the promoted final
  post-norm residual still on):
  - `data/gemma4-q8-gpu1-postnormcombo-mtp-on-full512-20260701TactiveA/summary.json`
  - `data/gemma4-q8-gpu3-postnormcombo-mtp-on-full512-20260701TactiveA/summary.json`

A/B artifacts:

- `data/gemma4-q8-mtp-postnormcombo-ab-20260701TactiveA.json`
- `data/gemma4-q8-mtp-postnormcombo-ab-20260701TactiveA.md`

## Validity

All four lanes passed the fixed realistic final gate:

- `cached_tokens=0` for every prompt;
- prompts are unique and run once as cold first responses;
- target/verifier model and quantization unchanged (`UD-Q8_K_XL` target,
  Q4_0 MTP draft);
- primary metric is generated-token throughput for tokens 1-100 after TTFT;
- no n-gram/history/cache/checkpoint acceleration.

## Results

| Lane | Median tok/s | p10 tok/s | Mean tok/s | Full512 tok/s | Wall512 tok/s | TTFT ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 control | `116.78730535019729` | `106.15052652801079` | `117.62758550090935` | `109.52647677148543` | `105.39504290961234` | `179.32988097891212` |
| GPU2 control | `113.96211444018608` | `108.10939528576625` | `116.96111456630422` | `110.83849782249558` | `106.69755807865073` | `179.29258604999632` |
| GPU1 combo-on | `117.22745755712424` | `105.77460506757922` | `118.57197883652863` | `111.53228161447252` | `106.84051946027708` | `178.41948196291924` |
| GPU3 combo-on | `115.86059840160311` | `105.8473878403125` | `117.96199566820677` | `111.36348700987915` | `106.69410885558696` | `177.62561701238155` |

Paired A/B:

```text
control run medians: 116.787, 113.962
candidate run medians: 117.227, 115.861
median paired ratio 95% CI: -2.754% / 0.395% / 3.346%
decision: inconclusive_positive
```

## Decision

Do **not** promote or submit. The combo preserved validity and showed a small
positive central estimate, but the paired MTP confidence interval crosses
negative and the absolute medians remain below the current `124.97714084813418`
tok/s record.

This closes the post-norm combo as a near-term short-record candidate. The
no-spec calibration result remains useful as evidence that the target-side graph
can move by about 1%, but the full MTP pipeline variance and prompt mix do not
support changing the promoted recipe.
