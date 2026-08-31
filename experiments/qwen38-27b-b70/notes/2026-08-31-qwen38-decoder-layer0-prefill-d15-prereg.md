# Qwen3.8 decoder layer-0 prefill D15 preregistration

Date: 2026-08-31

Status: **preregistered before D15 model requests**

D14 was invalid because a process branched before its call-60 trace. D15 removes
generated-history ambiguity by hashing GDN layer 0's returned hidden-state and
residual on initial prefill call 0. The image, verified local model, TP1 eager
MTP0 lane, prompt, seed, and four fresh empty caches remain unchanged.

Different layer-0 pairs identify divergence in the first decoder layer. Exact
pairs require advancing the prefill boundary. Diagnostic only.
