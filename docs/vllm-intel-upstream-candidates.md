# vLLM / Intel XPU Upstream Candidates

Date: 2026-06-17

This file collects work from this repo that looks generally useful for vLLM,
vllm-xpu-kernels, Intel XPU/oneCCL/oneAPI, or related integration docs. It
intentionally excludes one-off benchmark wiring and speed hacks that did not
survive quality gates.

This is not a claim that each item is already upstream-ready. The goal is to
identify reusable patches, diagnostics, and design directions that could be
turned into clean PRs or maintainer-actionable issues.

LocalMaxxing result submission credentials and helper usage are documented in
[localmaxxing.md](localmaxxing.md); keep the API key outside Git.

## Highest-Value Candidates

### 1. XPU W8A8 INT8 grouped GEMM and MoE support

What we did:

- Added prototype W8A8 INT8 grouped GEMM support in `vllm-xpu-kernels` for
  Qwen3.6 Quark W8A8 INT8 MoE paths.
- Explored XE2 policies, activation/weight scales, active-offset GEMM variants,
  and oneDNN sidecar execution/parity paths.
- Built live parity checks showing oneDNN sidecar GEMM1/GEMM2/gathered output
  can match the existing XPU path exactly for sampled Qwen3.6 MoE islands.

Why it is generally useful:

- Modern MoE checkpoints increasingly use W8A8/INT8 or FP8-family formats.
- vLLM/XPU needs a first-class fast path for routed MoE decode on Arc Pro B
  series and future Intel GPUs.
- Current endpoint work suggests small Python wrapper boundaries are not enough;
  the useful upstream shape is a lower-level fused or persistent MoE/GEMM
  family with exact parity tests.

Relevant artifacts:

- `patches/vllm-xpu-kernels-qwen36-quark-w8a8-int8-xpu-20260609.patch`
- `patches/vllm-xpu-kernels-w8a8-offset-gemm-prototype-20260612.patch`
- `patches/vllm-xpu-kernels-qwen36-w8a8-policy-override-20260611.patch`
- `patches/vllm-xpu-qwen36-onednn-sidecar-both-gather-parity-20260613.patch`
- `notes/2026-06-13-qwen36-moe-sidecar-readiness.md`

Suggested upstream shape:

- Start with shape-exact microbenchmarks and parity tests.
- Then upstream either a native `vllm-xpu-kernels` W8A8 grouped-GEMM path or a
  oneDNN-backed grouped-GEMM path with cached descriptors/primitives.
- Keep endpoint promotion separate from kernel parity.

### 2. MoE route capture for real-distribution kernel tuning

What we did:

- Added opt-in MoE route capture hooks that record expert histograms, token
  counts, layer names, ranks, and optional top-k IDs.
- Used this to reject simplistic route-skew explanations and to define real
  grouped-GEMM workloads for Qwen3.6 A3B.

Why it is generally useful:

- Synthetic evenly-distributed MoE benchmarks miss the long-tail expert
  distributions that drive real decode performance.
- Intel/vLLM maintainers need route histograms to tune grouped GEMM, persistent
  MoE loops, expert locality, and EP/TP layouts.

Relevant artifacts:

- `patches/vllm-qwen36-moe-route-capture-20260611.patch`
- `patches/vllm-qwen36-moe-route-capture-lower-hooks-20260611.patch`
- `patches/vllm-qwen36-moe-route-capture-stage-token-filters-20260611.patch`
- `scripts/summarize-qwen36-moe-route-capture.py`
- `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`

Suggested upstream shape:

- Add a model-agnostic, default-off MoE route-capture utility.
- Emit compact histograms by default; full IDs only behind an explicit flag.
- Include capture safety around graph/stream capture.

### 3. AOT/custom-op census for vLLM generated graphs

What we did:

- Added a script to scan vLLM/Inductor generated graph code and count custom
  op boundaries such as all-reduce, W8A8 GEMM, per-token quant, MoE, and GDN.
- Used it to prove that several proposed optimizations were no-ops or touched
  the wrong bottleneck.

Why it is generally useful:

- vLLM performance work often guesses which op family dominates. A generated
  graph census gives maintainers a cheap, reproducible operator inventory.
- This is especially useful for XPU where eager, graph, and cache-root behavior
  can differ.

Relevant artifacts:

- `scripts/census-qwen36-aot-ops.py`
- `data/qwen36-quark-int8-tp4-noprefix-current-aot-census-20260611.json`
- `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`

Suggested upstream shape:

- Generalize the census script into a `vllm tools` diagnostic.
- Include per-op counts, representative source windows, inferred boundaries,
  cache root, and compilation config.

### 4. Graph-cache provenance guard and quality sentinels

