# Qwen3.8 packaged GDN pad D37r preregistration

Date: 2026-08-31

Status: **preregistered before D37r model requests**

D37's reconstructing tracer bypassed the packaged forward and is invalid.
D37r runs the sealed r2 image with a non-invasive hook that calls the packaged
`QwenGatedDeltaNetAttention.forward_xpu` unchanged at every layer/call. At
layer 0 call 2 it hashes the input and returned output only after the forward
completes. No projection, recurrent-core operation, tensor, or state is
reconstructed or replaced.

Across four fresh processes, input and output hashes must match and all 64
generated token IDs must be identical. The trace JSON itself must be
byte-identical. A pass authorizes the strict varied-prompt determinism and
independent quality suite; it does not authorize a speed claim.
