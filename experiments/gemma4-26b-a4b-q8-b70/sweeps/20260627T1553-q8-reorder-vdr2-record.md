# 2026-06-27T1553 - Q8 reorder VDR=2 fresh-response record

## Summary

Outcome: **win, promoted, LocalMaxxing approved**.

The reordered Q8_0 MMVQ body was still using the upstream/default vector
dequant ratio (`vdr_mmvq=4`). A small default-preserving source patch made this
ratio compile-time selectable:

- patch: `patches/gemma4-26b-a4b-q8-b70/q8-reorder-vdr-compile-knob-20260627.patch`
- source: `/home/steve/src/llama.cpp-gemma-record-repro-c926/ggml/src/ggml-sycl/quants.hpp`
- default remains `GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=4`;
- record build uses `-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2`.

This was tested on the current fresh-response record stack:

- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`;
- MTP draft only: `gemma-4-26B-A4B-it-Q4_0-MTP.gguf`;
- one Intel Arc Pro B70, `ONEAPI_DEVICE_SELECTOR=level_zero:0`;
- `UBATCH_SIZE=720`, `BATCH_SIZE=1024`, `POLL=100`, `THREADS=8`;
- `--spec-draft-n-max 7`, `--spec-draft-n-min 3`,
  `--spec-draft-p-min 0.10`, backend sampling off;
- no n-gram/history acceleration, no context checkpoints.

## Result

Full confirmation:

- run dir:
  `data/gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z/`
- summary:
  `data/gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z/summary.json`
- benchmark:
  `data/gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z/p512o512.json`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm-20260627T155347Z.server.log`

| Metric | Value |
| --- | ---: |
| Canary | `6144/6144` |
| Fresh row0 after-TTFT tok/s | `176.21623213048554` |
| Support mean after-TTFT tok/s | `176.40259133127742` |
| Fresh row0 wall tok/s | `139.3169544024847` |
| Support mean wall tok/s | `148.0935352276448` |
| Prompt / output tokens | `588 / 512` |
| Row cached tokens | `[0, 0, 0]` |

Fresh-response validity:

- headline is row0 only;
- row0 reports `usage.prompt_tokens_details.cached_tokens=0`;
- rows 1-2 repeat the same prompt and are support/stability only;
- draft source is the current-request Gemma MTP draft, not previously learned
  repeated continuation history.

LocalMaxxing:

- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627.queue.json`
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-q8reorder-vdr2-ub720-nmin3-pmin010-fresh-20260627.submit.log`
- approved ID: `cmqwkedg303jeqr013z753j62`

## Comparison

Previous approved record:

- run:
  `data/gemma4-q8-gpu0-q8reorder-ub720-nmin3-pmin010-fullconfirm-20260627T144855Z/`
- LocalMaxxing: `cmqwi45d803gyqr01td3vf9ka`
- fresh row0: `171.1076295077342 tok/s`
- support mean: `170.12922191012277 tok/s`

VDR=2 improves row0 by `+5.10860262375134 tok/s` and support mean by about
`+6.27337 tok/s` with the same quality lane and canary depth.

## Build

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
source /opt/intel/oneapi/setvars.sh
cmake -S . -B build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icx \
  -DCMAKE_CXX_COMPILER=/opt/intel/oneapi/compiler/2026.0/bin/icpx \
  -DCMAKE_CXX_FLAGS='-DGGML_SYCL_REORDER_Q8_0_VDR_MMVQ=2' \
  -DGGML_SYCL=ON -DGGML_SYCL_TARGET=INTEL \
  -DGGML_SYCL_DEVICE_ARCH=bmg-g31 \
  -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON -DGGML_SYCL_DNN=ON \
  -DGGML_SYCL_HOST_MEM_FALLBACK=ON
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 \
  --target llama-server -j 8
```

Binary:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server
```

## Reproduce

```bash
cd /home/steve/qwen36-results-main
EXTRA='--parallel 1 --cache-ram 0 --spec-type draft-mtp --spec-draft-model /mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf --spec-draft-n-max 7 --spec-draft-device SYCL0 --spec-draft-ngl all --spec-draft-type-k f16 --spec-draft-type-v f16 --spec-draft-n-min 3 --spec-draft-p-min 0.10 --no-spec-draft-backend-sampling --spec-draft-threads 32 --spec-draft-threads-batch 32 --ctx-checkpoints 0'

ONEAPI_DEVICE_SELECTOR=level_zero:0 \
UR_L0_USE_IMMEDIATE_COMMANDLISTS=1 \
GGML_SYCL_DISABLE_OPT=0 GGML_SYCL_DISABLE_GRAPH=0 GGML_SYCL_ENABLE_VMM=0 \
LLAMA_SERVER=/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server \
MODEL=/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf \
EXTRA_LLAMA_ARGS="$EXTRA" \
LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1 \
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER=1 \
LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1 \
LLAMA_MTP_DEFER_TARGET_H_NEXTN=1 \
LLAMA_MTP_DRAFT_FAST_ARGMAX=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_IDS=1 \
LLAMA_MTP_DRAFT_DIRECT_ARGMAX_UNROLL=7 \
LLAMA_GEMMA4_MTP_QONLY_ATTN_INPUTS=1 \
LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX=1 \
LLAMA_GEMMA4_MOE_SELECTED_SOFTMAX_FUSED=1 \
LLAMA_GEMMA4_MOE_WEIGHTED_SUM=1 \
LLAMA_GEMMA4_MOE_REUSE_ATTN_RMS=1 \
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1 \
GPU_INDEX=0 PORT=18310 \
LABEL=gemma4-q8-gpu0-q8reorder-vdr2-ub720-nmin3-pmin010-fullconfirm \
CTX_SIZE=8192 BATCH_SIZE=1024 UBATCH_SIZE=720 POLL=100 THREADS=8 \
FLASH_ATTN=off REASONING=off \
CANARY_REPEATS=1536 BENCH_REPEATS=3 \
PROMPT_TOKENS=512 MAX_TOKENS=512 BENCH_PROMPT_MODE=filled-long \
scripts/run-gemma4-26b-first-baseline.sh
```

## Next

Try `GGML_SYCL_REORDER_Q8_0_VDR_MMVQ=1` and `=8` as separate builds/runs.
Keep each variant isolated because this knob changes the compiled kernel body.
Do not combine this with other source changes until the VDR sweep is complete.
