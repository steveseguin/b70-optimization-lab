# Preregistration: Qwen3.8 FP8 dynamic MTP6-at-one/MTP1-at-load R12

## Question

Can one additional serial reuse of the checkpoint's single publisher MTP
layer improve the promoted dynamic service's replicated one-user decode median
by at least 2% while retaining at least 98% of its replicated c64 aggregate
median and passing the same sequential and concurrent quality gates?

The frozen promoted MTP5 medians are 128.4283182361941 tok/s for one user and
1098.3153567738368 aggregate tok/s at c64. This is one bounded treatment, not
a depth or flag sweep.

## Frozen runtime and treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- unchanged block-W8A16, active-width GDN, and active-Mamba-allocation patches;
- 2x B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, direct oneCCL transport;
- only service change: maximum MTP depth 6 with schedule exactly
  `[[1,1,6],[2,128,1]]`, replacing `[[1,1,5],[2,128,1]]`;
- a new container name, port, and previously nonexistent compile-cache
  directory.

## Ordered gates

1. Direct-verify every model weight and exact image/patch label, then confirm
   the live command contains the frozen MTP6-to-MTP1 schedule.
2. Require c2 output isolation, engine health, 7/7 sequential exact cases,
   8/8 repeat stability, and exact frozen-baseline agreement.
3. After one excluded conditioner, require the first eligible single-user row
   to return 128 tokens with zero cached tokens at **at least 130.996884
   tok/s** (2% above the promoted MTP5 median).
4. After one excluded transition, require the declared c64 batch to return all
   8192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **at least 1076.349049 aggregate tok/s** (98% of the promoted
   c64 median).
5. On the same service, require **512/512 synchronized exact-answer
   requests**, all cache-zero, followed by a healthy endpoint and zero-exit
   stop.
6. Preserve raw logs, container inspection, checksums, and every excluded
   conditioning/transition receipt.

A pass is a positive screen only. Promotion requires a separately
preregistered fresh-server R13 replication. Failure closes this exact MTP6
treatment without changing the promoted MTP5-to-MTP1 package. No missing
concurrency, context, or MTP depth is inferred, interpolated, or extrapolated.