What we did:

- Added a guard script that checks model identity, graph/AOT cache root, and
  fixed sentinel output tokens before accepting a speed run.
- Found that graph cache provenance can be a quality variable, not only a
  performance variable.

Why it is generally useful:

- For XPU graph paths, a restart or cache-root change can silently move the
  runtime into a different quality branch.
- Upstream examples should not publish speed numbers unless exact-output
  sentinel probes pass.

Relevant artifacts:

- `scripts/check-qwen36-accepted-provenance.py`
- `scripts/probe-fixed-chatml-completion-repeat.py`
- `notes/2026-06-11-qwen36-aot-localmaxxing-and-runtime-screens.md`
- `notes/2026-06-13-qwen36-decode-graph-replay-corruption.md`

Suggested upstream shape:

- Add a small deterministic XPU quality-canary fixture to vLLM examples.
- Record graph cache root, compilation config, model revision, and sentinel
  token prefixes in benchmark artifacts.
- Treat cache-root changes as new runtime modes until they pass sentinels.

### 5. XPU decode graph replay correctness regression

What we did:

- Built a fixed raw ChatML completion repeat probe that exposed replay-only
  corruption in a fast XPU PIECEWISE decode graph lane.
- Demonstrated that bypassing decode replay was clean but slow, proving the
  correctness boundary was graph replay, not detokenization or HTTP serving.
- Added diagnostic toggles for strong output references, step markers, replay
  sync, recapture attempts, and decode-replay bypass.

Why it is generally useful:

- Graph replay bugs are high risk: they can be fast and wrong.
- A model-agnostic repeat fixture can help vLLM/PyTorch/Intel isolate stale
  state, aliasing, dynamic allocation, and grouped-kernel graph issues.

Relevant artifacts:

- `patches/vllm-qwen36-decode-replay-boundary-20260613o.patch`
- `patches/vllm-qwen36-replay-correctness-stack-20260614bd.patch`
- `scripts/probe-fixed-chatml-completion-repeat.py`
- `notes/2026-06-13-qwen36-decode-graph-replay-corruption.md`

Suggested upstream shape:

- File an upstream correctness issue with the clean replay-vs-no-replay
  artifact.
- Upstream the repeat probe as a regression utility.
- Keep the bypass flag diagnostic-only unless a narrower family-specific bypass
  is needed while the backend bug is fixed.

### 6. XPU CPU KV offload and session-cache support

What we did:

- Prototyped an XPU CPU KV offload worker and scheduler changes.
- Validated that pinned host memory and XPU transfers can reload KV at roughly
  `14-16 GB/s` in session-cache tests.
- Clarified the key boundary: CPU KV offload can park/reload prefix sessions,
  but active attention still needs a GPU-resident working KV suffix unless CPU
  paged attention is implemented.

Why it is generally useful:

- vLLM CPU KV offload should support XPU, not only CUDA-like paths.
- Long-context and multi-session local AI workloads need clear semantics:
  session parking is different from active-context overflow.

Relevant artifacts:

- `experiments/minimax_xpu_kv_offload/patches/xpu-cpu-kv-worker-prototype-20260525.patch`
- `experiments/minimax_xpu_kv_offload/patches/kv-offload-admission-check-xpu-experiment-20260524.patch`
- `experiments/minimax_xpu_kv_offload/README.md`
- `experiments/minimax_xpu_kv_offload/notes-20260525-session-cache-operations.md`
- `docs/current-reproducibility-map.md`

Suggested upstream shape:

- Add official XPU CPU KV offload support with tests for prefix reload,
  metadata copy, scheduler fencing, and failure recovery.
- Document pinned memory API choice: PyTorch XPU, SYCL USM, or Level Zero.
- Add admission checks that distinguish GPU KV allocation from host KV budget.

### 7. TurboQuant XPU workspace handling

What we did:

- Found TurboQuant XPU locked-workspace failures during decode and continuation
  prefill.
- Added a fallback that allocates temporary buffers when the shared workspace
  is locked.
- Validated startup and quality canaries for some long-context TurboQuant modes,
  while recording that sustained decode remained much slower than the normal KV
  lane.

Why it is generally useful:

- The current failure mode is confusing and surfaces as a server error.
- Workspace sizing should be explicit before capture/lock, especially on XPU.

Relevant artifacts:

- `patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`
- `scripts/repro-minimax-turboquant-xpu-workspace-bug.sh`
- `experiments/minimax_xpu_kv_offload/notes-20260525-c2-quality-and-turboquant.md`
- `experiments/minimax_xpu_kv_offload/notes-20260525-turboquant-active-context-boundary.md`

Suggested upstream shape:

