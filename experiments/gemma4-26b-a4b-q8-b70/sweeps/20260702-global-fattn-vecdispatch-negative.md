# Gemma 4 26B Q8 Global FlashAttention Vec-Dispatch Negative

Date: 2026-07-02

## Question

The prefill node profile showed full/global FlashAttention layers dominating
TTFT at long context. Hot global shapes looked like:

```text
Q=[512,2,16,1], K/V=[512,256,2,1], mask=[256,2,1,1]
```

The current SYCL FlashAttention dispatch routes Gemma GQA (`gqa_ratio >= 2`)
through the tile kernel. The vec kernel already supports `D=512` and
`Q->ne[1] == 2`, so this experiment tested whether forcing the profiled global
shape to `BEST_FATTN_KERNEL_VEC` improves prefill.

## Patch

Default-off source patch:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-vecdispatch-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-vecdispatch-source.diffstat`

Pre-edit source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-vecdispatch-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-global-fattn-vecdispatch-preedit-source.diffstat`

The tested gate was `GGML_SYCL_FATTN_DV512_GQA_GLOBAL_VEC=1`. The patch built
successfully after sourcing oneAPI. An earlier build attempt without the oneAPI
environment failed during final link with unresolved SYCL/OpenMP symbols; that
was a build-environment issue, not a C++ compile failure.

## Validation

Single-case smoke:

- `data/gemma4-long-context-service-gate-20260702Tglobalvec-smoke1.json`
- `lc-12288-early`, exact JSON pass, `cached_tokens=0`
- prefill approx `1225.294 tok/s`, decode `127.462 tok/s`

Four-GPU same-window A/B:

- Control:
  `data/gemma4-long-context-service-gate-20260702Tglobalvec-ab-control2.json`
- Candidate:
  `data/gemma4-long-context-service-gate-20260702Tglobalvec-ab-candidate1.json`
- Comparison:
  `data/gemma4-global-fattn-vecdispatch-comparison-20260702.json`

Run identity:

- model: Gemma 4 26B A4B instruct `UD-Q8_K_XL` target/verifier
- llama.cpp source baseline: `c926ad098` record stack
- one replica per B70 GPU, GPUs 0-3
- `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`
- `BATCH_SIZE=2048`, `UBATCH_SIZE=1024`, `LLAMA_PREFILL_UBATCH_SIZE=2048`
- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`
- cases: `lc-12288-early`, `lc-16384-late`, `lc-22000-middle`
- `MAX_TOKENS=96`, `CANARY_REPEATS=2`
- every promoted comparison row had exact JSON validation pass and
  `cached_tokens=0`

A comma-delimited `LONG_CONTEXT_CASE_IDS` attempt (`control1`) selected zero
long-context cases and was discarded as a harness invocation mistake. The
valid rerun used whitespace-delimited case IDs.

## Result

The candidate was valid but slightly slower:

| metric | paired mean delta | paired median delta |
| --- | ---: | ---: |
| approximate prefill tok/s | `-0.165%` | `-0.174%` |
| decode tok/s after TTFT | `-0.088%` | `-0.063%` |
| TTFT | `+0.166%` | `+0.174%` |

Decision: **negative / no win**.

## Interpretation

The existing tile path remains better for this shape. The likely reason is that
the tile kernel keeps useful GQA/KV reuse that the vec path gives up by
rereading K/V per Q head. This closes the cheap vec-dispatch branch.

Do not promote or leave the patch active. The active llama.cpp source was
restored after the run and `llama-server` was rebuilt successfully after
sourcing oneAPI. Future service work should move to a real hot-shape tile
variant or another structural global FlashAttention change, not forcing this
shape through the existing vec kernel.
