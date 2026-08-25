# Qwen3.8 27B Q4_K_M TP1 WDC with q6_K reorder suppressed

Date: 2026-08-25

Status: **preregistered; not yet built or measured.**

R4's Q4_K-only force door resolved correctly, but the width-1 q6_K output
head still took its ordinary reorder path and exhausted VRAM on a full
temporary copy. R5 adds a second default-off, explicit door:
`GGML_SYCL_DISABLE_REORDER_Q6K`. It makes `should_reorder_tensor` return false
only for q6_K when requested and prints the resolved door in the banner.

The incremental [q6_K guard patch](../patches/llama-qwen38-disable-q6k-reorder-20260825.patch)
has SHA-256
`5a33ad949bdafd54854563b6df531d78b4ac3208eb33a710fcdcb21b44d60a65`.
Apply it after the [scoped Q4_K reorder patch](../patches/llama-qwen38-q4k-scoped-reorder-20260825.patch).
The resulting complete reconstructed source diff SHA-256 is
`6a6b49a22e09738f5de7bd04f1ac71b4a39d764091c5cf4f02ee0c526dce170f`.

Portable launch after building that source with the existing WDC build script:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q4km \
SOURCE_DIR=/path/to/restored/llama.cpp \
BUILD_DIR=/path/to/new/build-sycl-aot-bmg-g31-wdc-noq6 \
OUT_DIR=/path/to/results \
EXPECTED_DIFF_SHA=6a6b49a22e09738f5de7bd04f1ac71b4a39d764091c5cf4f02ee0c526dce170f \
CAMPAIGN_ID=qwen38-q4km-tp1-wdc-noq6-20260825-r5 \
RUNTIME_PROFILE=wdc-q4k-scoped-noq6 NPL=1,64 ATTEMPT=1 \
  experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-batched-ladder.sh
```

The q6_K output-head path may become slower without reordered MMVQ. R5 must
therefore retain at least 95% of B1 and gain at least 5% at B64 before any
full-ladder work. Even a passing raw screen remains unqualified until the
endpoint sequential-oracle gate passes.
