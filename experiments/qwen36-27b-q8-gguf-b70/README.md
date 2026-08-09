# Qwen3.6 27B Q8_0 GGUF on one B70

Status: one-B70 target-only baseline validated through 32K, and the simultaneous
four-replica 4K functional topology passes. The next service target is two F16-
KV 32K slots per card. No localmaxxing performance result is promoted from this
lane yet.

The durable goal, integrity boundary, adaptive research loop, four-GPU model,
and recurring subagent roles are in [`STRATEGY.md`](STRATEGY.md). Dated plans
are replaceable tactical proposals beneath that strategy.

## Scope

This lane has one primary identity:

- target-only `Qwen3.6-27B-Q8_0.gguf`;
- text-only, with no multimodal projector;
- one Intel Arc Pro B70 with 32 GiB VRAM;
- validated reference context of 32,768 tokens with F16 KV;
- primary next target of two F16-KV 32K slots per card, validation pending;
- optional later stretch capacity of 100K to 128K with Q8 KV;
- no MTP, DFlash, n-gram, prompt-cache, or response-cache acceleration.

MTP and vision are optional follow-ups. They must not be mixed into the target-
only baseline identity or result packet.

The selected deployment direction is four independent one-GPU processes. The
primary candidate is two slots per process, for up to eight cluster-wide
requests. This is a separate capacity/throughput identity that still needs to
pass: in llama.cpp, `-c` is the total budget across all `-np` slots, so two 32K
slots require `-c 65536 -np 2`.

`UD-Q8_K_XL` is excluded from the one-card lane because its file is already
larger than one B70 before KV cache and runtime buffers. `Q8_0` is the intended
Q8 fit candidate.

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

## Validated fit

The GGUF file is 26.63 GiB. With a 32,768-token F16 KV allocation, the server
fully offloaded `65/65` layers and XPU-SMI reported `28,372 MiB` loaded on one
B70. The retained buffers include a `25,972.29 MiB` model buffer, `2,048 MiB`
KV buffer, `149.62 MiB` recurrent-state buffer, and `38.50 MiB` device compute
buffer.

Qwen3.6 27B has 64 layers with conventional attention every fourth layer. With
16 conventional-attention layers, four KV heads, head dimension 256, and F16
K/V, the conventional KV allocation is 64 KiB per token, matching the retained
2 GiB allocation at 32K. The F16 lane therefore fits with roughly 4.3 GiB of
reported device-memory headroom; Q8 KV is not needed for the validated 32K
reference or the primary c2/32K target. It would be required only for the
optional 100K-or-more stretch target on one 32 GiB card.

Measured-memory modeling predicts F16 c1/64K and c2/32K can fit. The c2/32K
shape is now the next target. Q8_0 KV is predicted to permit c1/100K and
probably c1/128K; those are optional capacity rows, not immediate work. These
are not fit results. The exact estimates, slot semantics, stop conditions, and
validation order are in
[`notes/2026-08-08-context-concurrency-mtp-vision-plan.md`](notes/2026-08-08-context-concurrency-mtp-vision-plan.md).

Validated results under the correctness-qualified default
`GGML_SYCL_ENABLE_DNN=0`, `GGML_SYCL_ENABLE_OPT=1`:

- fixed cold 12-prompt, 128-token suite: `15.550257 tok/s` median tokens 1--100,
  p10 `15.548172`, mean `15.550044`; 12/12 stream/replay exactness checks
  passed, all native cache-reuse counts were zero;
- one UTF-8 byte-fallback token at generated index 89 was intentionally absent
  from SSE; the complete replay uniquely aligned it and retained valid token-1
  and token-100 timing endpoints;
- calibrated 4,369 / 17,274 / 31,846 prompt-token retrieval rows all passed
  exact JSON fields with zero cached tokens;
- 32K prefill median `156.043 tok/s`; decode-after-TTFT median `14.025 tok/s`,
  ranging from `15.240` at 4K to `12.783` at 31.8K;
- both correctness-qualified validation runs exited cleanly, returned GPU 0 from 28,372 or
  26,573 MiB to 43 MiB, and retained empty device/server fault scans.

The validation sequence remains useful for future runtimes:

1. 4K target-only compatibility smoke with a 4K F16-KV allocation and full GPU
   offload.
2. Fixed cold realistic suite through llama.cpp's native streaming endpoint to
   establish the Q8_0 exact-token regression oracle and conventional 100-event/
   99-interval baseline speed.
3. A separately labeled 32K F16-KV allocation and calibrated long-context
   retrieval gate.
4. A full-512 c1 packet, then simultaneous F16-KV c2/32K fit, exactness,
   retrieval, turnover, aggregate-rate, latency, and fairness gates.
5. Q8_0 KV only for an optional larger-context target. Treat Q8 KV as a
   separate quality identity and compare it against the F16-KV corpus.
