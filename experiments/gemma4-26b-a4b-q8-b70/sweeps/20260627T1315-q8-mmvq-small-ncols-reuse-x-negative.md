# 2026-06-27T13:15Z - Q8 MMVQ Small-Ncols X-Reuse Is Negative

## Question

Can the hot `Q8_0 x Q8_1` multi-column MMVQ path be improved by loading each
`Q8_0` weight block once per lane and reusing it across destination columns
2..8?

This targeted the generic non-reordered path:

- source: `/home/steve/src/llama.cpp-gemma-record-repro-c926/ggml/src/ggml-sycl/mmvq.cpp`;
- flag: `LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS=1`;
- patch snapshot:
  `patches/gemma4-26b-a4b-q8-b70/q8-mmvq-small-ncols-reuse-x-negative-20260627.patch`.

The idea came from node profiles showing `MUL_MAT_ID` / Q8 MMVQ body time as
the dominant verifier-side cost. Route-cache plumbing is already known to be a
small edge.

## Build

Built successfully:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31 --target llama-server -j 12
```

The AOT link completed with normal spill warnings.

## Paired Screen

Both runs used the rebuilt binary, current record recipe, Q8 target/verifier,
Q4_0 MTP draft, `UBATCH_SIZE=768`, filled-long `p512/o512`, one benchmark row,
and 64 canary repeats / 256 canary rows.

| run | GPU | flag | canary | fresh row0 tok/s | wall tok/s | output hash |
| --- | --- | --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu1-q8mmvq-smallncols-ub768-screen-20260627T131520Z` | 1 | `LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS=1` | 256/256 | `102.340539553` | `89.307105256` | `d3236ebed08d...` |
| `gemma4-q8-gpu2-q8mmvq-control-ub768-screen-20260627T131542Z` | 2 | `LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS=0` | 256/256 | `104.236784884` | `90.716840919` | `d4cf5f90168b...` |

Artifacts:

- `data/gemma4-q8-gpu1-q8mmvq-smallncols-ub768-screen-20260627T131520Z/summary.json`;
- `data/gemma4-q8-gpu2-q8mmvq-control-ub768-screen-20260627T131542Z/summary.json`;
- server logs under `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/`.

## Decision

Negative. The specialization is slower than paired control by about `1.90 tok/s`
fresh row0 and also changes the deterministic long-output hash/format. Canaries
passed, but the speed and output-shape signals both argue against promotion.

Do not submit to LocalMaxxing. Do not rerun unless a future profile shows this
kernel form was not reached or a more precise body-specialization changes the
register/occupancy tradeoff.

After recording the patch, the source change was reverted so the source tree
returns toward the known-good Gemma stack. The run-identity harness change that
records `LLAMA_SYCL_Q8_MMVQ_SMALL_NCOLS` should remain useful for future tests.

## Follow-Up

The next higher-ROI lanes remain:

1. candidate-vs-max verifier for drafted tokens, avoiding full logits/argmax
   materialization where possible;
2. more specific `MUL_MAT_ID` Q8 body work for actual MoE verifier shapes
   (`gate_up` vs `down`) rather than generic multi-column MMVQ;
3. compact direct-unroll confidence scores for current `n=7`, if quality can be
   preserved without warmed-history assumptions.
