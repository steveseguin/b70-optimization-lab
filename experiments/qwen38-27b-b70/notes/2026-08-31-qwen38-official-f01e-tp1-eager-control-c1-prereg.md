# Qwen3.8 official-f01e TP1 eager control C1 preregistration

Date: 2026-08-31

Status: **preregistered before either C1 model request**

## Question

The current deterministic candidate still differs across fresh TP1 servers,
while its production INT4 GEMMs, padded GDN B/A projection, Gemma RMS paths,
ordinary native GDN trajectory, and actual LM head have all repeated exactly
across fresh processes. Does the immutable official Intel runtime repeat the
same complete workload?

## Frozen control

- official image digest
  `sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f`;
- vLLM `ac7509e2b1db40fec2f03dde1ed4e9dfdc2338c9`, package
  `0.27.2rc1.dev77+gac7509e2b.xpu`, XPU kernels `0.1.12.3`;
- exact direct-verified local AutoRound model, local B70 GPU 0, TP1, MTP0,
  FP16 activation/KV, eager execution, XPU Graph and prefix caching off;
- new runtime cache and fresh server for each of `official-A` and
  `official-B`;
- fixed 12-prompt/six-class realistic suite, each prompt used once per arm,
  natural completion with a 512-token cap, temperature 0, complete streamed
  token IDs, and required `cached_tokens=0`;
- objective canaries after the performance workload; exact cleanup and kernel
  journal gates.

Pass requires 12/12 complete token arrays to match across the two fresh
servers, in addition to every per-arm gate. The two class-balanced rates are
diagnostic and cannot be promoted by this control.

A pass localizes the defect to differences in the newer current
runtime/kernel/overlay stack. A failure shows that the official parent also
has cross-server instability under the stronger suite; the next raw target is
then the full attention path. Neither outcome authorizes MTP or publication.
