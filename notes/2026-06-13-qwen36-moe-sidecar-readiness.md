# Qwen3.6 MoE Sidecar Readiness

## Current Decision

The all-rank layer-family timing points at the W8A8 MoE path, not collectives,
as the next best no-quality-loss optimization target for c1 decode. The next
engineering path stays on a resident/persistent MoE layerlet until replay data
contradicts it.

## Existing Replay Evidence

- File-backed oneDNN layer-9/rank-0 MoE island:
  `data/qwen36-onednn-moe-island-layer9-r1-20260612ay/onednn_moe_island_result.json`.
  GEMM1 mean `34.462620 us`, GEMM2 mean `24.756200 us`.
  `gemm1_vs_xpu_max_abs_diff`, `gemm2_vs_xpu_max_abs_diff`, and
  `onednn_island_vs_xpu_fused_moe_max_abs_diff` were all `0.0`.
- Resident two-GEMM pair:
  `data/qwen36-onednn-moe-island-layer9-r1-resident-pair-rerun-20260612az.json`.
  Pair mean `54.340054 us`, p50 `49.954 us`, min `28.714 us`, with exact raw
  checksums for both GEMM outputs.
- Multi-window oneDNN island:
  `data/qwen36-onednn-moe-island-layer9-r1-multiwindow-20260612bc/multi_window_onednn_moe_island_result.json`.
  `16/16` windows were exact. Aggregate max abs diffs were all `0.0`.
  Mean GEMM1 across windows was `53.810433 us`; mean GEMM2 was `33.440583 us`.
- Offset/active-offset layer-floor replay:
  `data/qwen36-replay-digest-moe-layerfloor-offsetactive-20260613f.json` and
  `data/qwen36-moe-fusion-target-budget-offsetactive-20260613h.md`.
  Current exact `xpu_fused_moe` was `315.291681 us/layer`.
  Exact fused-prologue offset-GEMM was `209.052431 us/layer`.
  Exact fused-prologue active-offset-GEMM was `211.169644 us/layer`.
  The candidate target for >200 tok/s is `189.100588 us/layer`, so the
  current exact lower-bound candidates are useful but not endpoint-ready.

## Rank Skew Check

`data/qwen36-rank-route-forward-overlay-20260613n.json` rejects the simple
route-skew explanation. Route counters were identical across ranks for all 40
layers, while forward-end wait still varied:

| rank | mean forward-end wait ms |
|---:|---:|
| 0 | 4.214303 |
| 1 | 4.470655 |
| 2 | 4.769202 |
| 3 | 4.820472 |

This keeps the focus on implementation overhead, dispatch boundaries, and
possibly rank/device execution variance rather than rank-specific route
distribution.

## Source Readiness Change

Patch artifact:
`patches/vllm-xpu-qwen36-onednn-sidecar-end-offsets-20260613.patch`.

The Python sidecar helper `_make_onednn_grouped_offsets` in
`/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/fused_moe_interface.py`
now returns cumulative end offsets, matching the exact oneDNN grouped-memory
runner. Smoke result:
`data/qwen36-onednn-sidecar-offset-helper-smoke-20260613.json`.

This is sidecar-readiness only. The accepted endpoint is unaffected unless the
opt-in oneDNN sidecar probe/execution path is enabled.

## One-GEMM Execute Prototype

Patch artifact:
`patches/vllm-xpu-qwen36-onednn-sidecar-execute-onegemm-20260613.patch`.

This extends the existing sidecar probe with an opt-in
`VLLM_XPU_MOE_ONEDNN_SIDECAR_EXECUTE` mode:

- `0`, `false`, `off`, `dry`: descriptor/USM-wrap probe only.
- `gemm1` or `1`: execute oneDNN grouped GEMM1 into `gemm1_output`.
- `gemm2` or `2`: execute oneDNN grouped GEMM2 into `gemm2_output`.

The default remains no execution. The probe still requires the existing
sidecar env gate, max-call gate, rank/layer filters, and no active stream
capture.

Validation artifact:
`data/qwen36-onednn-sidecar-execute-build-smoke-20260613.json`.

- Targeted C++ build succeeded in
  `/home/steve/src/vllm-xpu-kernels/build/qwen36-sidecar-probe-20260612`.
- The built extension registered the new schema with `int execute_mode`.
- A direct synthetic XPU smoke through standalone `importlib` was blocked by
  oneDNN engine creation: `RuntimeError: could not create an engine` with
  `bad engine kind`. This is the same shared oneDNN engine path used by the
  vLLM process, so the next runtime test should run inside the normal vLLM
  endpoint context, not via standalone import.

## Next Tasks

1. Run the one-GEMM execute prototype inside a normal vLLM process context with
   `VLLM_XPU_MOE_ONEDNN_SIDECAR_EXECUTE=gemm1`, max calls `1`, rank `0`, and a
   single layer filter such as `layers.9`.
2. Add a sidecar log checksum/parity field for the overwritten scratch output,
   then compare the oneDNN result against the pre-execute XPU scratch result.
3. Repeat for GEMM2.
4. Extend to resident two-GEMM execution with cached descriptors/primitives.
5. Add activation/quant2 and gather/combine parity until the full island
   returns `max_abs_diff=0.0` versus `xpu_fused_moe`.
6. Only then run endpoint A/B. Promotion requires exact canary token IDs,
   four measured repeats after warmup, peak VRAM/power/thermal provenance, and
   the accepted quality gates.

## Success Gate

The non-speculative layerlet needs to beat roughly `189 us/layer`, ideally with
one resident/fused dispatch boundary. If a replay-exact layerlet cannot beat
that budget, shift the next >200 tok/s effort toward exact target-verified
speculation parity.
