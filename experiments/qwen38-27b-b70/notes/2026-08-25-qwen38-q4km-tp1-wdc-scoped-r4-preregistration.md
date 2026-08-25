# Qwen3.8 27B Q4_K_M TP1 scoped-reorder WDC r4

Date: 2026-08-25

Status: **preregistered; not yet built or measured.**

R1 and r3 proved that broad `GGML_SYCL_FORCE_REORDER=1` exceeds one B70's
device memory when it reaches the 1.27-billion-element q6_K output tensor. R2
proved that `REORDER_IN_GEMM=1` alone remains width-gated and leaves Q4_K WDC
vacuous. R4 changes the source rather than guessing another flag.

The incremental
[patch](../patches/llama-qwen38-q4k-scoped-reorder-20260825.patch) adds one
default-off runtime door: `GGML_SYCL_FORCE_REORDER_Q4K`. It bypasses the width
predicate only when the weight type is Q4_K and prints its resolved value in
the door banner. The broad test hook is left unchanged. Patch SHA-256 is
`519bb0005d815c73a807dbf7f6ef196b31d61597bad3dc82b68d156259f8f261`;
the complete reconstructed source diff SHA-256 is
`3d2ab1e5b6820cf05874377510cc4ee4168190290e65af7b8621a4e032b8493b`.

Portable build and launch:

```bash
SOURCE_DIR=/path/to/restored/llama.cpp \
BUILD_DIR=/path/to/new/build-sycl-aot-bmg-g31-wdc-scoped \
EXPECTED_DIFF_SHA=3d2ab1e5b6820cf05874377510cc4ee4168190290e65af7b8621a4e032b8493b \
  experiments/qwen38-27b-b70/scripts/build-qwen38-q4km-tp1-wdc-batched-r1.sh

MODEL_DIR=/path/to/qwen3.8-27b-q4km \
SOURCE_DIR=/path/to/restored/llama.cpp \
BUILD_DIR=/path/to/new/build-sycl-aot-bmg-g31-wdc-scoped \
OUT_DIR=/path/to/results \
EXPECTED_DIFF_SHA=3d2ab1e5b6820cf05874377510cc4ee4168190290e65af7b8621a4e032b8493b \
CAMPAIGN_ID=qwen38-q4km-tp1-wdc-scoped-20260825-r4 \
RUNTIME_PROFILE=wdc-q4k-scoped NPL=1,64 ATTEMPT=1 \
  experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-batched-ladder.sh
```

The screen advances only with a clean Q4_K WDC census and the frozen speed
thresholds. Raw success still does not establish output quality or concurrent
HTTP serving; those require the endpoint sequential-oracle harness.
