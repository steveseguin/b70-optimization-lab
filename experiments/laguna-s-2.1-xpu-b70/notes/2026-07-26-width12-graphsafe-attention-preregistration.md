# Laguna width-12 graph-safe attention candidate

Date: 2026-07-26 America/Toronto

Status: **preregistered before build completion or device execution**.

## Hypothesis

The current exact width-12 result is `100.524890 tok/s`, `13/13` bitwise
exact, with `146/145` target topology. It needs a `1.47%` gain, equivalent to
about `0.57 ms` from the measured `39.35 ms` verifier cycle if emitted tokens
per cycle remain unchanged.

Laguna leaves 48 FlashAttention bodies eager inside each target replay. Earlier
in-process telemetry measured their Python/eager-boundary host path at
`8.118 ms` median per width-8 replay. An attempted attention-subgraph capture
failed before measurement because the chunk-prefill launcher used
`sycl_ext_oneapi_work_group_scratch_memory`, which the installed SYCL Graph
runtime refuses to record.

The Qwen 3.6 27B lane previously removed the same blocker by replacing the
dynamic scratch launch property with a typed, handler-owned
`sycl::local_accessor`. That representation is recordable by SYCL Graph and
preserved exact outputs in that lane.

Width-12 speculative verification already dispatches through the same
`chunk_prefill` launcher. The candidate therefore changes only that launch
representation and enables the existing default-off attention-subgraph
selector. It does not force another attention algorithm.

## Candidate and controls

- kernel source change: convert `chunk_prefill` work-group scratch to a typed
  handler-owned local accessor;
- build only the checked-in default attention policy sets, which include both
  Laguna head-128 full and sliding-attention tuples;
- target width `12`, DFlash depth `11`, TP4/EP4, batch one;
- shared-elementwise and QKNorm/RoPE fusions off, matching the valid width-12
  result;
- draft graph off and local argmax off;
- prebuilt exact-attention metadata off because the current runtime contract
  deliberately forbids combining two attention experiments;
- candidate selector:
  `VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=1`;
- control selector: the same rebuilt kernel with that selector `0`.

The rebuilt `_vllm_fa2_C` shim and `libattn_kernels_xe_2.so` hashes must be
recorded in every leg identity. Kernel source identity alone is insufficient
for this candidate.

## Gates

1. The reduced-policy FA2 library must build cleanly.
2. A candidate leg must capture and replay on all four ranks without the prior
   scratch-memory error.
3. It must retain `13/13` bitwise equality to the frozen q=1 teacher,
   cache-zero responses, one active generation, and clean cold process/device
   lifecycle.
4. Outer topology must remain `146` graphs and `145` eager boundaries on all
   ranks. Attention subgraphs replace Python submissions but do not remove the
   audited outer boundary labels.
5. Compare against a same-binary selector-off control before attributing the
   gain to capture.
6. Promote only an exact, policy-compliant measured result at or above
   `102 tok/s`; diagnostic replay time is never record evidence.

Any unsupported capture, output mismatch, topology drift, missing identity,
process leak, or device-health failure rejects the candidate. There is no
fallback while the selector is enabled.