6. Optional MTP only if ordinary c2 does not meet the serving objective. Use an
   integrated publisher artifact, or a same-publisher and same-revision target/
   MTP pair; do not cross-pair converters without tensor and metadata
   validation, and do not graft the third-party head-only extraction into the
   baseline.
7. Optional vision only after the text optimization and context envelope are
   settled. Use the same-repository, same-revision F16 projector pinned in
   [`optional-artifacts-manifest.json`](optional-artifacts-manifest.json).

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

The archived build's DNN selector is not correctness-safe for this Q8 target.
With DNN enabled, the fast path stayed near `15.55 tok/s` but four of twelve
temperature-zero replay rows diverged; an immediate A/A repeat also diverged.
Disabling the broader optimization stack restored exactness but fell to
`5.033 tok/s`. Disabling only DNN restored exactness at `15.551 tok/s` in the
focused A/A test and `15.550 tok/s` across the full suite. The DNN-off 32K
confirmation paid about 2.8% in median prefill versus the DNN-on diagnostic,
with no meaningful decode change. Keep DNN-off as the lane default.

## Four-GPU use

Four one-card processes will be used for independent functional or optimization
lanes, each with its own source worktree, build, port, GPU ordinal, and run
directory. Parallel runs are screening or aggregate-service evidence. Official
single-card throughput comparisons remain isolated, same-card bracketed, and
confirmed on a second card. The working protocol is in
[`notes/2026-08-08-four-gpu-optimization-and-c2-plan.md`](notes/2026-08-08-four-gpu-optimization-and-c2-plan.md).

The simultaneous four-replica functional smoke passed: all four services were
resident at 4K with `26,573 MiB` on each card, fully offloaded, and generated
the same sealed 128-token output concurrently before clean teardown to 43 MiB.
This proves the process topology, not a four-card performance score. See
[`notes/2026-08-08-four-replica-functional-smoke.md`](notes/2026-08-08-four-replica-functional-smoke.md).

## Entry points

- Target-only server: [`scripts/serve-target-only.sh`](scripts/serve-target-only.sh)
- Validation runner: [`scripts/run-validation.sh`](scripts/run-validation.sh)
- Four-replica functional smoke: [`scripts/run-four-replica-smoke.sh`](scripts/run-four-replica-smoke.sh)
- Exact emitted-token capture/comparison and 99-interval primary metric: [`scripts/capture-exact-tokens.py`](scripts/capture-exact-tokens.py)
- Model identity: [`model-manifest.json`](model-manifest.json)
- Runtime identity: [`runtime-manifest.json`](runtime-manifest.json)
- Optional future artifact identities: [`optional-artifacts-manifest.json`](optional-artifacts-manifest.json)
- Short realistic suite: [`repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`](../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json)
- Calibrated 4K/17K/31K retrieval ladder: [`long-context-suite-v1.json`](long-context-suite-v1.json)
- Long-context harness: [`scripts/bench-openai-long-context-suite.py`](../../scripts/bench-openai-long-context-suite.py)
- Result summary: [`data/baseline-summary-20260808.json`](data/baseline-summary-20260808.json)
- Chronological result note: [`notes/2026-08-08-one-b70-baseline-and-dnn-exactness.md`](notes/2026-08-08-one-b70-baseline-and-dnn-exactness.md)
- Four-replica result: [`notes/2026-08-08-four-replica-functional-smoke.md`](notes/2026-08-08-four-replica-functional-smoke.md)
- Context/concurrency and optional-feature plan: [`notes/2026-08-08-context-concurrency-mtp-vision-plan.md`](notes/2026-08-08-context-concurrency-mtp-vision-plan.md)
- Four-GPU optimization and c2 execution plan: [`notes/2026-08-08-four-gpu-optimization-and-c2-plan.md`](notes/2026-08-08-four-gpu-optimization-and-c2-plan.md)
- Durable adaptive optimization strategy: [`STRATEGY.md`](STRATEGY.md)
- Sourced living idea queue: [`../../suggestions/qwen36-27b-q8-gguf/README.md`](../../suggestions/qwen36-27b-q8-gguf/README.md)

The exact-token file is a self-regression oracle for later runtime/kernel/MTP
changes; it is not an external proof that Q8_0 reproduces BF16. Do not publish
or submit a rate until the model hash, runtime identity, fixed cold suite,
native `cache_n=0`, 100 token events/99 intervals, full-offload evidence, clean
teardown, and relevant context/quality gate are retained together.

The 128-token fixed suite is the bring-up and regression gate. A promotable
performance packet additionally needs TTFT, request-wall throughput, and the
workspace-standard full 512-token decode measurement. A long-context run with
`CASE_ID` selects a diagnostic subset; only the default run with all three
declared cases is the complete 4K/17K/31K retrieval gate.
