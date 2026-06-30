# 2026-06-30 FA-on 32K/VMM UBATCH Screen

Status: closed. Valid but not a record; keep the promoted recipe at
`BATCH_SIZE=1024`, `UBATCH_SIZE=1024`.

## Purpose

Re-check the final record identity's `BATCH_SIZE` / `UBATCH_SIZE` neighborhood
after the row-economics profile. The current headline recipe uses
`BATCH_SIZE=1024`, `UBATCH_SIZE=1024`. This screen asks whether a larger
microbatch changes target/verifier throughput without changing target quality,
quantization, speculative verification semantics, context length, or cache
policy.

This is not a source patch and not a LocalMaxxing result. It started as a
strict128 screen used to decide whether a full512 paired confirmation was worth
running; the full512 confirmation is recorded below.

## Shared Identity

- target/verifier: Gemma 4 26B A4B IT `UD-Q8_K_XL`
- draft: Gemma MTP `Q4_0`, `n_max=3`, `n_min=2`, `p_min=0.0475`
- runtime: llama.cpp `c926ad098` patched Gemma stack, one B70 per lane
- suite: fixed realistic cold suite, each prompt once
- validity: `cached_tokens=0` on every prompt, no prompt/KV cache reuse, no
  response reuse, no n-gram/history acceleration, `--ctx-checkpoints 0`
- key env/config:
  `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `MAX_TOKENS=128`, `CANARY_REPEATS=32`

Current headline for comparison remains the full512 non-profiled record:
`121.41411987308553 tok/s` in
`data/gemma4-q8-gpu3-q8lmhead-noreorder-control-full512-20260629T224927Z/summary.json`.

## Strict128 Screen Results

| Label | Batch | UBatch | Valid | Canary | Median 1-100 tok/s | p10 | Mean | Full after TTFT | Wall full | TTFT ms |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemma4-q8-gpu0-faon-vmm-ub768-strict128-20260630Tcont` | 1024 | 768 | pass | 128/128 | `115.27868945060834` | `102.64463965197208` | `115.45887514380031` | `113.6793763034328` | `94.94822148753451` | `178.86045604245737` |
| `gemma4-q8-gpu1-faon-vmm-ub896-strict128-20260630Tcont` | 1024 | 896 | pass | 128/128 | `117.53966767868373` | `100.67493406453427` | `116.43772551728772` | `118.697595317304` | `99.10932770265941` | `179.3850350077264` |
| `gemma4-q8-gpu2-faon-vmm-ub1024-control-strict128-20260630Tcont` | 1024 | 1024 | pass | 128/128 | `116.32512318613897` | `100.6981920540771` | `114.95171242472107` | `116.78841427491768` | `99.46488645552988` | `180.28968351427466` |
| `gemma4-q8-gpu3-faon-vmm-ub1152-strict128-20260630Tcont` | 1152 | 1152 | pass | 128/128 | `121.24708378127268` | `109.7932680050226` | `118.62708551390502` | `117.40542216833933` | `100.12899322179143` | `179.6315275132656` |

## Full512 Promotion Screen

The strict128 `UBATCH_SIZE=1152` signal was promoted to a paired full512 screen:
two `BATCH_SIZE=1152`, `UBATCH_SIZE=1152` candidate lanes and two
`BATCH_SIZE=1024`, `UBATCH_SIZE=1024` controls. All four passed the fixed cold
gate and 128/128 canary rows with `cached_tokens=0`.

| Label | Batch | UBatch | Valid | Canary | Median 1-100 tok/s | p10 | Mean | Full after TTFT | Wall full | TTFT ms |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemma4-q8-gpu0-faon-vmm-ub1152-full512-A-20260630Tcont` | 1152 | 1152 | pass | 128/128 | `118.43353215490006` | `107.38817563842781` | `118.36480176617688` | `109.61119044881457` | `103.7687383266499` | `179.12590055493638` |
| `gemma4-q8-gpu1-faon-vmm-ub1152-full512-B-20260630Tcont` | 1152 | 1152 | pass | 128/128 | `116.29263842544727` | `107.44872268279161` | `116.67928427766837` | `110.87457122147849` | `105.75359804522931` | `179.49246458010748` |
| `gemma4-q8-gpu2-faon-vmm-ub1024-full512-control-A-20260630Tcont` | 1024 | 1024 | pass | 128/128 | `113.62212528072519` | `107.62565831326508` | `116.67753404818173` | `109.73594649219945` | `105.32688200816597` | `180.2478220197372` |
| `gemma4-q8-gpu3-faon-vmm-ub1024-full512-control-B-20260630Tcont` | 1024 | 1024 | pass | 128/128 | `114.99220812107981` | `104.51241028324709` | `114.96670826513298` | `109.43159337983886` | `105.43463069618474` | `179.18937001377344` |

Full512 summary:

- candidate average primary median: `117.36308529017367 tok/s`;
- paired-control average primary median: `114.3071667009025 tok/s`;
- candidate average delta versus controls: `+3.0559185892711724 tok/s`;
- best candidate: `118.43353215490006 tok/s`;
- gap to current headline: `-2.980587718185461 tok/s` versus
  `121.41411987308553`.

## Decision

`UBATCH_SIZE=1152` is a valid local positive versus same-window controls, but
it did **not** beat the current full512 headline. Do not change the promoted
recipe and do not submit this to LocalMaxxing. Keep `BATCH_SIZE=1024`,
`UBATCH_SIZE=1024` as the record recipe unless a future source patch changes
the microbatch tradeoff.

`UBATCH_SIZE=768` and `UBATCH_SIZE=896` are closed for the short-record lane
unless a future source patch changes the memory/workgroup tradeoff enough to
justify retesting.
