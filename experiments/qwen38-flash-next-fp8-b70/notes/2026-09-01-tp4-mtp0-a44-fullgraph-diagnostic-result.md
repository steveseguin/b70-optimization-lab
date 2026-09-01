# Qwen3.8 Flash-Next FP8 A44 full-graph diagnostic result

Date: 2026-09-01
Status: major diagnostic speed positive; exact-4K reliability negative

The flattened A44 launcher was accidentally executed when the obsolete outer
wrapper source-only selector was used. The direct launch retained the official
FP8 checkpoint, TP4/EP4 MTP0, synchronous PLE-only placement, public oneCCL,
and full-decode-only size-1 graph. It did not retain the outer wrapper's Torch
trace export or supervisor lifecycle, so this run is diagnostic and cannot be
promoted.

The result nevertheless establishes the missing performance fact. Three
cache-zero p146/o256 rows returned the exact protected output hash at
`20.846123 / 20.507849 / 19.072700 tok/s`, median `20.507849 tok/s`. This is
about 3.72 times the protected `5.515783 tok/s` eager target-only result and
roughly equals the old MTP4 rate without speculation. The accepted quality
boundary also passed: 6/7 semantics with only the known code-case miss,
16/16 one repeat hash, and the exact cache-zero 4K needle.

The two exact-depth 4K rows passed transport at `12.215318 / 11.612849 tok/s`
but returned different output hashes. The first matched authority; the second
did not. Full graph therefore solves the short-decode dispatch bottleneck but
does not solve the existing long-prefill repeatability issue. No speed is
promoted, protected results remain unchanged, and teardown recovered memory,
swap, listener, and all four devices without reboot.

The next arm must use a standalone launcher that explicitly exports the bound
trace path, a real supervisor, and fresh paths. If exact 4K remains variable,
the production packet should cap the certified lossless context below that
boundary while the long-prefill issue remains a separate diagnosis.
