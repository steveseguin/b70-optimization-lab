# Preregistration: Qwen3.8 FP8 dynamic MTP3 R7 replication

## Question

Does the R6 MTP3-at-one/MTP1-at-load result reproduce from a new container and
empty compile cache while retaining the promoted service's aggregate floor and
passing the same concurrent quality gate?

R6 measured 99.712488 tok/s for one user and 1,066.000395 aggregate tok/s at
c64. This replication freezes the implementation and service; it is not
another tuning sweep.

## Frozen runtime

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- 2× B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, direct oneCCL transport;
- dynamic schedule exactly `[[1,1,3],[2,128,1]]`;
- new container name and a previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify all model weights and exact image/patch labels; record the
   command, image inspection, logs, and checksums.
2. Require c2 output isolation, 7/7 sequential exact cases, 8/8 repeat
   stability, and exact frozen-baseline agreement.
3. After one excluded conditioner, require the first eligible single row to
   return 128 cache-zero tokens at **≥94.726864 tok/s** (95% of R6 and still
   materially above the currently promoted MTP2 result).
4. After one excluded c64 transition, require the declared c64 run to return
   all 8,192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **≥1,063.338213 aggregate tok/s**. This retains at least 98%
   of the currently promoted aggregate median.
5. Require **512/512 synchronized c64 exact-answer requests**, all cache-zero,
   followed by engine health and a zero-exit clean stop.

If every gate passes, use the R6/R7 medians for promotion. Otherwise retain the
existing MTP2-to-MTP1 package unchanged and close this exact treatment. No
missing context, concurrency, or speculative depth is inferred, interpolated,
or extrapolated.
