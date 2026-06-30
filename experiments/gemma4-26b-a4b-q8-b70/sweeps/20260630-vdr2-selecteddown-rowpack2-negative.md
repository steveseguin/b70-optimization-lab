# Gemma4 Q8 VDR2 selected-down rowpack=2 negative

Date: 2026-06-30 UTC

## Question

Can the active `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`
selected-down verifier path improve by packing two output rows into each VDR2
workgroup?

The patch was default-off and limited to the current non-GEGLU selected-down
VDR2 path:

- `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2_ROWPACK=2`;
- local-Y rows share one selected-softmax local buffer;
- GEGLU caller is pinned to the old rowpack (`GGML_SYCL_MMV_Y`);
- active source hunk was reverted after the run.

Patch snapshot:
`patches/gemma4-vdr2-selecteddown-rowpack2-experiment-20260629.patch`.

## Fixed identity

Same strict cold-response identity as the current Gemma Q8 record:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- draft: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one B70 per replica, `FLASH_ATTN=on`, `CTX_SIZE=32768`,
  `GGML_SYCL_ENABLE_VMM=1`, `BATCH_SIZE=1024`, `UBATCH_SIZE=1024`;
- MTP: `n_max=3`, `n_min=2`, `p_min=0.0475`, backend sampling off,
  `--ctx-checkpoints 0`;
- current record flags, including VDR2 reordered-Q8, selected-softmax,
  fused weighted-sum, direct draft argmax IDs, q-only assistant attention,
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`, and
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`.

All rows below are fixed realistic prompt-suite runs, each prompt once,
`cached_tokens=0`, no prompt/history/cache reuse, and canary passing.

## Strict128 screen

Stamp: `20260630T000115Z`

| Lane | Rowpack | Primary median 1-100 tok/s | p10 | Full-output tok/s | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-rowpack2-control-strict128-20260630T000115Z/summary.json` | unset | 118.2821795580862 | 108.0759754943108 | 113.01121935289471 | control |
| `data/gemma4-q8-gpu1-rowpack2-on-strict128-20260630T000115Z/summary.json` | 2 | 119.91429816980194 | 103.23791803977888 | 116.20858015934289 | candidate valid, mild primary positive |
| `data/gemma4-q8-gpu2-rowpack2-control2-strict128-20260630T000115Z/summary.json` | unset | 117.03867376815343 | 103.21628748451444 | 114.42298317331833 | control |
| `data/gemma4-q8-gpu3-rowpack2-on2-strict128-20260630T000115Z/summary.json` | 2 | 116.62556154002101 | 104.65258425085689 | 116.29148994351749 | candidate valid, primary loss |

Strict128 average primary median: controls `117.66042666311981`, rowpack=2
`118.26992985491148` (`+0.6095031917916742`). Full-output median improved more
strongly, so a full512 cross-over was justified.

## Full512 cross-over

Stamp: `20260630T000407Z`

| Lane | Rowpack | Primary median 1-100 tok/s | p10 | Mean | Full512 after-TTFT | Wall full512 | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `data/gemma4-q8-gpu0-rowpack2-on-full512-20260630T000407Z/summary.json` | 2 | 119.75026683034108 | 107.08471887803789 | 116.68054670060895 | 110.07064279673611 | 105.46796384701245 | candidate valid |
| `data/gemma4-q8-gpu1-rowpack2-control-full512-20260630T000407Z/summary.json` | unset | 120.62626200287556 | 106.46062549103673 | 119.3160149807066 | 109.73181731862854 | 104.97241793093635 | control |
| `data/gemma4-q8-gpu2-rowpack2-on2-full512-20260630T000407Z/summary.json` | 2 | 110.62392954093656 | 103.33416825725698 | 114.01908410813239 | 112.30268498502274 | 106.59607418298317 | candidate valid |
| `data/gemma4-q8-gpu3-rowpack2-control2-full512-20260630T000407Z/summary.json` | unset | 117.70674646289913 | 102.69168013958942 | 117.01043440128763 | 108.36454722463412 | 104.47321378257717 | control |

Full512 averages:

- primary 1-100 median: controls `119.16650423288735`, rowpack=2
  `115.18709818563882` (`-3.9794060472485313`);
- p10: controls `104.57615281531307`, rowpack=2 `105.20944356764744`;
- full512 after-TTFT: controls `109.04818227163133`, rowpack=2
  `111.18666389087943`;
- wall full512: controls `104.72281585681476`, rowpack=2
  `106.03201901499781`.

Current valid record remains
`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`
at `121.41411987308553` primary median tok/s.

## Decision

Reject for headline throughput and do not submit. Rowpack=2 appears to improve
longer full-output throughput and wall-clock throughput, but the project record
metric is median generated-token throughput for tokens 1-100 after TTFT. On the
full512 cross-over, rowpack=2 lost that primary metric versus same-window
controls and stayed below the current `121.41411987308553 tok/s` record.

Carryover: rowpack may be useful for service/long-output lanes, but it should
not be part of the short-context record recipe unless a future design recovers
the early-window loss.
