# Qwen3.8 layer-0 GDN stages call-2 D31r preregistration

Date: 2026-08-31

Status: **preregistered before D31r model requests**

D31 was technically invalid: the instrumentation used an obsolete custom-op
signature and failed before writing a trace. D31r uses the current production
signature, including `_xpu_conv_state` and `_xpu_ssm_state`. It otherwise
retains D31's frozen four-process workload and its post-computation hashes of
the hidden input, QKVZ and BA projections, recurrent-core output, output gate,
gated norm, flattened norm, and final output projection.

The earliest boundary with different hashes determines the next causal split.
Diagnostic only; no speed or quality claim.
