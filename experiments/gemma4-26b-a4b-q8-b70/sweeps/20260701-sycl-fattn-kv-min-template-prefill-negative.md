# Gemma 4 26B Q8 B70: Isolated KV-min Prefill Tile Retry

Date: 2026-07-01

Status: **negative, not promoted**.

This retry followed up on
`20260701-sycl-fattn-kv-min-left-bound-partial.md`. The earlier KV-min
left-bound patch repeatedly improved long-prefill by roughly `+4.7%` to
`+6.1%`, but it also regressed the fixed short-decode guard. This experiment
tried to isolate KV-min into a separate large-prefill-only tile variant so the
normal decode/default tile path would remain unchanged.

## Patch

Patch snapshot:

- `patches/gemma4-26b-a4b-q8-b70/20260701-sycl-fattn-kv-min-template-prefill-negative.patch`
- sha256:
  `81c9b943a4c5fcc86a6b3ac68c6bd62b7835375ed7e21f881eef4039ce7b55f2`

The tested source state added a compile-time `use_KV_min` template path and
enabled it only when all of these were true:

- `GGML_SYCL_FATTN_KV_MIN_SCAN=1`;
- `GGML_SYCL_FATTN_KV_MIN_SCAN_MIN_Q=2048`;
- `Q->ne[1] >= 2048`;
- the DV512 GQA service path selected `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`.

The patch is an experiment snapshot on top of the current Gemma/B70 llama.cpp
source stack. It is not a clean upstream-only patch and was not promoted.

## Validation

Artifact:

- `data/gemma4-kvmin-template-longctx-ab-20260701T045743Z-kvmin-template-ab1.json`

Four lanes ran in parallel:

- GPUs `0` and `2`: control, no KV-min env;
- GPUs `1` and `3`: candidate, `GGML_SYCL_FATTN_KV_MIN_SCAN=1`,
  `GGML_SYCL_FATTN_KV_MIN_SCAN_MIN_Q=2048`.

Common identity:

- target model: Gemma 4 26B A4B IT `UD-Q8_K_XL`;
- one B70 per lane;
- `CTX_SIZE=32768`;
- `FLASH_ATTN=on`;
- `GGML_SYCL_ENABLE_VMM=1`;
- `BATCH_SIZE=2048`;
- `UBATCH_SIZE=1024`;
- `LLAMA_PREFILL_UBATCH_SIZE=2048`;
- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`;
- long-context cases: `lc-12288-early`, `lc-16384-late`,
  `lc-22000-middle`;
- `MAX_TOKENS=96`;
- `CANARY_REPEATS=2`;
- `cached_tokens=0` for all case rows.

All lanes passed the long-context gate, canary, quality, and cached-token
checks.

## Result

Corrected aggregate after fixing the lane-classification bug in the first
summary:

| Group | Median prefill tok/s by lane | Average |
| --- | ---: | ---: |
| control | `1054.206949`, `1056.258192` | `1055.232571` |
| KV-min template | `1040.605255`, `1053.994427` | `1047.299841` |

Candidate delta:

- prefill: `-0.7518%`;
- decode: `-0.1825%`.

Per-case candidate results were valid but did not beat controls. Because the
long-prefill objective failed, no short-decode guard was run for this retry.

## Decision

Do not promote this isolated-template KV-min variant.

The intended separation from short decode was achieved structurally, but the
prefill gain from the earlier direct KV-min patch did not repeat. The likely
explanation is that the narrowed template/selector path changed which
FlashAttention tile shape actually receives the left-bound optimization, or
the second-bound scan/read cost offsets the skipped KV work in this isolated
form. Either way, this variant is a loss against the current service profile.

The active source was reverted to remove all `KV_min`/`kv_min` identifiers
after this patch was archived. Keep the existing non-KV-min service controls:

- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`;
- `GGML_SYCL_FATTN_KV_MAX_SCAN_MIN_Q`.

Future SWA/prefill work should prefer a host-derived or launch-derived left
bound for Gemma sliding-window attention, not a second mask scan and second
per-tile bound read in the hot tile.
