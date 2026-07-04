# 2026-07-04 - INT8 GEMM scratchpad ring-size screen: no-promo

## Summary

Screened `VLLM_XPU_INT8_GEMM_SCRATCHPAD_RING_SIZE` on the current Qwen27
webhie/BF16-scale record recipe.

Why it was worth one bounded screen: the current bottleneck includes repeated
runtime INT8 LM-head oneDNN GEMMs, and the local wrapper in
`/home/steve/src/vllm-xpu-kernels/csrc/xpu/onednn/int8_gemm_w8a8.h` reuses a
thread-local user scratchpad ring with default size `1`.

Result: larger ring sizes are strict-valid, but there is no statistically
useful win. Ring4 produced one high support row (`65.817 tok/s`) and one
first-pass high row (`65.708 tok/s`), but the same-window crossover deltas
against ring1 controls were only `+0.42%` and `+0.27%`, below the
`~1-1.5%` practical variance band for this recipe. Do not promote or submit.

## Identity

- model: `webhie/Qwen3.6-27B-int4-AutoRound`;
- revision: `f5750c90b3776db658594df5fe8051098226dd8e`;
- runtime mode: AutoRound W4A16 + runtime INT8 LM-head with BF16 scales;
- recipe: promote-source MTP3/cg8,
  `VLLM_XPU_GDN_PROMOTE_ACCEPTED_SPEC_STATE=1`,
  `VLLM_XPU_GDN_NONSPEC_POSTPROCESS_ACCEPTED_STATE=0`,
  `VLLM_XPU_LM_HEAD_INT8=1`,
  `VLLM_XPU_LM_HEAD_INT8_SCALE_DTYPE=bf16`;
- gate: fixed Qwen realistic suite, chat mode, each prompt once, streamed token
  IDs, primary metric generated tokens 1-100 after TTFT, `cached_tokens=0` on
  every request.

## First same-window pass

| Ring size | GPU | Gate | cached=0 | Median tok/s | p10 | Mean | TTFT median |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 control | 0 | pass | yes | `64.94594083219681` | `57.972797563710834` | `64.34502883294265` | `604.377934942022 ms` |
| 2 | 1 | pass | yes | `65.59256849266124` | `57.88899603663567` | `64.30565564754515` | `612.1998748276383 ms` |
| 4 | 2 | pass | yes | `65.70828722489509` | `57.9168619539425` | `64.68966000720067` | `602.6058330899104 ms` |
| 8 | 3 | pass | yes | `64.36692281735876` | `57.70315113963782` | `64.16340939517342` | `610.3853840613738 ms` |

Ring4's first-pass median was `+1.17%` over ring1 control, which is inside the
inconclusive band and required a crossover.

## Crossover

| Pair | Variant | GPU | Gate | cached=0 | Median tok/s | Delta vs paired ring1 |
| --- | --- | ---: | --- | --- | ---: | ---: |
| A | ring4 | 0 | pass | yes | `65.81735720602546` | `+0.42%` |
| A | ring1 control | 1 | pass | yes | `65.54179622517225` | baseline |
| B | ring4 | 2 | pass | yes | `64.72845556968409` | `+0.27%` |
| B | ring1 control | 3 | pass | yes | `64.55276347813671` | baseline |

The p10/mean values did not show a meaningful separation either:

- ring4 A mean `64.76166312733032`, control A mean `64.35489714775058`;
- ring4 B mean `64.25702713418171`, control B mean `64.16482838445988`.

## Artifacts

First pass:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring1-control-20260704-codex-20260704T120149Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring2-20260704-codex-20260704T120149Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring4-20260704-codex-20260704T120149Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring8-20260704-codex-20260704T120149Z.json`

Crossover:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring4-crossoverA-20260704-codex-20260704T120444Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring1-controlA-20260704-codex-20260704T120444Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring4-crossoverB-20260704-codex-20260704T120444Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-bf16scale-int8scratch-ring1-controlB-20260704-codex-20260704T120444Z.json`

## Decision

Keep the default scratchpad ring-size behavior for the current recipe. Ring2/4
are not harmful in the strict runs, but they are not a supported headline
improvement.

Do not submit any of these rows to LocalMaxxing. The best ring4 rows are support
only and remain inside the variance band. Revisit only if a future source
change creates real concurrent oneDNN LM-head overlap or a trace shows
scratchpad reuse as a correctness/performance issue.
