# Qwen3.8 27B Q8_0 + MTP2 — one-B70 candidate package

This package keeps the quality-conservative Q8_0 target and adds the pinned
Q4_0 MTP draft at depth 2. Two fresh servers measured a strict
**37.062028 tok/s** class-balanced median versus **19.582597 tok/s** for the
configuration-matched MTP0 control: **+89.26%**. All **24/24** speculative
output arrays were exact to control, every prompt reported cache zero, and all
objective canaries passed.

MTP1 also passed at `30.260758 tok/s`, but MTP2 was faster. No 32K or
concurrency value has been measured for this exact Q8+MTP2 deployment, so
those cells remain explicitly open.

> **Status: candidate.** The exact artifacts, patch stack, launch, strict
> suite, target oracle, and fresh-server repeat are closed in this repository.
> Clean-host installation/replay and beginner recovery remain open.

Use the [complete reproduction guide](../../repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/README.md).

## Short path

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2 \
CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/restore-and-build.sh

TARGET_DIR=/path/to/qwen38-q8 \
DRAFT_DIR=/path/to/qwen38-draft/MTP \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/preflight.sh

TARGET_DIR=/path/to/qwen38-q8 \
DRAFT_DIR=/path/to/qwen38-draft/MTP \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/run-server.sh
```

Evidence: [strict aggregate](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.json).
