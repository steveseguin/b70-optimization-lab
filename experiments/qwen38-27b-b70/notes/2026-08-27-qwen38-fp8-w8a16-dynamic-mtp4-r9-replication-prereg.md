# Preregistration: Qwen3.8 FP8 dynamic MTP4 R9 replication

## Question

Does the R8 MTP4-at-one/MTP1-at-load result reproduce from a new container and
empty compile cache while retaining both its single-user gain and aggregate
rate under the same quality gates?

R8 measured 117.572120 tok/s for one user and 1,094.053681 aggregate tok/s at
c64. The runtime, implementation, schedule, and workload are frozen.

## Frozen runtime

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- 2× B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, direct oneCCL transport;
- dynamic schedule exactly `[[1,1,4],[2,128,1]]`;
- new container name and a previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify all model weights and exact image/patch labels; preserve the
   live command, image inspection, logs, and checksums.
2. Require c2 output isolation, 7/7 sequential exact cases, 8/8 repeat
   stability, and exact frozen-baseline agreement.
3. After one excluded conditioner, require the first eligible single row to
   return 128 cache-zero tokens at **≥111.693515 tok/s** (95% of R8 and still
   materially above the promoted MTP3 result).
4. After one excluded c64 transition, require the declared c64 row to return
   all 8,192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **≥1,072.172608 aggregate tok/s** (98% of R8).
5. Require **512/512 synchronized c64 exact-answer requests**, all cache-zero,
   followed by engine health and a zero-exit stop.

If every gate passes, use the R8/R9 medians for promotion. Otherwise retain
the existing MTP3-to-MTP1 package and close this exact treatment. No missing
context, concurrency, or speculative depth is inferred, interpolated, or
extrapolated.
