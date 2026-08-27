# Preregistration: Qwen3.8 FP8 dynamic Mamba allocation R5 replication

## Question

Does the R4 active-Mamba-allocation result reproduce from a new container and
empty compile cache, while passing exact-answer quality under the same c64
concurrency that produces the aggregate result?

R4 measured 1,087.492388 aggregate tok/s and 83.665057 single-user tok/s. This
replication freezes the implementation and service; it is not another tuning
sweep.

## Frozen runtime and service

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- active-Mamba-allocation patch SHA-256
  `3334c37f33677e4a499aa5959f79fb78d2fa47a39a350ab4bd1a120169512190`;
- 2× B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, direct oneCCL transport;
- dynamic schedule exactly `[[1,1,2],[2,128,1]]`;
- new container name and a previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify every model weight and verify the exact image ID, patch
   labels, installed source, and container command.
2. Repeat the R4 c2 output-isolation canary, 7/7 plus repeat-8 semantic suite,
   and exact static-MTP2 baseline comparison.
3. After one excluded conditioner, require the first eligible single-user row
   to return 128 tokens with zero cached tokens at **≥82.810053 tok/s after
   TTFT**.
4. After one excluded c64 transition, require the declared c64 batch to return
   8,192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions. It must measure both **≥875 tok/s** and **≥1,033.117768 tok/s**
   (95% of R4).
5. On that same live service, run the existing exact-answer canary at c64 for
   eight synchronized rounds: **512/512 requests must pass**, all cached-token
   counts must be zero, and the engine must remain healthy.
6. Stop the service, preserve final logs/inspect/checksums, and reject the
   replication on any runtime crash or unexplained error.

If every gate passes, R4+R5 authorize promotion of the exact measured c64 and
single-user profile into the repo package/site. Only measured values may be
published; no other concurrency, context, or MTP depth is inferred,
interpolated, or extrapolated.
