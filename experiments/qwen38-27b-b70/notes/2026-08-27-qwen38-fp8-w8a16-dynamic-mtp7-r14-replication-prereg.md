# Preregistration: Qwen3.8 FP8 dynamic MTP7 R14 replication

## Question

Does the R13 MTP7-at-one/MTP1-at-load result reproduce from a new container
and empty compile cache while retaining its single-user gain, c64 aggregate
rate, and exact-output behavior?

R13 measured 138.77859047437784 tok/s for one user and 1101.1864448314723
aggregate tok/s at c64. The runtime, implementation, schedule, and workload
are frozen before R14 starts.

## Frozen runtime

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- 2x B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, and direct oneCCL transport;
- dynamic schedule exactly `[[1,1,7],[2,128,1]]`;
- new container `qwen38-fp8-w8a16-mtp7-dynamic-mtp1-r14`, port 18137, and a
  previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify all model weights and exact image/patch labels; preserve the
   live command, image inspection, logs, and checksums.
2. Require c2 output isolation, 7/7 sequential exact cases, 8/8 repeat
   stability, and exact frozen-baseline agreement.
3. After one excluded conditioner, require the first eligible single row to
   return 128 cache-zero tokens at **at least 131.839661 tok/s** (95% of R13
   and still above the promoted MTP5 result).
4. After one excluded c64 transition, require the declared c64 row to return
   all 8192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **at least 1079.162716 aggregate tok/s** (98% of R13).
5. Require **512/512 synchronized c64 exact-answer requests**, all cache-zero,
   followed by engine health and a zero-exit stop.

If every gate passes, use the R13/R14 medians for promotion. Otherwise retain
the replicated MTP5-to-MTP1 package and close this exact MTP7 treatment. No
missing context, concurrency, or speculative depth is inferred, interpolated,
or extrapolated.
