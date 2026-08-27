# Qwen3.8 27B Q8_0 on one Intel Arc Pro B70

> **Certification: `candidate-portable-repro`, not a starter guide.** The
> model, source, patch, build, launch, depth benchmark, and service-quality
> identities are closed. Intel driver/oneAPI installation and a clean-host
> replay are still pending.

This is the repository's quality-conservative one-card Qwen3.8 GGUF lane. It
uses Q8_0 weights, F16 KV, one server slot, and no draft model or speculative
decoding. The raw-engine tg128 curve measured `19.662501 tok/s` at depth zero
and `18.023689 tok/s` at 32K. These are direct `llama-bench` rates, not HTTP or
realistic-prompt headline rates; no featured package speed is currently
claimed. The matching service tuple separately passed
7/7 canaries, 8/8 repeat stability, a 7,617-token needle test, and zero cached
tokens on all 16 responses. A separate output-audited HTTP profile uses eight
active slots and queues up to 64 simultaneous requests, reaching a stable
`68.555544 tok/s` aggregate at 64 requests.

## Exact dependencies

- Model: [`model-direct.json`](model-direct.json), revision
  `0669b98607d47046c7c2b3f801011d54a08cfccf`, Q8_0 SHA-256
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`.
- Runtime base: `mndodd/llama.cpp` commit
  `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`.
- Build: [`restore-and-build.sh`](restore-and-build.sh), which delegates by a
  relative repository path to the shared, hash-verifying Qwen3.8 TP1 builder.
- Tested compiler identity: Intel oneAPI 2026.1.1 selected with
  `CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx`.

The exact tested binary retained the complete lab patch stack. The builder
decodes, hashes, and applies these in order:

1. [Full Qwen3.6/Q8 SYCL stack](../../patches/qwen36-27b-q8-tp2-asrock-b70/llama-cpp-mndodd-4302fb599-lab-tp2-dp4a2-20260815.diff.gz.b64) (`f21e9b557c3d024527ac98d5f189cf7ea72fa8c38a5faf2a22ee339fd1988998`).
2. [Qwen3.8 Q4-shape increment](../../patches/qwen38-27b-q4km-tp2-asrock-b70/llama-cpp-q4k-mmvq-swiglu-tp2-20260815.diff.gz.b64) (`0a27858525f6a402cf9c92d1b93daee0a80e2ffaef9137bf7bce784a549b58b6`; retained in the exact build, Q4-specific paths are inert for Q8 weights).
3. [TP1 GDN state-I/O widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-gdn-state-io-widen-20260821.diff.gz.b64) (`1377fd89ea595f4d6e0654ce07387f9e0c2438f6677360c4c94cd99072ce6272`).
4. [TP1 convolution/QK widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-conv-qk-widen-20260821.diff.gz.b64) (`5b0141e3ef6be67365e638ef796247e25280b1bf1e7c11e61c77aba0657fcb7b`).
5. [TP1 QK source-shape widening](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-qk-norm-rope-src-widen-20260821.diff.gz.b64) (`8299e77c2186bc2d024c1a9030ed69aafcad26442296a68523dde1a1b6d46c7e`).
6. [Memo hardening artifact](../../patches/qwen38-27b-q4km-tp1-b70s/llama-cpp-tp1-q8out-rejected-memo320-20260821.diff.gz.b64) (`717bc1cc3eda198ded7df4e2a0046fd1ce88434c47e702feecaf4dff258142d0`; the rejected Q8-output door remains disabled).

## Download, build, and preflight

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q8_0.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen3.8-27b-q8

SOURCE_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1 \
CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  repro/qwen38-27b-q8-tp1-b70/restore-and-build.sh

MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-tp1-b70/preflight.sh
```

Preflight reads the 28.60 GB model through direct and ordinary I/O and requires
both hashes. The tested small host had 16 GB nominal RAM plus swap; the runner
caps the server at 13 GiB host memory and 12 GiB swap. A 32 GB or larger host
is simpler. Model weights reside primarily in B70 VRAM.

## Launch and quality validation

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
GPU_INDEX=0 repro/qwen38-27b-q8-tp1-b70/run-server.sh
```

For the exact long-context quality battery, download only the pinned tokenizer
metadata (not the AutoRound weights) and install `transformers==5.10.2` in a
virtual environment:

```bash
huggingface-cli download devan-carlin/Qwen3.8-27B-int4-AutoRound \
  config.json tokenizer.json tokenizer_config.json \
  --revision bce40cacab0a4535b92fb3d57615c2bea9adf3d1 \
  --local-dir /path/to/qwen3.8-tokenizer

TOKENIZER_DIR=/path/to/qwen3.8-tokenizer PYTHON=/path/to/venv/bin/python \
OUT=/path/to/quality.json repro/qwen38-27b-q8-tp1-b70/quality.sh
```

Success prints `service_quality_passed=true` and
`cached_tokens_all_zero=true`. Stop the foreground server with `Ctrl-C` and
confirm `pgrep -x llama-server` returns no process.

For aggregate serving, launch the exact qualified eight-slot/4K-total-context
profile instead. Requests above eight wait in the server queue; they do not
allocate additional GPU slots.

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
GPU_INDEX=0 repro/qwen38-27b-q8-tp1-b70/run-throughput-server.sh
```

The measured 1/2/4/8/16/32/64-request aggregate curve is in the
[qualified result](../../experiments/qwen38-27b-b70/data/2026-08-25-qwen38-q8-tp1-http-p8-queue-concurrency-r5-result.json).
All points are medians of two fresh servers with complete raw token IDs and
zero prompt-cache reuse. The p64/32K and p32/16K F16-KV profiles are retained
allocation failures; p16/8K fits but loses aggregate throughput above eight
users. The queue profile does not qualify queued TTFT or per-request latency.

To reproduce one exact output-audited curve attempt, stop any running server
and invoke the retained fail-closed wrapper. It verifies model and binary
hashes, acquires the GPU locks, starts a fresh p8 service, sends the frozen
1/2/4/8/16/32/64-request suite, and rejects incomplete, cached, or cross-task
output. Use a new `ATTEMPT` value rather than overwriting evidence.

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
OUT_DIR=/path/to/results ATTEMPT=1 PORT=18088 \
  experiments/qwen38-27b-b70/scripts/run-qwen38-q8-tp1-http-p8-queue-concurrency-r5.sh
```

## Reproduce the measured context curve

Run this with no server active. It performs 5 repetitions for pp2048 and tg128
at every exact depth from 0 through 32K; it does not interpolate points.

```bash
MODEL_DIR=/path/to/qwen3.8-27b-q8 \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-tp1/build-sycl-aot-bmg-g31 \
OUT=/path/to/depth.json repro/qwen38-27b-q8-tp1-b70/bench-depth.sh
```

Measured evidence: [depth result](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q8weights-f16-tp1-local-r2-result.md)
and [service-quality result](../../experiments/qwen38-27b-b70/notes/2026-08-25-qwen38-q8weights-f16-tp1-service-quality-r1-result.md).
Still open: clean-host platform/build replay, a conventional realistic-prompt
HTTP speed capture, TTFT by context, and queued per-request latency.
