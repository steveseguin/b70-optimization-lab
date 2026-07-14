# DeepSeek V4 MHC post/pre fusion

The successful boundary is a true single-workgroup M=1 MHC post/pre kernel
after the standard TP4 collective. It preserves MHC-post accumulation order,
rounds every residual output to BF16, issues a convergent global/local
workgroup barrier, and only then performs the 24 projection reductions,
sigmoid/Sinkhorn gates, and weighted layer-input reduction.

The sequence mattered:

- Ring final-writeback plus MHC-post was exact but reached only `29.5955 tok/s`.
- Adding all of MHC-pre as an epilogue to that 1024-thread ring kernel passed
  exact changing-input and graph gates but fell to `27.0187 tok/s`. Work and
  register footprint on the collective critical path erased the launch saving.
- Keeping ring+post and moving pre to one dedicated kernel recovered
  `29.6193 tok/s`, proving the epilogue placement—not MHC-pre arithmetic—caused
  the large regression. The custom ring itself still lost to production oneCCL.
- Returning to production oneCCL and fusing only MHC post→BF16→pre reduced the
  isolated boundary from `119.262 us` to `80.574 us`. Forty changing cases were
  bitwise exact; all four graph outputs both changed and matched the reference.

Three strict cold suites reached `30.340369`, `30.213779`, and `30.240489`
tok/s. Their combined 36-prompt median was `30.270674 tok/s`; all prompts were
unique, all reported `cached_tokens=0`, and speculation/history/prefix reuse
were disabled. Sequential `1073 -> 437 -> 1073`, exact copy, Paris, and strict
JSON canaries passed.

The best valid run was approved on LocalMaxxing as
`cmrl9xiwe06zzmj01cof0k38p`. This is a small record, not a route to 50+ tok/s
by itself. The durable architectural lesson is to fuse compute boundaries
within one card while keeping extra arithmetic off the PCIe collective's
critical progression.

Structured evidence is in
`experiments/deepseek-v4-flash-reap-xpu-b70/data/mhc-post-pre-fusion-20260714.json`.
