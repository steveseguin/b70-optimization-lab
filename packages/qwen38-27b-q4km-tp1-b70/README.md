# Qwen3.8 27B Q4_K_M — one-B70 candidate package

This is the user-facing front door for our validated one-card Qwen3.8 lane:
`27.81–27.82 tok/s`, target-only, cache-zero, and exact against the registered
12-prompt oracle. The full semantic/repeat/needle battery also passed.

> **Status: candidate, not a beginner install guide.** Model, source, patch,
> build, launch, and result identities are present. The Intel driver and
> oneAPI installation have not yet been rebuilt and tested from a clean OS.

Use the [reproduction guide](../../repro/qwen38-27b-q4km-tp1-b70/README.md)
for the complete procedure. It includes every required repository patch and
its decoded SHA-256, rather than sending users to a detached recipe.

The short sequence is:

```bash
# Download the pinned GGUF (see the guide for the exact command).

SOURCE_DIR=/path/to/new/llama.cpp-qwen38-tp1 \
  repro/qwen38-27b-q4km-tp1-b70/restore-and-build.sh

MODEL_DIR=/path/to/qwen3.8-27b-q4km \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q4km-tp1-b70/preflight.sh

MODEL_DIR=/path/to/qwen3.8-27b-q4km \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-tp1/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q4km-tp1-b70/run-server.sh
```

Then run `bench.sh` from another terminal. Do not compare or publish the
speed unless its cache-zero, freshness, and 12/12 exact-output gates pass.
