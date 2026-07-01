# 2026-07-01 MTP Full512 Follow-Up: Attention + Per-Layer Postnorm Combo

Status: valid full512 MTP A/B, not promoted.

This is the normal MTP follow-up to the no-spec calibration result in
`20260701-nospec-retest-results.md`. No-spec showed a strong target-side signal
for:

```bash
LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1
LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1
```

The purpose here was to check whether that target-side gain survives in the
actual record path with Q4_0 MTP draft speculation and target verification.

## Run Identity

- stamp: `20260701T143822Z-mtp-postnormcombo-full512`
- source/build: `/home/steve/src/llama.cpp-gemma-record-repro-c926`,
  reordered-Q8 VDR2 build
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- common recipe: `CTX_SIZE=32768`, `FLASH_ATTN=on`,
  `GGML_SYCL_ENABLE_VMM=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`,
  `POLL=100`
- MTP: `--spec-type draft-mtp`, `n_max=3`, `n_min=2`, `p_min=0.0475`,
  Q4_0 draft on the same B70, `--ctx-checkpoints 0`
- promoted target flags held constant:
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`
- candidate extra flags:
  `LLAMA_GEMMA4_FUSED_ATTN_POST_NORM_RESIDUAL=1`,
  `LLAMA_GEMMA4_FUSED_PER_LAYER_POST_NORM_RESIDUAL=1`
- validation: fixed realistic suite, each prompt once as a fresh response,
  `cached_tokens=0`, canary `512/512`, `MAX_TOKENS=512`, primary metric is
  median generated tok/s for tokens 1-100 after TTFT

## Results

All eight lanes passed the realistic final gate, had `cached_tokens=0`, and
passed the text canary.

| GPU | Lane | Summary | Median 1-100 | p10 | Mean | Full512 | Wall full512 | TTFT ms |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | control | `data/gemma4-q8-gpu0-mtp-postnormcombo-control-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `114.072734` | `105.289284` | `118.005822` | `109.100277` | `104.923684` | `178.128962` |
| 1 | combo on | `data/gemma4-q8-gpu1-mtp-postnormcombo-on-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `116.869935` | `105.958173` | `116.196881` | `110.830502` | `106.415896` | `178.522823` |
| 2 | control | `data/gemma4-q8-gpu2-mtp-postnormcombo-control-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `114.239183` | `104.999560` | `117.133904` | `111.917616` | `106.875170` | `177.566746` |
| 3 | combo on | `data/gemma4-q8-gpu3-mtp-postnormcombo-on-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `117.166218` | `104.896413` | `117.619529` | `110.315740` | `105.032758` | `177.803792` |
| 0 | combo on, xover | `data/gemma4-q8-gpu0-mtp-postnormcombo-on-xover-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `119.121080` | `105.807455` | `118.840868` | `112.203509` | `106.607952` | `178.458059` |
| 1 | control, xover | `data/gemma4-q8-gpu1-mtp-postnormcombo-control-xover-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `119.542951` | `104.230550` | `118.806939` | `111.209958` | `106.185416` | `178.745834` |
| 2 | combo on, xover | `data/gemma4-q8-gpu2-mtp-postnormcombo-on-xover-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `119.331324` | `106.299234` | `117.225943` | `110.423693` | `106.517098` | `177.578895` |
| 3 | control, xover | `data/gemma4-q8-gpu3-mtp-postnormcombo-control-xover-full512-20260701T143822Z-mtp-postnormcombo-full512/summary.json` | `119.600345` | `104.567898` | `118.552068` | `110.405482` | `105.877438` | `178.616791` |

Analyzer outputs:

- first pass:
  `data/gemma4-q8-mtp-postnormcombo-ab-20260701T143822Z-mtp-postnormcombo-full512.{json,md}`
- cross-over:
  `data/gemma4-q8-mtp-postnormcombo-xover-ab-20260701T143822Z-mtp-postnormcombo-full512.{json,md}`
- combined:
  `data/gemma4-q8-mtp-postnormcombo-combined-ab-20260701T143822Z-mtp-postnormcombo-full512.{json,md}`

Combined paired analyzer:

- control run medians: `114.073`, `114.239`, `119.543`, `119.600`
- candidate run medians: `116.870`, `117.166`, `119.121`, `119.331`
- control mean-of-run-medians: `116.863803`
- candidate mean-of-run-medians: `118.122139`
- crude run-median delta: `+1.077%`
- paired prompt median ratio 95% CI:
  `-3.488% / +0.679% / +3.525%`
- paired prompt mean ratio 95% CI:
  `-3.914% / -0.231% / +3.277%`

## Decision

Do not promote and do not submit.

The result is valid but not decisive. The candidate run medians are slightly
higher on average, but the paired prompt interval crosses negative by a wide
margin, and the best candidate lane (`119.331 tok/s`) is below the current
valid record (`124.97714084813418 tok/s`). The cross-over also weakened the
apparent win: controls on GPUs 1/3 were faster than combo lanes on GPUs 0/2.

Interpretation:

- The no-spec target-side improvement is real enough to keep as a target-kernel
  fact.
- In the MTP record path, acceptance/scheduler variance and verifier cost
  dominate enough that the combo does not become a headline improvement.
- Do not repeat this exact combo as a record candidate unless another source
  change makes MTP less variance-heavy or changes the verifier/target balance.

Next decode work should return to the larger bottleneck: verifier row/head
cost or MTP acceptance efficiency. For target-only changes, keep using no-spec
calibration first, but require the normal MTP final gate before promotion.
