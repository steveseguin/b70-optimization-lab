# Qwen3.8 layer-1 GDN state after prefill D43 preregistration

Date: 2026-08-31

Status: **preregistered before D43 model requests**

D42 proved convolution and SSM state already differ before late decode call 62.
D43 applies the identical synchronizing before/after state trace to layer 1
prefill call 2 (M=71) on the runtime-sitecopy projection-repair image.

Across four fresh processes:

- pre-core convolution and SSM state should be identical initial state;
- if post-core state differs, the prefill core/final-state path creates the
  drift even when its returned layer output is exact;
- if post-core state is identical, divergence begins during decode and a
  bounded earlier-call search follows.

No performance or production claim is authorized.
