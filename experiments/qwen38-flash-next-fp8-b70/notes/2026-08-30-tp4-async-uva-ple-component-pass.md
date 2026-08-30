# Qwen3.8 Flash-Next FP8 TP4 async-UVA PLE component pass

Date: 2026-08-30
Status: exact component pass; endpoint qualification pending

The default-off `VLLM_XPU_PLE_UVA_PREFETCH=1` candidate overlaps the sole
rank-local PLE table lookup with decoder layer 0. It deliberately preserves the
accepted arithmetic: raw FP8 owner rows are read on a side XPU stream, the main
stream joins at the layer-1 PLE boundary, and the existing int8 TP reduction,
FP8 reinterpretation, scaling, projections, gate, convolution, and addition
remain in their original order. No collective runs on the side stream.

This is a narrow XPU/eager/selective-UVA arm. It rejects process-worker PLE,
non-XPU platforms, disabled UVA, graph execution, a non-UVA offloader, a
missing selective PLE parameter, and models with more than one PLE layer.
Pending work is drained after an earlier-layer failure, and lifecycle state is
cleared after token validation or collective failure rather than poisoning
every later request.

Two four-card gates passed:

- the primitive lookup gate cycled distinct maximum, small, and medium row
  sets for 100 queued repetitions per rank and matched its CPU byte oracle;
- the direct-source gate invoked the modified vLLM n-gram, synchronous
  embedding, async start, and async finalize methods for 100 cycles of
  `64 -> 1 -> 42 -> 2` tokens. Every async output matched the synchronous
  output byte-for-byte on all four ranks, and every generation retained one
  stable cross-rank hash.

The focused source batteries pass (`28` NVIDIA-PLE/async tests and `11` AMD
model/trace/order tests, with five hardware cases skipped). Independent review
closed default-off per-layer overhead, non-FP8 masking, stream/buffer lifetime,
main-stream collective ordering, and exception cleanup. The public draft vLLM
PR was used only as a design input; this patch does not adopt its CUDA-specific
worker switch or its BF16-before-reduction arithmetic change.

This is not yet a performance result. The isolated side-stream gate has no
layer-0 work to hide the lookup behind, so its wall time is not interpreted.
The next gate is a trace-off, full-model endpoint comparison using the local
NVMe checkpoint, followed by the exact short and 4K quality/repeat battery.
Protected `5.515783 tok/s` target-only and approximately `20.727 tok/s` MTP4
results remain unchanged.

Structured receipt:
[`../data/20260830-tp4-async-uva-ple-component-pass.json`](../data/20260830-tp4-async-uva-ple-component-pass.json).
