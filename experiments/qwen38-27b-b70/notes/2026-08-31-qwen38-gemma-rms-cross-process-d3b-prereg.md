# Qwen3.8 Gemma RMSNorm cross-process D3b preregistration

Date: 2026-08-31

Status: **preregistered before D3b operator calls**

D3 failed only because vLLM warning text preceded JSON on stdout. D3b repeats
the identical four-process, fixed-seed operator matrix from D3 at M=1 and all
12 strict prefill row counts, covering plain/fused and direct/serial/padded
RMSNorm. The only change is fail-closed receipt transport: each harness writes
JSON to an explicit mounted file and process logs are separate.

Pass/fail interpretation is unchanged. Every mode/case must repeat within a
process and yield one SHA-256 across all four fresh processes. A stable
alternative to an unstable direct path is a candidate repair; all-stable is a
negative causal screen. No model promotion follows from this diagnostic.