- Prefer pre-sizing/growing the workspace before it is locked.
- If fallback allocation remains necessary, log it as a degraded path.
- Add XPU TurboQuant examples with supported context, speed, and quality
  caveats.

### 8. Modular low-memory builds for vllm-xpu-kernels

What we did:

- Added and validated a `_C`-only build loop for `vllm-xpu-kernels`.
- Avoided recompiling huge unrelated targets like `paged_decode_xe2.cpp` when
  iterating on basic kernels.

Why it is generally useful:

- Full `vllm-xpu-kernels` builds can exceed 120 GB RSS on one compile unit.
- Faster partial builds would make upstream development and CI less fragile.

Relevant artifacts:

- `notes/2026-06-10-vllm-xpu-kernels-c-only-build.md`
- `scripts/build-vllm-xpu-kernels-c-only.sh`
- `scripts/build-vllm-xpu-kernels-xpu-c-only.sh`
- `docs/intel-b70-minimax-feedback-20260523.md`

Suggested upstream shape:

- Add official CMake/build targets for `_C`, `_xpu_C`, FA2, MoE, GDN, and
  allocator components.
- Document expected peak memory by target.
- Provide ABI-matched wheels for tested PyTorch XPU releases so most users do
  not need source builds.

### 9. Compressed-tensors scalar-scale handling for XPU FA2

What we did:

- Fixed singleton KV scale tensors by reshaping them to scalar views before
  passing them into XPU FA2 paths.

Why it is generally useful:

- This is a small compatibility fix for compressed-tensors KV cache support on
  XPU.
- It should be easier to upstream than the larger kernel experiments.

Relevant artifact:

- `patches/vllm-xpu-fa2-compressed-tensors-scalar-scales.patch`

Suggested upstream shape:

- Add the scalar-view conversion and a unit/regression test with singleton
  scale tensors on XPU attention backends.

### 10. XPU block-FP8 fallback and requantization experiments

What we did:

- Built fallback paths for block-FP8 Qwen-class checkpoints on XPU:
  dequantize block-FP8 to BF16, and optionally requantize to per-channel FP8
  for Intel FP8 GEMM.
- Confirmed the path is runnable but not performance-competitive enough yet.

Why it is generally useful:

- vLLM/XPU needs a native 128x128 block-FP8 W8A8 path for current FP8
  checkpoints.
- Fallbacks are useful for correctness and coverage while native kernels are
  developed.

Relevant artifacts:

- `patches/vllm-c51df4300-xpu-qwen36-block-fp8-fallbacks.patch`
- `patches/vllm-xpu-block-fp8-requant-env-20260506.patch`
- `results/fp8-vllm-xpu-qwen36-2026-05-04.md`

Suggested upstream shape:

- Add a conservative BF16 fallback for unsupported block-FP8 XPU formats.
- Track native block-FP8 support separately as a performance project.
- Make requantization opt-in and clearly mark quality implications.

### 11. Graph-safe communication and oneCCL diagnostics

What we did:

- Tested forcing XPU graph capture with communication ops and oneCCL settings.
- Found that some oneCCL scheduler/worker modes are incompatible with graph
  recording, while the accepted fast paths depend on graph-safe collectives.
- Built multiple all-reduce and callsite timing probes.

Why it is generally useful:

- Multi-GPU XPU decode is dominated by small repeated collectives for some
  models.
- vLLM should not simply disable graph capture whenever communication exists;
  it should know which collective paths are graph-safe.

Relevant artifacts:

- `patches/vllm-xpu-force-graph-with-comm-experiment.patch`
- `patches/vllm-xpu-allreduce-callsite-timing-20260510.patch`
- `patches/vllm-xpu-allreduce-boundary-probes-20260516.patch`
- `benchmarks/b70_xccl_minimax_allreduce_shapes.py`
- `benchmarks/b70_xccl_decode_size_allreduce_bench.py`
- `notes/2026-05-19-minimax-site-labeled-allreduce-timing.md`

Suggested upstream shape:

- Add feature detection for graph-safe oneCCL/SYCL collective modes.
- Improve diagnostics when a collective blocks graph capture.
- Provide small-message all-reduce benchmarks aligned with hidden-size decode
  shapes, not only bulk bandwidth tests.

### 12. XPU GDN / Mamba state tracing for speculative decoding

What we did:

- Added detailed GDN state tracing for Qwen3.6 speculation and replay
  debugging.
- Isolated that packed speculative verifier rows can diverge from ordinary
  decode rows because recurrent/GDN state transactions are not equivalent.
- Developed an EAGLE path plan that requires fixing verifier parity first.

Why it is generally useful:

- GDN/Mamba-style stateful layers make speculation harder than ordinary
  Transformer-only decode.
