# Qwen3.8 official FP8 later-runtime c64 screen

Status: **complete negative screen; do not promote**.

The zero-overlay `4af586e185/1e90ffa672` runtime completed the frozen c64
shape at **736.090698 tok/s**, versus the protected `774.394144 tok/s` median:
`-38.303446 tok/s` or **-4.95%**. It also missed the preregistered
`813.113851 tok/s` continuation threshold.

All 64 responses completed 128 tokens, exposed complete raw token IDs,
reported zero cached prompt tokens, and had no cross-base frozen-oracle
collision. The output classification was
`output-isolation-qualified-shape-variant`; cleanup was clean. The excluded
identical c64 warmup measured `700.290379 tok/s` and is not a result.

This candidate receives no confirmation run and changes no public package or
headline. The complete evidence is preserved under
[`qwen38-fp8-tp2-http-p64-current-main-screen-20260826-r17-attempt1`](../data/qwen38-fp8-tp2-http-p64-current-main-screen-20260826-r17-attempt1/)
with a compact
[`result summary`](../data/2026-08-26-qwen38-fp8-tp2-http-p64-current-main-screen-r17-result.json).
