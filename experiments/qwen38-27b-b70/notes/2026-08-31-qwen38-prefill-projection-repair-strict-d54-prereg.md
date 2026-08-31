# D54 preregistration: projection-repair strict qualification

Date: 2026-08-31

D53 passed byte-identical 64-layer traces and complete outputs in four fresh
processes. D54 is the first non-tracing qualification of the same repair. It is
not a promotion until every gate below passes.

The candidate is the frozen GDN repair image plus the hash-bound sitecustomize
repair for dense MLP down and full-attention QKV/output projections when
`32 < M < 512`. It remains TP1/MTP0, uses local ext4 weights, GPU 0, eager mode,
no prefix caching, temperature 0, and a new compile/cache root.

Required gates:

1. direct model-manifest verification;
2. all 12 unique prompts in `realistic-suite-v1.json`, once each;
3. natural EOS, at least 100 streamed token events, cached tokens zero, and the
   complete final performance gate;
4. the median of prompt-class medians, never a fixture or best-row headline;
5. objective arithmetic, copy, JSON, and eight-repeat determinism canaries;
6. clean post-run shutdown and no new GPU, filesystem, OOM, or kernel fault.

The output remains candidate evidence pending a second fresh strict replay with
per-prompt token-ID comparison. No D53 or D54 diagnostic speed may be promoted.
