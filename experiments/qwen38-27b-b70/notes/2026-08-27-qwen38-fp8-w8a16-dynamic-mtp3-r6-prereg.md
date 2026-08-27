# Preregistration: Qwen3.8 FP8 dynamic MTP3-at-one/MTP1-at-load R6

## Question

Can one additional serial reuse of the checkpoint's single publisher MTP layer
improve the replicated dynamic service's one-user decode by at least 2% while
retaining its MTP1 aggregate operating point within 2% and passing the same
sequential and concurrent quality gates?

The frozen reference medians are 83.680193 tok/s for one user and 1,085.038992
aggregate tok/s at c64. This is a single treatment, not a depth or flag sweep.

## Frozen runtime and treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- unchanged block-W8A16, active-width GDN, and active-Mamba-allocation patches;
- 2× B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, direct oneCCL transport;
- only service change: maximum MTP depth 3 with schedule exactly
  `[[1,1,3],[2,128,1]]`, replacing `[[1,1,2],[2,128,1]]`;
- a new container name and previously nonexistent compile-cache directory.

The active-width kernel and Mamba allocation are width-generic: the maximum
state row becomes four positions, while two-or-more-request decode remains an
active width of two positions (target plus MTP1). No source or binary changes
are introduced in this screen.

## Ordered gates

1. Direct-verify every model weight and exact image/patch label, then confirm
   the live container command contains the frozen MTP3-to-MTP1 schedule.
2. Require the c2 output-isolation canary, engine health, 7/7 sequential cases,
   8/8 repeat stability, and exact agreement with the frozen static-MTP2
   baseline.
3. After one excluded conditioner, require the first eligible single-user row
   to return 128 tokens with zero cached tokens at **≥85.353797 tok/s** (2%
   above the promoted two-attempt median).
4. After one excluded transition, require the declared c64 batch to return all
   8,192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **≥1,063.338213 aggregate tok/s** (98% of the promoted
   median).
5. On the same live service, require **512/512 synchronized exact-answer
   requests**, all cache-zero, followed by a healthy endpoint and clean stop.
6. Preserve raw logs, container inspection, input/result checksums, and every
   excluded conditioning/transition receipt.

A pass is a positive screen only. Promotion requires a separately
preregistered fresh-server replication. A failure closes this exact MTP3
treatment without changing the promoted MTP2-to-MTP1 package. No missing
concurrency, context, or MTP depth is inferred, interpolated, or extrapolated.
