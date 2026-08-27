# Preregistration: Qwen3.8 FP8 dynamic MTP8 R16 replication

R16 freezes the R15 runtime, model, workload, and exact
`[[1,1,8],[2,128,1]]` schedule in a new container, on port 18139, with a
previously nonexistent compile cache. R15 measured 146.80824408506146 tok/s
single-user and 1095.5536494164612 tok/s at c64.

The ordered gates are unchanged: direct model/image verification; c2 output
isolation; 7/7 sequential exact cases; 8/8 repeat stability; frozen-baseline
agreement; a first eligible cache-zero 128-token single row of at least
**139.467832 tok/s** (95% of R15); a complete, isolated, cache-zero c64 row of
at least **1073.642576 tok/s** (98% of R15); and 512/512 synchronized exact
answers. All raw receipts and shutdown state must be preserved.

If R16 passes, promote the R15/R16 medians. Otherwise retain MTP7. No absent
context, concurrency, or MTP depth is inferred, interpolated, or extrapolated.
