# Preregistration: Qwen3.8 FP8 dynamic MTP8-through-c2 R21

## Question

Can retaining MTP8 at batch size two accelerate the draining tail enough to
improve the promoted MTP8/MTP1 c64 rate without sacrificing singleton speed or
concurrent output identity?

The promoted schedule switches from K8 to K1 at batch size two. R20 showed
that forcing the tail to remain K1 slows it, while the unlatched high-K
singleton tail is beneficial. No prior lane tests K8 at c2. This bounded
treatment changes only the schedule boundary from `[[1,1,8],[2,128,1]]` to
`[[1,2,8],[3,128,1]]`.

## Frozen runtime and treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- unchanged block-W8A16, active-width GDN, and active-Mamba-allocation patches;
- 2x B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, and direct oneCCL transport;
- schedule exactly `[[1,2,8],[3,128,1]]`;
- new container `qwen38-fp8-w8a16-mtp8-c2-dynamic-mtp1-r21`, port 18144,
  and a previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify every model weight and exact image/patch labels, then confirm
   the live schedule and 128-slot cap.
2. Because c2 now uses K8 for the first time, require **2/2 complete,
   cache-zero, sequential-oracle-exact outputs** with zero cross-base
   collisions, followed by a healthy engine. Stop immediately on mismatch.
3. Require 7/7 sequential exact cases, 8/8 repeat stability, and exact
   frozen-baseline agreement.
4. After one excluded conditioner, require the first eligible singleton to
   return 128 cache-zero tokens at **at least 139.473697 tok/s** (95% of the
   promoted MTP8 singleton median).
5. After one excluded transition, require the declared c64 batch to return all
   8,192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **at least 1,094.314767 aggregate tok/s** (the promoted MTP8
   median, not the old 875 target).
6. Require **512/512 synchronized exact-answer requests**, all cache-zero,
   followed by a healthy endpoint and zero-exit stop.

A pass authorizes only a separately preregistered R22 replication. Promotion
would additionally require the replicated medians to exceed the existing
MTP8 profile while preserving both quality canaries. Failure closes this exact
threshold. No missing concurrency, context, or depth is inferred,
interpolated, or extrapolated.
