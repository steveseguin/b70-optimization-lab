# Qwen3.6 27B Q8_0 GGUF on one B70

Status: artifact verified on USB; GPU bring-up pending. No result is promoted
from this lane yet.

## Scope

This lane has one primary identity:

- target-only `Qwen3.6-27B-Q8_0.gguf`;
- text-only, with no multimodal projector;
- one Intel Arc Pro B70 with 32 GiB VRAM;
- target context ceiling of 32,768 tokens;
- no MTP, DFlash, n-gram, prompt-cache, or response-cache acceleration.

MTP and vision are optional follow-ups. They must not be mixed into the target-only baseline identity or result packet.

`UD-Q8_K_XL` is excluded from the one-card lane because its file is already larger than one B70 before KV cache and runtime buffers. `Q8_0` is the intended Q8 fit candidate.

## Pinned model

- Repository: `unsloth/Qwen3.6-27B-GGUF`
- Revision: `82d411acf4a06cfb8d9b073a5211bf410bfc29bf`
- File: `Qwen3.6-27B-Q8_0.gguf`
- Size: `28,595,763,424` bytes (`26.631880 GiB`)
- SHA-256: `f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce`
- Canonical USB path: `/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf`

The machine-readable identity is in [`model-manifest.json`](model-manifest.json).
The canonical USB file independently passed the declared size and SHA-256.
Its GGUF table has 64 blocks (`0` through `63`), no block-64 tensors, and no
MTP/projector/vision-named metadata or tensors. The internal staging copy was
removed only after the USB checksum passed.

## Fit expectation

The GGUF file is 26.63 GiB, leaving about 5.37 GiB of nominal device memory on a 32 GiB card before KV cache, recurrent state, compute buffers, and backend workspaces.

Qwen3.6 27B has 64 layers with conventional attention every fourth layer. With 16 conventional-attention layers, four KV heads, head dimension 256, and F16 K/V, the conventional KV allocation is approximately 64 KiB per token, or 2 GiB at 32,768 tokens. This makes F16 KV plausible but tight. It remains an unverified capacity estimate until the server loads and completes the 32K retrieval gate.

Validation order:

1. 4K target-only compatibility smoke with a 4K F16-KV allocation and full GPU offload.
2. Fixed cold realistic suite through llama.cpp's native streaming endpoint to establish the Q8_0 exact-token regression oracle and conventional 100-event/99-interval baseline speed.
3. A separately labeled 32K F16-KV allocation and calibrated long-context retrieval gate.
4. Q8_0 KV only if F16 KV cannot retain safe headroom. Treat Q8 KV as a separate quality identity and compare it against the F16-KV oracle.
5. Optional MTP only after the target-only 32K baseline passes. Use an integrated publisher artifact, or a same-publisher and same-revision target/MTP pair; do not cross-pair converters without tensor and metadata validation, and do not graft the third-party head-only extraction into the baseline.

If full GPU offload fails even with Q8 KV and a smaller microbatch, do not hide that result with CPU layer offload. The product goal is one fast, independent B70 lane, so partial offload is a separate capacity diagnostic rather than a successful configuration.

## Historical evidence

A historically recorded local May 2026 `ggml-org` Q8_0 artifact of the same model family fit one B70 and measured `15.275 tok/s` at p512/n128 with F16 KV. That historical file differed by 928 bytes from today's pinned Unsloth artifact, its SHA/revision and full command were not retained, and the raw logs and old source tree were later removed for disk pressure. It is a trend anchor, not a strict reproduction or a 32K proof.

The preserved summary is [`results/qwen36-b70-followup-2026-05-04-q8-allreduce-profiling.md`](../../results/qwen36-b70-followup-2026-05-04-q8-allreduce-profiling.md). The deletion is recorded in [`notes/2026-05-07-model-retention-cleanup.md`](../../notes/2026-05-07-model-retention-cleanup.md).

The later Q4_0/DFlash lane contains relevant benchmark and speculative-decoding lessons but not a Q8 target kernel result. In particular, the locally named Q8 fusion flags optimized Q8_1 activations feeding Q4 weights and must not be carried into this baseline. See [`notes/2026-07-13-qwen27-dflash-sycl-closure.md`](../../notes/2026-07-13-qwen27-dflash-sycl-closure.md).

## Runtime identity

Initial compatibility smoke uses the archived community-validation build:

- llama.cpp commit `15586e2d7165570fb3aa7c26e0d442e289ef69de`;
- runtime version `10298 (15586e2d7)`;
- IntelLLVM / oneAPI 2026.0.0;
- restored path `/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server`;
- archive `/mnt/usb-models/models/runtime-builds/llama.cpp-15586e2d7-oneapi2026.0-sycl-worktree.tar.zst`;
- archive SHA-256 `0ab088aac2cb2c12331fd18c4dbda4a30228a25e06bc2a8a95f770693da8d4d8`.

This build is a reproducible compatibility baseline, not automatically the optimization winner. Before source changes, create a dedicated clean worktree and preserve its commit, build flags, binary hash, and patch. Do not modify `/home/steve/src/llama.cpp`; that tree contains protected Q4/DFlash experiments.

## Four-GPU use

Four one-card processes can be used for independent functional or optimization lanes, each with its own source worktree, port, GPU ordinal, and run directory. Official throughput comparisons remain one active model at a time with the other cards idle, unless the result is explicitly labeled as simultaneous multi-service throughput. This avoids host, USB, power, and thermal interference in single-card timing.

## Entry points

- Target-only server: [`scripts/serve-target-only.sh`](scripts/serve-target-only.sh)
- Validation runner: [`scripts/run-validation.sh`](scripts/run-validation.sh)
- Exact emitted-token capture/comparison and 99-interval primary metric: [`scripts/capture-exact-tokens.py`](scripts/capture-exact-tokens.py)
- Model identity: [`model-manifest.json`](model-manifest.json)
- Runtime identity: [`runtime-manifest.json`](runtime-manifest.json)
- Short realistic suite: [`repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`](../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json)
- Calibrated 4K/17K/31K retrieval ladder: [`long-context-suite-v1.json`](long-context-suite-v1.json)
- Long-context harness: [`scripts/bench-openai-long-context-suite.py`](../../scripts/bench-openai-long-context-suite.py)

The exact-token file is a self-regression oracle for later runtime/kernel/MTP changes; it is not an external proof that Q8_0 reproduces BF16. Do not publish or submit a rate until the model hash, runtime identity, fixed cold suite, native `cache_n=0`, 100 token events/99 intervals, full-offload evidence, clean teardown, and relevant context/quality gate are retained together.

The 128-token fixed suite is the bring-up and regression gate. A promotable
performance packet additionally needs TTFT, request-wall throughput, and the
workspace-standard full 512-token decode measurement. A long-context run with
`CASE_ID` selects a diagnostic subset; only the default run with all three
declared cases is the complete 4K/17K/31K retrieval gate.
