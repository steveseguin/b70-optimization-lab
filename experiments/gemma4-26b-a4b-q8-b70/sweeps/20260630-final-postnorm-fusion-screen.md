# 2026-06-30 Final Post-Norm Residual Fusion Screen

Status: promoted as the current valid headline row, with a variance caveat.
Strict128, strict128 cross-over, and full512 A/B all passed the fixed cold
realistic gate. The best full512 lane reached `123.67689864739785 tok/s` and
was submitted to LocalMaxxing as `cmr01nnet000mld01x2tt6qds`.

This is a source-flag screen against the current Gemma 4 26B A4B Q8
FA-on 32K/VMM selected-down VDR2 record identity. It is not a LocalMaxxing
candidate unless a full512 cold-suite lane beats the current
`121.41411987308553 tok/s` record.

## Question

The source already contains a default-off graph shortcut:

`LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`

It replaces the separate final post-FFN RMS norm plus residual add in
`src/models/gemma4.cpp` with `ggml_rms_norm_scale_add()`. This was negative on
older stacks, but was not clearly rechecked after the FA-on 32K/VMM and VDR2
selected-down record stack.

Control identity:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: Q4_0 MTP draft, target verified;
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`;
- `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`;
- `n_max=3`, `n_min=2`, `p_min=0.0475`;
- promoted flags:
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`;
- fixed realistic cold suite, `cached_tokens=0`, no history/ngram/cache reuse.

## Strict128 Screen

Stamp: `20260630T023532Z-postnorm`.

All lanes passed `realistic_final_gate`, `cached_tokens=0`, and `256/256`
canary rows.

| Lane | Flag | Summary | Median 1-100 | p10 | Mean | Full128 | Wall | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | control | `data/gemma4-q8-gpu0-postnorm-control-strict128-20260630T023532Z-postnorm/summary.json` | 120.297113 | 107.394264 | 118.608100 | 115.468625 | 98.595678 | 179.904132 |
| GPU1 | final postnorm | `data/gemma4-q8-gpu1-finalpostnorm-on-strict128-20260630T023532Z-postnorm/summary.json` | 118.469174 | 107.117303 | 118.033543 | 116.966323 | 100.091297 | 179.360386 |
| GPU2 | branch postnorm | `data/gemma4-q8-gpu2-branchpostnorm-on-strict128-20260630T023532Z-postnorm/summary.json` | 116.534576 | 106.100343 | 118.563153 | 115.258800 | 98.335468 | 179.270397 |
| GPU3 | control | `data/gemma4-q8-gpu3-postnorm-control-strict128-20260630T023532Z-postnorm/summary.json` | 111.980509 | 105.470244 | 115.128664 | 111.913870 | 95.817057 | 180.781445 |

Branch post-norm (`LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD=1`) is not
interesting on this stack. It landed between the two noisy controls and did not
show a reason to continue.

Final post-norm was mixed: below the high control on the primary metric, but
better than the low control and better on full-output/wall than both controls.
That justified exactly one cross-over before closing or promoting.

## Strict128 Cross-Over

Stamp: `20260630T023810Z-finalpost-xover`.

All lanes passed `realistic_final_gate`, `cached_tokens=0`, and `256/256`
canary rows.

| Lane | Flag | Summary | Median 1-100 | p10 | Mean | Full128 | Wall | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | final postnorm | `data/gemma4-q8-gpu0-finalpostnorm-on-xover-strict128-20260630T023810Z-finalpost-xover/summary.json` | 118.908417 | 105.612265 | 118.194353 | 117.687219 | 98.650704 | 179.893711 |
| GPU1 | control | `data/gemma4-q8-gpu1-finalpostnorm-control-xover-strict128-20260630T023810Z-finalpost-xover/summary.json` | 116.553371 | 105.253231 | 115.981281 | 112.202294 | 96.963064 | 180.296809 |
| GPU2 | control | `data/gemma4-q8-gpu2-finalpostnorm-control-xover-strict128-20260630T023810Z-finalpost-xover/summary.json` | 116.269646 | 107.373152 | 117.359451 | 113.433859 | 98.031400 | 180.630335 |
| GPU3 | final postnorm | `data/gemma4-q8-gpu3-finalpostnorm-on-xover-strict128-20260630T023810Z-finalpost-xover/summary.json` | 116.394593 | 105.573007 | 116.498890 | 113.702728 | 98.596744 | 179.989932 |

Cross-over averages:

- controls: `116.41150833131836 tok/s` primary median average;
- final postnorm: `117.6515050898982 tok/s` primary median average.

## Full512 A/B

Stamp: `20260630T024027Z-finalpost-full512`.

All lanes passed `realistic_final_gate`, `cached_tokens=0`, and `512/512`
canary rows.

| Lane | Flag | Summary | Median 1-100 | p10 | Mean | Full512 | Wall | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GPU0 | final postnorm | `data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json` | 123.676899 | 105.672525 | 120.825361 | 110.683107 | 106.440766 | 179.124976 |
| GPU1 | control | `data/gemma4-q8-gpu1-finalpostnorm-control-full512-20260630T024027Z-finalpost-full512/summary.json` | 117.873477 | 107.551946 | 118.507636 | 108.731285 | 104.232649 | 179.487557 |
| GPU2 | control | `data/gemma4-q8-gpu2-finalpostnorm-control-full512-20260630T024027Z-finalpost-full512/summary.json` | 114.709199 | 107.577677 | 115.651617 | 109.759894 | 104.677378 | 179.719387 |
| GPU3 | final postnorm | `data/gemma4-q8-gpu3-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json` | 116.551385 | 103.115698 | 115.666292 | 108.946715 | 104.504069 | 178.537438 |

Full512 averages:

- controls: `116.29133772533568 tok/s` primary median average;
- final postnorm: `120.11414175477651 tok/s` primary median average.

## Decision

Promote `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1` into the current
record reproduction recipe. The GPU0 full512 final-postnorm lane is a valid
new high:

- primary metric: `123.67689864739785 tok/s` median generated-token throughput
  for tokens 1-100 after TTFT;
- p10 `105.67252530778094`, mean `120.82536080117124`;
- median full512 after-TTFT `110.68310696601407`, median wall full512
  `106.44076646173642`, median TTFT `179.12497598445043 ms`;
- LocalMaxxing: `cmr01nnet000mld01x2tt6qds`.

Caveat: this remains a high-variance lane. The second final-postnorm full512
lane (`116.55138486215519`) did not beat the prior `121.41411987308553` record,
and controls spanned `114.709-117.873`. Treat the flag as the current best
recipe because it produced a valid submitted high and its paired average beat
controls, but keep running repeat confirmations before using the size of the
GPU0 jump as an expected effect size.
