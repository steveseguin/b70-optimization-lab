# Laguna 122.829 record current-stream event-profile preregistration

Date: 2026-07-31 America/Toronto

Status: **diagnostic only; no benchmark, endpoint, or submission claim
authorized**.

## Purpose

The transposed-scale record is conventionally `122.828558121099 tok/s`, while
the requested frontier is 130. Historical cycle attribution predates width 12,
the current DFlash graph stack, GRF128 target decode, and contiguous target
scales. It is no longer an adequate basis for selecting the next candidate.

Run the existing default-off current-XPU-stream event profiler on the exact
record stack. It places timing events around the already audited target replay
callbacks and changes no tensor, operation, callback order, graph segment,
collective, attention call, model precision, or arithmetic.

## Frozen execution

- vLLM: `34b43849fc7c8ff8633f223469cc2a0d525c256e`;
- XPU kernels: `8dd94f2307db3b830fe07f212c4b36f719652a5c`;
- grouped-GEMM SHA-256:
  `c4845ed7704a9afcf59e12f9d51e288f293f2e39966e283e2a7e322fed68b839`;
- BF16 KV, width 12 / depth 11, one active generation;
- target topology 146 graphs / 145 eager breaks per rank;
- draft topology 14 / 13 per rank;
- fixed cold 13-prompt suite, no warmup, no retry, cache-zero required;
- exact target-q1 token and text comparison remains mandatory;
- runtime lock:
  `experiments/laguna-s-2.1-xpu-b70/tools/runtime-lock-transposed-scales.json`.

The diagnostic uses exactly one fresh measurement-leg process with a new
owner-private event root. Because event synchronization intentionally perturbs
one verifier replay, any rate emitted by the surrounding harness is invalid
and must not be quoted, promoted, compared, or submitted.

## Interpretation

Require four complete rank files, 146/145 topology, identical segment-kind
order, exact/cache-zero suite completion, clean teardown, and post-run idle.
Select only one real rank's internally consistent total and category sums; do
not combine per-category maxima from different ranks.

This profiler observes the first audited replay and may include cold replay or
frequency effects. XCCL may use an internal stream, so collective completion is
not a validated global critical path. Results are directional candidate
selection only:

- graph-dominated: inspect repeated layer graph positions and target grouped
  GEMM/device-kernel work;
- attention-dominated: revisit only exact attention execution, not KV dtype;
- collective-dominated: require completion-join proof before changing any
  boundary or topology;
- no material concentration: stop micro-tuning this replay wrapper and profile
  the draft/current full cycle separately.

No reset, reboot, privileged recovery, source mutation, endpoint claim, or
LocalMaxxing submission is authorized by this diagnostic.
