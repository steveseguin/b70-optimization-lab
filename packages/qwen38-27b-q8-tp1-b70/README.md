# Qwen3.8 27B Q8_0 — one-B70 candidate package

This is the quality-conservative one-card Qwen3.8 option: Q8_0 weights, F16
KV, target-only decoding, and no speculative helper. The exact raw-engine
tg128 curve measured `19.662501 tok/s` at depth zero and `18.023689 tok/s` at
32K. Prefill pp2048 measured `996.891020` and `719.144647 tok/s` at those same
depths. Every displayed marker is a five-repetition measurement.

The matching OpenAI-compatible service separately passed 7/7 semantic
canaries, 8/8 repeat stability, a 7,617-token needle, and explicit zero cached
tokens on all 16 requests. The raw-engine rate is not relabeled as HTTP or
realistic-prompt speed.

> **Status: candidate.** The model, source patches, build, launch, depth
> benchmark, and quality checks are closed in this repository. A clean Ubuntu
> host installation/replay, beginner recovery path, realistic HTTP speed, and
> qualified concurrency curve remain open.

Use the [complete reproduction guide](../../repro/qwen38-27b-q8-tp1-b70/README.md).
It includes the pinned download, direct-read verification, specific patch
links and decoded hashes, relative build entry point, launch command, quality
battery, and exact context sweep.

## Measured context behavior

| existing context | raw tg128 | raw pp2048 |
| ---: | ---: | ---: |
| 0 | 19.662501 | 996.891020 |
| 8K | 19.293993 | 914.062353 |
| 16K | 18.838870 | 837.512717 |
| 32K | 18.023689 | 719.144647 |

Decode declines only 8.3% from 0 to 32K with F16 KV; prefill declines 27.9%.
Those are measured endpoint comparisons, not an interpolated curve. See the
[full evidence](../../experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-local-20260825-r2/result.json)
and [quality qualification](../../experiments/qwen38-27b-b70/data/qwen38-q8weights-f16-tp1-service-quality-20260825-r1/qualification.json).

## Short path

```bash
# First download the exact GGUF using the command in the guide.
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1 \
CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  repro/qwen38-27b-q8-tp1-b70/restore-and-build.sh

MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-tp1-b70/preflight.sh

MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-tp1-b70/run-server.sh
```

The guide's `quality.sh` is the promotion gate. The separate
`bench-depth.sh` reproduces the displayed raw-engine curves when no server is
running.
