# Qwen3.8 27B Q4_K_M TP1 Q4_K WDC screen preregistration

Date: 2026-08-25

Status: **preregistered; candidate not yet built or measured.**

The completed DNN-off ladder peaks at `95.411842 tok/s` raw aggregate at 64
parallel sequences. The source contains a default-off Q4_K oneDNN
weight-decompression GEMM with measured shape guards, but no Qwen3.8
end-to-end evidence. This screen tests that transfer rather than treating
source comments from another model/shape as a result.

The [manifest](../data/2026-08-25-qwen38-q4km-tp1-wdc-screen-r1.json)
freezes the delta. Stage 1 measures only parallel 1 and 64. It advances to the
full seven-point ladder only if B64 improves by at least 5%, B1 retains at
least 95% of control, the banner proves non-mutant Q4_K WDC is compiled and
enabled, a WDC census proves engagement, and the process completes cleanly.
These thresholds decide whether to spend more benchmark time; they are not
validity gates and do not authorize publication.

Portable build and stage-1 launch:

```bash
SOURCE_DIR=/path/to/restored/llama.cpp \
BUILD_DIR=/path/to/new/build-sycl-aot-bmg-g31-wdc \
  experiments/qwen38-27b-b70/scripts/build-qwen38-q4km-tp1-wdc-batched-r1.sh

MODEL_DIR=/path/to/qwen3.8-27b-q4km \
SOURCE_DIR=/path/to/restored/llama.cpp \
BUILD_DIR=/path/to/new/build-sycl-aot-bmg-g31-wdc \
OUT_DIR=/path/to/results \
CAMPAIGN_ID=qwen38-q4km-tp1-wdc-screen-20260825-r1 \
RUNTIME_PROFILE=wdc-q4k NPL=1,64 ATTEMPT=1 \
  experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-batched-ladder.sh
```

Even a large raw gain remains mechanism evidence. Promotion requires the
separate endpoint concurrency harness with complete outputs and each prompt's
same-server sequential oracle.
