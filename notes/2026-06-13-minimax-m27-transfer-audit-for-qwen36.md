# MiniMax M2.7 Transfer Audit For Qwen3.6

Date: 2026-06-13

Scope:

- Review successful MiniMax M2.7 optimization actions and compare them against
  the current Qwen3.6 35B-A3B Quark W8A8 INT8 lane.
- Transfer only the engineering pattern when the MiniMax win depended on a
  different quantization format. This audit does not propose 4-bit, AWQ,
  Qwen3.5, expert dropping, or any quality-changing shortcut for Qwen.

## MiniMax Actions Already Applied Or Tried On Qwen

1. **PIECEWISE XPU graph capture and no-prefix serving posture.**
   MiniMax first got large accepted gains when graph capture, no-prefix serving,
   and a warm direct-loaded cache root were treated as a single recipe instead
   of independent flags. The current Qwen accepted launcher already uses a
   PIECEWISE graph/no-prefix posture with communicator capture guardrails.

2. **Clone-safe custom collectives.**
   MiniMax promoted clone-safe custom allreduce before testing more aggressive
   tiny-collective mutations. The current Qwen accepted launcher already
   enables XPU custom-op collectives with clone-input guardrails.

3. **Block-size 256 and MBT512 as direct flag ports.**
   MiniMax benefited from `--block-size 256` and `--max-num-batched-tokens 512`
   in its later recipe. Qwen tested both as direct ports and rejected them for
   the current 32K/no-prefix W8A8 endpoint. Do not retry these blindly.

4. **Cache provenance and canary checks.**
   MiniMax exposed a stale-cache trap: one fast cache root produced invalid
   output, while a fresh root passed strict quality and then held steady. Qwen
   already has accepted-provenance checks, but the MiniMax lesson should be
   formalized as a repeatable promotion protocol.

5. **Public benchmark recording.**
   MiniMax wins were useful once exact commands, cache roots, quality gates, and
   Localmaxxing rows were recorded. Qwen now has an exact-model B70 row around
   `99-100 tok/s`; future rows should only be posted for accepted-quality
   endpoints, not diagnostic probes.

6. **oneCCL P2P posture.**
   MiniMax converged back to `CCL_TOPO_P2P_ACCESS=1` with default
   `CCL_ZE_IPC_EXCHANGE` for vLLM runs, while using explicit `pidfd` mostly for
   standalone diagnostics. The current Qwen accepted launcher already keeps P2P
   enabled and leaves `CCL_ZE_IPC_EXCHANGE` unset.

7. **Fast storage/cache roots.**
   MiniMax benefited operationally from moving models and cache roots onto the
   fast NVMe mount. Qwen already uses `/mnt/fast-ai` for the model/cache path.

## Successful MiniMax Patterns Not Fully Tried Here

1. **Site-labeled collective timing before kernel work.**
   MiniMax call-site timing separated vocab, attention-output, MoE-output, and
   Q/K RMS variance collectives. That made the later small collective wins
   targeted instead of speculative. Qwen has forward-boundary timing, but not a
   full site-labeled collective census across all ranks. This is the next
   highest-signal Qwen probe.

2. **MoE output collective folded into the custom-op boundary.**
   MiniMax got a clean win by moving the MoE output allreduce path closer to
   the custom MoE operation. Qwen has tested exact offset/active-offset W8A8
   replay, but not a W8A8 layerlet that also absorbs or immediately schedules
   the output collective. Add this to the persistent one-dispatch MoE work.

3. **Tiny-collective policy based on actual tensor shapes.**
   MiniMax's Q/K variance allreduce had tiny FP32 tensors where clone elision
   and then an alias-correct in-place custom op produced quality-passing speed
   wins. Qwen should not assume the same shape exists, but the action is
   transferable: log collective call sites, sizes, dtypes, and aliasing, then
   apply a tiny-collective policy only to proven hot sites.

4. **Work-sharing/persistent MoE dispatch as an architecture pattern.**
   MiniMax's strongest MoE wins came when the MoE path reduced per-layer
   dispatch overhead and kept the recipe aligned with graph capture and
   scheduler settings. The exact INT4 kernel is not transferable to Qwen, but
   the architecture is: a resident W8A8 top-k decode layerlet with descriptors,
   scratch, scales, expert pointers, route command, and collective boundary
   managed as one unit.

