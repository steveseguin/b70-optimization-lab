# Qwen3.8 layer-0 GDN stages call-2 D31 preregistration

Date: 2026-08-31

Status: **preregistered before D31 model requests**

D30 proves the complete layer-0 GDN output differs on decode call 2. D31
retains all frozen conditions and reproduces the production XPU forward while
retaining references to these boundaries: hidden input, QKVZ projection, BA
projection, recurrent-core output, output gate, gated norm output, flattened
norm output, and final output projection. It hashes the retained tensors only
after all GDN computation has been enqueued, avoiding a host synchronization
before the suspect core operation.

Four fresh processes are required. The earliest differing boundary determines
the next causal split. Diagnostic only; no speed or quality claim.
