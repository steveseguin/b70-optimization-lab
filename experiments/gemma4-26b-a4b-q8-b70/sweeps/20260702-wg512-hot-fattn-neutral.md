# 2026-07-02 - WG512 hot FlashAttention tile is neutral

## Question

Can the Gemma 4 26B Q8 long-context service lane improve prefill by running the
hot `DKQ=576,DV=512,ncols=16` GQA8 FlashAttention tile with 512 work-items
(16 subgroups, `cpw=1`) instead of the current 256 work-items (8 subgroups,
`cpw=2`) while preserving the existing Q8 quality and short-decode path?

## Patch

Default-off source experiment in:

- `/home/steve/src/llama.cpp-gemma-record-repro-c926/ggml/src/ggml-sycl/fattn-tile.hpp`

Env gate:

- `GGML_SYCL_FATTN_DV512_GQA8_WG512=1`

Patch snapshots:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-wg512-preedit-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-wg512-source.patch`

Hashes:

- preedit source diff: `7220e022ae836b2a885f6e1ba5d73422f1ddd9c74e0c3e4582a0d7066fa295e3`
- experimental source diff: `bf8890ff5b678c99f1794b3490bc609b2446485f0de221d4651a02ee18940673`
- experimental `libggml-sycl.so.0.15.2`: `66dd3c01abf25cc53494555d3c0f701bfc04efc0fe9314db78dd6f9fce9e1573`

Build result: **success**.

## Smoke A/B

Both runs used the same experimental binary, one GPU, one fixed cold
long-context prompt (`lc-12288-early`), `cached_tokens=0`, `MAX_TOKENS=96`,
`CANARY_REPEATS=1`, and the existing service flags:

- `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND=1`
- `LLAMA_EXPERIMENTAL_SWA_FATTN_LEFT_BOUND_MIN_Q=2048`
- `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1`

Candidate additionally set `GGML_SYCL_FATTN_DV512_GQA8_WG512=1`.

| run | gate | cached | prefill tok/s | decode tok/s | TTFT |
| --- | --- | --- | ---: | ---: | ---: |
| `20260702Twg512-smoke1` | pass | 0 | `1233.6752037830677` | `128.11048942756867` | `13.142032805946656` |
| `20260702Twg512-control1` | pass | 0 | `1233.1665281712321` | `128.1957960916284` | `13.147453835001215` |

Delta, candidate vs same-binary control:

- prefill: `+0.041%`
- decode: `-0.067%`
- TTFT: `-0.041%`

Output hashes matched across candidate/control.

## Decision

**No promotion.** The result is effectively neutral and far below the
pre-declared threshold for a broader 4-GPU crossover (`~+1.5%` service prefill
with no decode/TTFT regression). The patch was preserved as an experiment
artifact and should be reverted from the active source before the next lane.

