# Qwen3.8-27B Q4_K_M TP2 c96 F16 activation-dedup neutral result

The default-off c96 activation-conversion dedup passed its exactness gates but
is **performance-neutral and rejected**. Feature-on attempts measured
`192.875824` and `192.825265 tok/s`, centering at `192.850545 tok/s`. Because
that was only `+0.0906%` over a different Intel AOT binary, a preregistered
same-binary control was required before attributing the delta.

With the exact candidate backend and the feature disabled, two fresh controls
measured `192.821156` and `192.914725 tok/s`, centering at **`192.867941
tok/s`**. Feature-on was therefore `-0.0090%` versus its matched control. The
apparent cross-build improvement was AOT/run variation, not an optimization.

Both fresh servers matched the frozen same-shape c96 oracle 96/96 by complete
128-token-ID digest. Prompt caching was disabled, every cached-token count was
zero, the candidate marker fired, the rejected dual-GEMM marker remained
absent, no cross-base collision occurred, and the kernel/journal gates stayed
clean.

The mechanism is exact and narrowly scoped. Adjacent `ffn_gate` and `ffn_up`
GEMMs at `[96,5120]` consume the same F32 activation. The candidate converts
that activation to F16 once per backend graph generation and device, then
feeds the unchanged F16 bytes to the second oneDNN GEMM. It is disabled unless
`GGML_SYCL_F16_ACT_DEDUP=1`, and it refuses every non-c96 or non-gate/up shape.

This experiment remains an aggregate c96 capacity measurement with the same
effective 49,152-token pool and exact `ffn_down,ffn_gate` weight cache as its
incumbent. It does not transfer to single-user decode, MTP, other context
depths, or batch-invariant text. The candidate patch is retained as negative
evidence, while the active source and backend were restored byte-for-byte to
the r26 identities. Complete identities and artifact hashes are in the
[structured result](../data/2026-08-30-qwen38-q4km-tp2-c96-f16-act-dedup-r27-results.json).
