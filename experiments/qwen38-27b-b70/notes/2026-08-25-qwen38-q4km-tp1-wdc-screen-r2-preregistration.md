# Qwen3.8 27B Q4_K_M TP1 Q4_K-only WDC screen r2

Date: 2026-08-25

Status: **preregistered after r1 failed before measurement.**

R1 reached no benchmark row. During the first warm-up it exhausted device
memory while making a full temporary copy of the 1.27-billion-element q6_K
output tensor. The r1 recipe incorrectly set `GGML_SYCL_FORCE_REORDER=1`,
which the source identifies as a test hook. The DNN build also resolved the
integration branch's unrelated default-on q8_0 WDC door.

The [r2 manifest](../data/2026-08-25-qwen38-q4km-tp1-wdc-screen-r2.json)
freezes the correction before retrying: remove `FORCE_REORDER`, set the master
WDC list to `off`, then override only `GGML_SYCL_WDC_Q4K=1`. The build, model,
matrix, advancement thresholds, and quality boundary remain unchanged.

Portable stage-1 launch:

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q4km \
SOURCE_DIR=/path/to/restored/llama.cpp \
BUILD_DIR=/path/to/new/build-sycl-aot-bmg-g31-wdc \
OUT_DIR=/path/to/results \
CAMPAIGN_ID=qwen38-q4km-tp1-wdc-screen-20260825-r2 \
RUNTIME_PROFILE=wdc-q4k NPL=1,64 ATTEMPT=1 \
  experiments/qwen38-27b-b70/scripts/run-qwen38-q4km-tp1-batched-ladder.sh
```

As before, any speed row remains raw random-token mechanism evidence. It
cannot be promoted as concurrent serving without the endpoint sequential
oracle gate.