- vLLM should have trace tools for state transactions, accepted-state updates,
  and first-divergence analysis.

Relevant artifacts:

- `patches/vllm-qwen36-replay-correctness-stack-20260614bd.patch`
- `patches/vllm-qwen36-spec-state-trace-20260611.patch`
- `patches/vllm-qwen36-spec-recovery-diagnostics-20260616.patch`
- `notes/2026-06-17-eagle-path-to-150-tok-s-plan.md`

Suggested upstream shape:

- Add default-off state tracing for recurrent attention/speculative decode.
- Add oracle-draft tests where the proposer is perfect, so verifier state
  bugs are isolated from draft quality.
- Treat speculation promotion as exact-token parity work, not only acceptance
  rate work.

### 13. Runtime/device-lost diagnostics around XPU metadata copies

What we did:

- Hit Level Zero `UR_RESULT_ERROR_DEVICE_LOST` in scheduler/model-runner
  metadata transfer paths such as block-table and computed-token copies.
- Added trace and guard scripts to preserve failure artifacts instead of losing
  everything to a server-side 500 or dead worker.

Why it is generally useful:

- Device-lost errors need device id, queue, copy size, request context, and
  recent operation history.
- These failures affect production reliability as much as kernel throughput.

Relevant artifacts:

- `patches/vllm-qwen36-xpu-gdn-prefill-where-device-lost-20260614f.patch`
- `patches/vllm-qwen36-active-gpu-model-runner-input-trace-20260611.patch`
- `scripts/check-qwen36-accepted-provenance.py`
- `docs/intel-b70-minimax-feedback-20260523.md`

Suggested upstream shape:

- Add structured failure artifacts for XPU worker crashes.
- Include request metadata, tensor/copy sizes, device/rank, and log tails.
- Add a small XPU post-crash health/copy probe for operators.

## Good Operational / Documentation Candidates

These are not mostly code patches, but they would materially improve the
vLLM/Intel user path.

1. Publish a B70 vLLM compatibility matrix:
   PyTorch XPU, oneAPI compiler, Intel compute runtime, oneCCL, vLLM,
   `vllm-xpu-kernels`, and known-good model recipes.
2. Publish ABI-matched `vllm-xpu-kernels` wheels for supported PyTorch XPU
   releases.
3. Provide an `intel-ai doctor` or `vllm xpu doctor` command that checks GPU
   visibility, Level Zero, PyTorch XPU, oneCCL, native extension ABI, cache
   permissions, compiler version, topology, and expected RAM/swap.
4. Make oneAPI compiler selection explicit. Avoid global `setvars.sh` drift
   when a narrower compiler env such as `compiler/2025.3/env/vars.sh` is
   required.
5. Register extension-owned `VLLM_*` environment variables so useful XPU flags
   do not appear as unknown mistakes in logs.

Relevant docs:

- `docs/feedback-for-intel.md`
- `docs/intel-b70-minimax-feedback-20260523.md`
- `repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`

## Do Not Upstream Yet

These were useful lab experiments but should not be presented as general
upstream wins without more work.

- MiniMax Q/K/RMS helper variants that were neutral or quality-sensitive.
- Local argmax, greedy-skip, or logits-shortcut paths that risk quality drift.
- Python-level MoE shared-add/all-reduce wrappers that passed quality but did
  not remove enough real work to speed up the endpoint.
- Full-decode graph mode for the Qwen3.6/XPU lane; it currently hits SYCL
  graph feature gaps.
- Current n-gram/MTP speculative paths; they either do not improve diverse
  prompts or fail verifier parity.
- oneDNN sidecar replacement as an endpoint speed path; parity work is useful,
  but eager endpoint quality is not yet a promotion oracle.
- TurboQuant as a production recommendation; it is useful for capacity
  research, but sustained decode is currently too slow for the main lane.

## Suggested PR / Issue Split

1. Small PR: compressed-tensors singleton scale fix for XPU FA2.
2. Small PR: `vllm-xpu-kernels` modular build targets or documented `_C`-only
   build mode.
3. Diagnostic PR: MoE route capture, default-off.
4. Diagnostic PR: AOT/custom-op census tool.
5. Correctness issue: XPU decode graph replay corruption with fixed-repeat
   reproducer.
6. Feature issue: official XPU CPU KV offload semantics and implementation.
7. Feature issue: TurboQuant XPU workspace pre-sizing.
8. Kernel project: W8A8 INT8 grouped GEMM / MoE path for Qwen3.6-class routed
   decode.
9. Kernel project: native block-FP8 W8A8 support for XPU.
10. Reliability issue: structured Level Zero device-lost diagnostics for vLLM
    worker metadata/copy paths.
