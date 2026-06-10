# Qwen3.6 GDN rms_norm_gated Custom Op Rejection

Date: 2026-06-10

## Goal

Test whether enabling the FLA `rms_norm_gated` custom op helps the Qwen3.6
GatedDeltaNet post-core path.

Graph inspection of the accepted GDN clone/no-prefix runtime showed the GDN
post-core gated RMSNorm decomposed into FP32 elementwise ops before the output
projection. The candidate kept the accepted model, quantization, context length,
GDN quant-reuse clone mode, and PIECEWISE graph settings, but changed custom
ops from `["none"]` to `["none", "+rms_norm_gated"]`.

## Candidate Runtime

- model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`
- snapshot: `/mnt/fast-ai/llm-cache/hf/models--nameistoken--Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/cced56592e8c8935f8220836b4baa04dfd389118`
- served name: `qwen36-35b-a3b-fp8`
- TP: `4`
- max model length: `32768`
- quantization: `quark`
- dtype: `auto` / runtime BF16
- prefix caching: disabled
- graph mode: `PIECEWISE`
- GDN quant-reuse mode: `VLLM_XPU_GDN_REUSE_QKVZ_BA_QUANT=clone`
- custom ops: `["none", "+rms_norm_gated"]`

## Attempts

### Attempt 1: direct enable

- session: `qwen36-tp4-gdn-rmsgated-32k`
- cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-rmsgated-32k-noprefix`
- log: `/tmp/qwen36-quark-int8-tp4-gdn-rmsgated-32k-noprefix-20260610.log`
- model load memory before failure: `8.58 GiB`

Result: startup failed during profile/compile.

Root cause:

- `torch._dynamo.exc.Unsupported: Attempted to inline function marked as skipped`
- path: `gdn_linear_attn.py` -> `RMSNormGated.forward_xpu` -> FLA
  `rmsnorm_fn`
- failing call: `torch.accelerator.device_index(tensor.device.index)` inside
  FLA `input_guard`

This confirmed that `+rms_norm_gated` did route into the intended FLA kernel,
but the FLA guard is not fullgraph-safe as-is on XPU.

### Attempt 2: skip redundant XPU device guard

Temporary local probe:

- skip `torch.accelerator.device_index(...)` when the selected tensor is already
  on `xpu`

- session: `qwen36-tp4-gdn-rmsgated-xpunoguard-32k`
- cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-rmsgated-xpunoguard-32k-noprefix`
- log: `/tmp/qwen36-quark-int8-tp4-gdn-rmsgated-xpunoguard-32k-noprefix-20260610.log`
- model load memory before failure: `8.58 GiB`

Result: startup failed during profile/compile.

Root cause:

- Dynamo could not construct a `ConstantVariable` for
  `torch._C._XpuDeviceProperties`
- source path: FLA `calc_rows_per_block()` -> `num_compute_units()` ->
  `torch.xpu.get_device_properties(device_id).max_compute_units`

This moved past the first blocker, but the kernel launch-shape helper still
queries XPU properties inside the compiled graph path.

### Attempt 3: cache XPU compute-unit count outside graph

Temporary local probe:

- cache XPU `max_compute_units` at module import
- for XPU, use the cached value in `calc_rows_per_block()`
- observed hardware value: `256` compute units per B70

- session: `qwen36-tp4-gdn-rmsgated-xpucachecu-32k`
- cache root: `/mnt/fast-ai/vllm-cache-exp/qwen36-35b-a3b-quark-int8-tp4-piecewise-graph-gdn-rmsgated-xpucachecu-32k-noprefix`
- log: `/tmp/qwen36-quark-int8-tp4-gdn-rmsgated-xpucachecu-32k-noprefix-20260610.log`
- model load memory before failure: `8.58 GiB`
- model loading: `14.106386 s`

Result: startup still failed during profile/compile.

Root cause:

- PyTorch/Triton first warned that mutated tensor identification failed for
  `layer_norm_fwd_kernel` with `IndexError('Function argument index out of range')`
- Intel Triton lowering then failed:
  `PassManager::run failed`
- lowering assertion:
  `TruncFOpConversion::createDestOps ... Assertion inElemTy.isF32() && "unsupported conversion" failed`
- the generated MLIR showed the FLA kernel using `f64` intermediates and then
  truncating to `bf16`, including an `f64 -> bf16` output path

This is no longer just a vLLM wrapper issue. The FLA gated RMSNorm Triton kernel
does not currently compile cleanly through the Intel XPU Triton lowering path in
this fullgraph/vLLM profile.

## Restore

Both temporary local vLLM source probes were reverted after the failed attempt.

The accepted backend was restored:

- session: `qwen36-tp4-gdn-reusequant-clone-envclean-32k`
- log: `/tmp/qwen36-quark-int8-tp4-gdn-reuseqkvzbaquant-clone-envclean-32k-noprefix-20260610.log`
- backend health: passed on `127.0.0.1:18080`
- frontdoor model listing: passed on `127.0.0.1:8000/v1/models`
- restored startup telemetry:
  - model load memory: `8.58 GiB`
  - model loading: `13.994800 s`
  - torch.compile: `4.33 s` from cached graph
  - available KV cache memory: `20.67 GiB`
  - max 32K concurrency estimate: `62.65x`
  - graph capture: `12 s`

## Decision

Reject `+rms_norm_gated` for the current Qwen3.6 Quark W8A8 INT8 XPU runtime.

Do not promote and do not quality/speed benchmark this candidate; it never
reaches a serving endpoint. The active stable path remains the accepted
GDN clone/no-prefix 32K backend.

## Lesson

The decomposed gated RMSNorm is a real optimization target, but the FLA Triton
custom op is not a drop-in win on Intel XPUs today. There are three separate
compile barriers:

1. XPU device-context guard is not fullgraph-safe.
2. XPU device-property query is not fullgraph-safe.
3. After those are bypassed, Intel Triton lowering rejects the generated gated
   RMSNorm kernel due to unsupported conversion involving `f64` intermediates.

If this path is revisited, the next attempt should be a proper XPU-safe gated
RMSNorm kernel or wrapper that keeps math in `fp32`/`bf16` and has a small direct
unit test before wiring it into the full vLLM graph.
