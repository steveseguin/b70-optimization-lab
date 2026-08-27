# Qwen3.8 27B Q8_0 + Q4_0 MTP2 on one Intel Arc Pro B70

> **Certification: `candidate-portable-repro`, not a starter guide.** The
> model artifacts, source patches, build, launch, strict benchmark, target
> oracle, and fresh-server repeat are closed. A clean-host Intel/oneAPI replay
> and beginner recovery flow are still pending.

This deployment uses Q8_0 target weights and a separate Q4_0 MTP draft at
depth 2. The strict fixed-suite headline is **37.062028 tok/s**, the median of
two fresh servers (`36.848184`, `37.275873`). A matched 1,024-context MTP0
control measured `19.582597 tok/s`, making the gain **89.26%**. All **24/24**
MTP2 output arrays matched the control exactly. Prompt caching, context
checkpoints, response reuse, and learned drafting were disabled.

The result is single-user and short-context. The exact Q8+MTP2 32K and
concurrency cells are unmeasured; do not copy values from the target-only or
Q4+MTP2 packages.

## Download exact artifacts

```bash
huggingface-cli download ggml-org/Qwen3.8-27B-GGUF \
  Qwen3.8-27B-Q8_0.gguf \
  --revision 0669b98607d47046c7c2b3f801011d54a08cfccf \
  --local-dir /path/to/qwen38-q8

huggingface-cli download unsloth/Qwen3.8-27B-GGUF \
  MTP/mtp-Qwen3.8-27B-Q4_0.gguf \
  --revision 4ca720788d1e01f1bff70c033e0d0028fd02e502 \
  --local-dir /path/to/qwen38-draft
```

Pinned SHA-256 identities:

- target: `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- draft: `50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e`

The machine-readable direct-I/O manifests are the existing
[Q8 target manifest](../qwen38-27b-q8-tp1-b70/model-direct.json) and
[Q4 draft manifest](../qwen38-27b-q4km-mtp2-tp1-b70/draft-model-direct.json).

## Restore and build the exact source stack

The builder starts from `mndodd/llama.cpp` commit
`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`, then applies and verifies the six
lab patches listed in [the Q8 base guide](../qwen38-27b-q8-tp1-b70/README.md#exact-dependencies).

```bash
SOURCE_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2 \
CXX_COMPILER=/opt/intel/oneapi/compiler/2026.1/bin/icpx \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/restore-and-build.sh
```

## Verify and launch

```bash
TARGET_DIR=/path/to/qwen38-q8 \
DRAFT_DIR=/path/to/qwen38-draft/MTP \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/preflight.sh

TARGET_DIR=/path/to/qwen38-q8 \
DRAFT_DIR=/path/to/qwen38-draft/MTP \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31 \
  repro/qwen38-27b-q8-q4mtp-mtp2-tp1-b70/run-server.sh
```

The measured server uses one B70, one slot, 1,024 configured context tokens,
F16 target and draft KV, graph off, MTP depth 2, prompt cache off, and raw
native completions. Check it from another terminal:

```bash
curl -fsS http://127.0.0.1:18141/health
```

## Re-run the strict benchmark

Stop any server first. Use new output directories; the runner refuses to
overwrite evidence and requires a clean pushed repository identity.

```bash
MTP_DEPTH=2 ATTEMPT=my-q8-mtp2-a \
TARGET_DIR=/path/to/qwen38-q8 DRAFT_DIR=/path/to/qwen38-draft/MTP \
BUILD_DIR=/path/to/new/llama.cpp-qwen38-q8-mtp2/build-sycl-aot-bmg-g31 \
OUT_DIR=/path/to/new-q8-mtp2-a PORT=18141 \
  experiments/qwen38-27b-b70/scripts/run-20260827-qwen38-q8-q4mtp-tp1-screen-attempt.sh
```

Run a second fresh attempt with a new `ATTEMPT`, `OUT_DIR`, and port, then
require exact token-array agreement with the repository comparator. The
campaign runner itself also compares every speculative array to the frozen
matched MTP0 oracle and fails closed on cache reuse, incomplete streams,
canary failure, or inactive drafting.

Evidence and policy:

- [strict result](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.json)
- [preregistration](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-depth-screen-r1-prereg.json)
- [matched-control amendment](../../experiments/qwen38-27b-b70/data/2026-08-27-qwen38-q8-q4mtp-tp1-depth-screen-r1-control-amendment.json)
- [human-readable result](../../experiments/qwen38-27b-b70/notes/2026-08-27-qwen38-q8-q4mtp-tp1-mtp2-strict-r1-result.md)

Stop the foreground server with `Ctrl-C`; `pgrep -x llama-server` must then
return no process.
