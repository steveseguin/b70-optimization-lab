# 2026-06-30 Final Post-Norm Repeat2 Full512 Variance

Status: valid cold-suite support run, no new record, do not submit.

This repeats the current promoted Gemma 4 26B A4B Q8 one-B70 recipe after the
`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` LocalMaxxing submission
(`cmr01nnet000mld01x2tt6qds`). It checks whether the promoted recipe reliably
beats the `123.67689864739785 tok/s` high across four GPUs.

## Identity

- Target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`.
- Draft: Q4_0 MTP draft, target verified.
- Runtime: llama.cpp working record stack at `c926ad098` baseline plus local
  Gemma patches.
- Hardware: one Intel Arc Pro B70 per lane.
- Recipe: `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`,
  `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`, `n_max=3`, `n_min=2`,
  `p_min=0.0475`, `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`.
- Validation: fixed realistic prompt suite, each prompt once as a cold first
  response, `cached_tokens=0` every request, no prompt/KV/context/response
  reuse, no n-gram/history acceleration, full512 output, canary `512/512`.

## Results

| Lane | Summary | Median 1-100 | p10 | Mean | Full512 | Wall full512 | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | `data/gemma4-q8-gpu0-finalpostnorm-repeat-full512-20260630T025805Z-finalpost-repeat2/summary.json` | 118.789412 | 106.331366 | 118.497505 | 109.955184 | 105.061340 | 178.725781 |
| GPU1 | `data/gemma4-q8-gpu1-finalpostnorm-repeat-full512-20260630T025805Z-finalpost-repeat2/summary.json` | 115.488248 | 107.867029 | 118.275004 | 109.750471 | 105.598906 | 178.174435 |
| GPU2 | `data/gemma4-q8-gpu2-finalpostnorm-repeat-full512-20260630T025805Z-finalpost-repeat2/summary.json` | 112.719024 | 105.712547 | 115.400717 | 110.608599 | 105.087859 | 178.846198 |
| GPU3 | `data/gemma4-q8-gpu3-finalpostnorm-repeat-full512-20260630T025805Z-finalpost-repeat2/summary.json` | 116.801249 | 108.197586 | 118.637370 | 111.133341 | 106.910844 | 178.984045 |

Average primary median: `115.94948311644934 tok/s`.

## Decision

Closed as variance/no-new-record. This does not disprove the promoted
`123.67689864739785 tok/s` row because that row passed the policy gate and was
submitted with supporting A/B data, but it reinforces the current caveat:
single-lane highs on this stack are noisy, and the expected repeatable
final-postnorm recipe speed is closer to the high-teens / low-120s than a
guaranteed `123+ tok/s`.
