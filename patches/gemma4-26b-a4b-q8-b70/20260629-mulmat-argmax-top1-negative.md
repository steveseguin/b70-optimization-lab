# 2026-06-29: `ggml_mul_mat_argmax` top-1-only reduction is negative

## Hypothesis

The current Gemma 4 26B Q8 record uses top-1 sampled IDs on the MTP draft path,
and the verifier fused-output-argmax path also only needs top-1 IDs for normal
verification. The existing SYCL `ggml_mul_mat_argmax` kernels still carry
top-2 bookkeeping in tile and final reductions even when `top2=false`.

Experiment patch:

- `patches/gemma4-26b-a4b-q8-b70/20260629-mulmat-argmax-top1-negative.patch`

The patch adds explicit `top2` branches in four tile kernels and two final
reduction kernels so `top2=false` only propagates the best value/index.

## Validation

Source: `/home/steve/src/llama.cpp-gemma-record-repro-c926`

Build:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

Screen command shape: four one-B70 replicas through the promoted
`repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh` wrapper, with
`MAX_TOKENS=128`, `CANARY_REPEATS=32`, `REALISTIC_GATE=1`, `cached_tokens=0`
on every prompt.

## Results

All rows below passed the fixed realistic gate and 128/128 canary rows. Primary
metric is median generated-token throughput for tokens 1-100 after TTFT.

| Variant | Result path | Median tok/s | Decision |
| --- | --- | ---: | --- |
| default patched binary | `data/gemma4-q8-gpu0-top1argmaxpatch-default-strict128-20260629E2/summary.json` | `114.26445465394764` | negative vs `115.72789384447941` record |
| `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=16` | `data/gemma4-q8-gpu1-top1argmaxpatch-tile16-strict128-20260629E2/summary.json` | `113.83871436968641` | negative |
| `LLAMA_SYCL_MUL_MAT_ARGMAX_TILE_SUBGROUPS=8` | `data/gemma4-q8-gpu2-top1argmaxpatch-tile8-strict128-20260629E2/summary.json` | `111.14857674410214` | negative |
| `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` | `data/gemma4-q8-gpu3-top1argmaxpatch-fusedverify-strict128-20260629E2/summary.json` | `95.77148113932887` | still far slower than backend argmax |

The patch does not improve the default record path and does not rescue the
model-specific fused verifier argmax path. The active source file was restored
to the pre-experiment VDR2 selected-down record snapshot after this run.

## Follow-up

Do not retry this exact top-1-only split. The remaining verifier-cost direction
should avoid the existing scratch-heavy `ggml_mul_mat_argmax` path entirely or
change the graph shape, for example a same-graph head-only bonus path or a new
compact argmax epilogue that reuses the faster regular Q8 LM-head structure.
