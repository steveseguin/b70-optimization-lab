# Gemma 4 26B Q8: Global-Only DV512 GQA `ncols2=16` Negative

Date: 2026-07-02

Status: closed negative. Do not promote. This was a correctness-safe
long-context prompt-processing experiment, but it was slower than the validated
`ncols2=8` service lane.

## Goal

Retest the `ncols2=16` idea after the broad 2026-07-01 attempt failed JSON
canaries with empty output. The revised hypothesis was narrower: force
`ncols2=16` only for the global Gemma attention path, while leaving SWA on the
validated `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8` path. The target was long-context
prefill/TTFT improvement with no short-decode or quality regression.

## Patch

Pre-edit source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-ncols16-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-ncols16-preedit-source.diffstat`

Candidate source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-ncols16-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-ncols16-source.diffstat`

Candidate code added default-off env gates in
`ggml/src/ggml-sycl/fattn-tile.hpp`:

- `GGML_SYCL_FATTN_DV512_GQA_GLOBAL_NCOLS2=16`
- `GGML_SYCL_FATTN_DV512_GQA_GLOBAL_NCOLS2_MIN_Q=2048`

The branch only fired when `DV == 512`, GQA optimization was available,
`dst->src[5] == nullptr` (global attention, not SWA), `Q->ne[1] >= min_q`, and
`gqa_ratio % 16 == 0`.

Build succeeded in
`/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2`.

## A/B Run

Stamp: `20260702Tglobalncols16-ab1`

Control lanes:

- GPU0: `data/gemma4-q8-gpu0-longctx-control-20260702Tglobalncols16-ab1/`
- GPU2: `data/gemma4-q8-gpu2-longctx-control-20260702Tglobalncols16-ab1/`

Candidate lanes:

- GPU1: `data/gemma4-q8-gpu1-longctx-globalncols16-20260702Tglobalncols16-ab1/`
- GPU3: `data/gemma4-q8-gpu3-longctx-globalncols16-20260702Tglobalncols16-ab1/`

Shared settings:

- model: Gemma 4 26B A4B IT GGUF Q8 record stack
- GPUs: one model copy per B70 GPU
- `CTX_SIZE=32768`
- `FLASH_ATTN=on`
- `BATCH_SIZE=2048`
- `UBATCH_SIZE=1024`
- `LLAMA_PREFILL_UBATCH_SIZE=2048`
- `GGML_SYCL_ENABLE_VMM=1`
- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`
- long-context cases: `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`
- `LONG_CONTEXT_MAX_TARGET_PROMPT_TOKENS=24000`
- `MAX_TOKENS=96`
- `CANARY_REPEATS=2`
- `REALISTIC_GATE=0`
- `LONG_CONTEXT_GATE=1`

Candidate-only env:

- `GGML_SYCL_FATTN_DV512_GQA_GLOBAL_NCOLS2=16`
- `GGML_SYCL_FATTN_DV512_GQA_GLOBAL_NCOLS2_MIN_Q=2048`

## Results

All four lanes passed:

- long-context exact validation: pass
- chat canary: 8/8 per lane
- `cached_tokens=0` for every recorded case

Aggregate medians:

| Lane | Variant | Prefill tok/s | Decode tok/s | TTFT s |
| --- | --- | ---: | ---: | ---: |
| GPU0 | control | 1125.661429 | 119.875462 | 20.192572 |
| GPU1 | candidate | 1109.732722 | 119.367345 | 20.482409 |
| GPU2 | control | 1128.247205 | 119.491213 | 20.146294 |
| GPU3 | candidate | 1121.798628 | 119.639005 | 20.262104 |

Control average:

- prefill: `1126.954317 tok/s`
- decode: `119.683338 tok/s`
- TTFT: `20.169433 s`

Candidate average:

- prefill: `1115.765675 tok/s`
- decode: `119.503175 tok/s`
- TTFT: `20.372257 s`

Candidate delta:

- prefill: `-0.9928%`
- decode: `-0.1505%`
- TTFT: `+1.0056%` slower

Representative candidate per-case rows:

GPU1:

- `lc-12288-early`: prompt `16213`, prefill `1198.265965`, decode `126.738168`, TTFT `13.530385`, cached `0`, exact pass
- `lc-16384-late`: prompt `22730`, prefill `1109.732722`, decode `119.367345`, TTFT `20.482409`, cached `0`, exact pass
- `lc-22000-middle`: prompt `30400`, prefill `1008.380365`, decode `112.805949`, TTFT `30.147354`, cached `0`, exact pass

GPU3:

- `lc-12288-early`: prompt `16213`, prefill `1211.960595`, decode `126.933497`, TTFT `13.377498`, cached `0`, exact pass
- `lc-16384-late`: prompt `22730`, prefill `1121.798628`, decode `119.639005`, TTFT `20.262104`, cached `0`, exact pass
- `lc-22000-middle`: prompt `30400`, prefill `1021.189749`, decode `112.756705`, TTFT `29.769198`, cached `0`, exact pass

## Decision

Rejected. The global-only `ncols2=16` selector is quality-safe in this narrow
form but is slower than the control on the intended prompt-processing metric.
No LocalMaxxing submission, no promoted repro, and no short-decode guard run is
warranted.

The active source should be restored to the pre-edit record stack and rebuilt
before the next experiment.

## Follow-Up

Do not spend more time on DV512 GQA `ncols2=16` selector roulette. The remaining
Gemma work with plausible upside is deeper:

- reduce verifier/LM-head cost with a non-serial row-work-saving design;
- profile and reduce global FlashAttention kernel cost instead of changing the
simple `ncols2` selector;
- keep prefill/long-context improvements separate from the short-decode record
and rerun the short realistic gate after any promoted service-lane change.
