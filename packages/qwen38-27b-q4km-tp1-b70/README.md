# Qwen3.8 27B Q4_K_M — one-B70 candidate package

This is the user-facing front door for our validated one-card Qwen3.8 lane:
`27.81–27.82 tok/s`, target-only, cache-zero, and exact against the registered
12-prompt oracle. The full semantic/repeat/needle battery also passed.

> **Status: candidate, not a beginner install guide.** Model, source, patch,
> build, launch, and result identities are present. The Intel driver and
> oneAPI installation have not yet been rebuilt and tested from a clean OS.

The restore script initializes the oneAPI environment, verifies every decoded
patch, disables the unused Web UI/download path, and builds the server plus
`llama-bench` and `llama-batched-bench`. `CXX_COMPILER` may select another
installed compiler only as a clearly separate experimental identity; it does
not reproduce the 2026.0.0 headline by implication.

Use the [reproduction guide](../../repro/qwen38-27b-q4km-tp1-b70/README.md)
for the complete procedure. It includes every required repository patch and
its decoded SHA-256, rather than sending users to a detached recipe.

## Context length and KV-cache dtype (measured 2026-08-22)

A single-card `llama-bench` sweep (raw-engine tg128/pp2048, flash-attn on,
5 reps; different metric from the `27.82` headline) maps how this lane behaves
as context grows and whether to use an 8-bit KV cache:

| context | decode KV f16 | decode KV q8_0 | prefill KV f16 |
| ---: | ---: | ---: | ---: |
| 0 | 24.81 | 24.27 | 825 |
| 8K | 23.83 | 18.68 | 851 |
| 16K | 23.10 | 14.86 | 780 |
| 32K | 21.77 | **10.66** | 668 |

**Keep the KV cache at f16 for speed.** Decode with f16 KV stays nearly flat
out to 32K (−12%), but the q8_0-KV decode penalty grows with context (~2% at
0 → **−51% at 32K**) because per-token KV dequant scales with cached length.
Prefill is unaffected by KV dtype (<1.5%). Use q8_0 KV only to fit longer
context into 32 GiB. Full data:
[sweep JSON](../../experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.json),
[chart](../../experiments/qwen38-27b-b70/data/2026-08-22-q4km-tp1-context-kv-sweep.svg).

## Who built what

- **neural.download lab — integrated:** Qwen3.8 Q4_K_M bring-up, the complete
  lab kernel stack, TP1 fusion increments, packaging, and validation. The
  matched TP1 ladder moved `26.047863/26.068073` to
  `27.813629/27.824790 tok/s` (`+6.8%` to `+7.0%`) with 24/24 oracle-exact
  outputs and the full quality battery passing. See the
  [TP1 patch evidence](../../patches/qwen38-27b-q4km-tp1-b70s/README.md).
- **[mndodd](https://github.com/mndodd) — integrated:** optimized Intel SYCL
  llama.cpp fork used as the pinned runtime base beneath our Qwen3.8 patches.
  Its separately matched Qwen3.6 Q8 TP2 control measured `31.338765` versus
  `29.610651 tok/s` (`+5.836%`). That exact contribution is credited here;
  the later Qwen3.8 package result remains our separately measured lane. See
  the [lab validation](../../community/mndodd-qwen36-27b-llamacpp-sycl/STATUS.md).

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
