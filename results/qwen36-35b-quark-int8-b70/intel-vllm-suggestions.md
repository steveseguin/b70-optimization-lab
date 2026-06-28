# Intel And vLLM Suggestions

This file collects the actionable feedback from the Qwen3.6 35B lane. The
detailed upstream backlog lives in:

- [`../../suggestions/findings/README.md`](../../suggestions/findings/README.md)
- [`../../suggestions/findings/qwen35-b70-options.md`](../../suggestions/findings/qwen35-b70-options.md)
- [`../../docs/vllm-intel-upstream-candidates.md`](../../docs/vllm-intel-upstream-candidates.md)
- [`../../docs/feedback-for-intel.md`](../../docs/feedback-for-intel.md)

Hardware note for Intel/vLLM readers: these suggestions come from a four-B70
lab with `128 GB` aggregate VRAM. That is enough to expose real XPU graph,
MoE, KV, and driver issues, but it is not enough to test larger families with
much headroom or to keep independent inference service and optimization lanes
running at the same time. Access to higher-VRAM Intel evaluation hardware would
turn several "future model" bullets into runnable repros.

## Highest-Value vLLM/XPU Items

1. Make XPU graph provenance explicit.
   - Graph-none, skipped-capture, and PIECEWISE forced-comm runs must be
     distinguishable in metrics and summaries.
   - Emit capture count, skipped-capture reasons, graph memory, and replay hit
     rate into the run summary.

2. Add graph-safe verifier state hooks for speculative decode.
   - GDN/Mamba/SSM models need rollback and commit operations that are ordered
     with graph replay.
   - Eager `copy_` state restore between captured decode replays is not robust.

3. Improve XPU error diagnostics.
   - Device-lost, OOR, IGC error-code-245, and graph-capture failures need
     concise, actionable logs with the failing shape and kernel path.
   - Current failures often surface as generic engine-core cancellation after a
     worker dies.

4. Continue upstream kernel-package bakeoffs.
   - XPU-native MoE, route GEMM, GDN/DFlash graph padding, B70 attention, KV
     fixes, and graph-safe collectives remain plausible baseline improvements.

5. Treat B70 topology and runtime as first-class benchmark identity.
   - P2P checksums, network interface, oneCCL/OFI settings, driver/runtime
     versions, IGC version, and graph/collective flags need to be captured with
     every claim.

## Intel Runtime Feedback

The repeated problems are not only model-level:

- Level Zero out-of-resources and device-lost failures can appear after
  apparently successful startup and graph capture.
- KV capacity estimates alone are not enough to promote high-concurrency or
  long-context profiles.
- IGC/ocloc failures can be shape-specific and can change the valid operating
  envelope even when smaller prompts pass.
- First-class PyTorch XPU/B70 support should include reliable device
  properties, memory reporting, small tensor movement, OOM recovery, and clear
  loader/driver ABI checks.

## What To Port To Other Models

- Run identity capture first, optimization second.
- Use canaries during every speed experiment; do not defer correctness until
  after a fast number.
- Separate ceilings from valid records in the ledger.
- Prefer upstreamable kernel/runtime deltas over model-specific flag stacks
  when the target model lane is already exhausted.