5. **Warm-cache promotion with repeat/stdev gates.**
   MiniMax did not promote first-run numbers. It discarded warmups, ran multiple
   repeats, rejected stale cache roots, and treated sub-`~1 tok/s` deltas as
   noise unless adjacent control/candidate pairs repeated. Qwen should promote
   future speedups with the same paired A/B discipline.

6. **Structured fast lane kept separate from general chat.**
   MiniMax's regex-constrained simple-HTML lane reached the highest public
   tok/s, but it was a task-specific structured-output lane, not an unconstrained
   chat result. For Qwen, this can become a production lane for strict tool or
   HTML schemas only if quality is defined as exact schema-constrained output.
   It is not a general `>200 tok/s` chat-decode claim.

7. **Display and driver isolation audit.**
   MiniMax's 32K serving work recorded the display moved off the Arc cards and
   `xe.disable_display=1`. Qwen should record the same host/display state in
   production benchmarks so graphics/display interference is not an unknown.

8. **Attention/KV placement audit.**
   Early MiniMax GGUF runs gained by fixing K/Q/V offload after device-map
   issues made earlier tests misleading. Qwen vLLM should already place model
   work on XPU, but the layer-family timing should still include attention/KV
   placement and any CPU staging indicators so we do not miss a hidden fallback.

9. **Shape-driven row packing or microtile sweeps.**
   MiniMax GGUF improved through `MMV_Y=2`, `-ub 64`, and fused RMSNorm only
   after actual hot shapes were known. The direct knobs do not apply to Qwen
   vLLM, but the method does: if the W8A8 layer-family probe shows small-N GEMM
   or row-vector kernels dominating, run a microtile/row-packing sweep against
   the exact Qwen shapes instead of changing generic launch flags.

## Actionable Qwen Additions

1. Add all-rank, site-labeled collective timing to the existing layer-family
   timing plan. Required fields: call-site label, layer, rank, dtype, element
   count, bytes, stream, wait time, algorithm if visible, and rank/card map.

2. Extend the persistent W8A8 MoE layerlet plan so it explicitly tests whether
   the combine/output collective can be folded into or adjacent to the layerlet,
   rather than leaving a separate host-visible TP boundary.

3. Add a tiny-collective decision table after the collective census:
   clone-safe baseline, no-clone only if alias-safe, alias-correct in-place op,
   and exact token/canary gate for each candidate site.

4. Use MiniMax-style promotion gates for any future Qwen result:
   fresh cache root, direct-loaded warm cache repeat, two discarded warmups,
   at least four measured repeats, adjacent control/candidate A/B, token-ID
   parity/canaries, raw metrics, command snippet, and cache root hashes.

5. Keep a separate structured-output fast-lane backlog item for production
   workflows. Never mix those results with free-form chat decode benchmarks.

6. Record host/display isolation in the next Localmaxxing-worthy Qwen run:
   driver, kernel, firmware, XPU stack, display attachment, power state, and
   whether any Arc card is serving display output.

7. Add attention/KV placement checks to the layer-family timing artifact:
   verify no CPU staging or unplanned host transfers occur around attention,
   KV reads/writes, GDN, router, logits, or collective boundaries.

8. If the timing artifact points at small-N W8A8 kernels rather than
   collectives/dispatch, add a Qwen-specific row-packing or microtile sweep
   using the measured shapes. Do not reuse MiniMax GGUF flags directly.

## Non-Transferable Or Lower Priority

- MiniMax's INT4/AutoRound/llm-scaler u4 kernels are not acceptable Qwen
  substitutions. The transferable part is the dispatch structure, not the
  quantization.
- MiniMax Q/K RMS helpers are architecture-specific. They become relevant to
  Qwen only if Qwen's collective census shows similar tiny hot collectives.
- MiniMax GGUF flags such as `GGML_SYCL_MMV_Y_RUNTIME`, `-ub`, fused RMSNorm,
  K/Q/V offload, and DNN toggles do not map directly onto the vLLM/XPU Qwen
  endpoint. Treat them as evidence for shape/placement audits only.
- Direct flag ports already rejected on Qwen, such as `block-size 256` and
  `MBT512`, should stay rejected unless a later layer/collective profile gives
  a specific reason to re-bracket the scheduler envelope.
