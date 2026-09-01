# Qwen3.8 FP8 TP2 MTP1 R73: no active CUDAGraph path

R73 was stopped before its first HTTP request. Startup proved that the
qualified R62 profile has `VLLM_XPU_ENABLE_XPU_GRAPH=0` and initializes the
engine with `cudagraph_mode=NONE`, while retaining vLLM compiled execution.
Consequently the hash-bound CUDAGraph replay hook produced zero records and
cannot localize this lane.

The model passed direct-I/O verification, no new GPU/Xe fault occurred, and no
speed or output claim was generated. R74 moves the identical bounded row-hash
strategy to `PiecewiseBackend.__call__`, the Python dispatcher around the
active compiled segments.

Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-cudagraph-boundary-trace-r73-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-cudagraph-boundary-trace-r73-result.json).
