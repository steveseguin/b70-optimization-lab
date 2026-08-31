# Qwen3.8 layer-1 GDN token-60 stage trace D41 preregistration

Date: 2026-08-31

Status: **preregistered before D41 model requests**

D40 found one identical layer-1 input and four different layer-1 outputs at
per-layer call index 62. D41 uses the established site-packages GDN stage hook
at layer 1/call 62 on the runtime-sitecopy repair image. At M=1 the packaged
prefill gate is inactive, so the hook mirrors the ordinary seven-argument XPU
GDN path: QKVZ, BA, recurrent core, gated norm, and output projection.

Across four fresh processes, the first stage with more than one hash is the
late decode causal boundary. The generic token-index guard is not authoritative
because call index includes two earlier engine calls; stage hashes and the D40
identical layer input are the preregistered evidence. No quality or speed claim
is authorized.
