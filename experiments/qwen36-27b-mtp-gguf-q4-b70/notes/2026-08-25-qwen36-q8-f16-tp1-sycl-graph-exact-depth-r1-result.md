# Qwen target-Q8/F16 TP1 SYCL graph exact-depth R1 result

State: **failed at depth 0 evidence parsing; cleanup passed**.

Depth 0 completed normally and emitted valid `llama-bench` JSON. Its stderr
proved a graph-enabled build and `GGML_SYCL_ENABLE_GRAPH=1`, and the Q8 footer
reported 665 backend graph-compute entries. However, `llama-bench` suppresses
`GGML_LOG_INFO` by default, so neither the per-action SYCL graph counters nor
the destructor summary were visible. The strict evidence parser correctly
rejected the row rather than inferring capture/replay from configuration.

The output root is immutable. A distinct retry must add only `llama-bench -v`,
which exposes info-level graph evidence, while preserving the seven contexts,
source, backend, DSO closure, model, and protected-value boundaries. No R1 row
is promotable and no graph-off value was replaced.
