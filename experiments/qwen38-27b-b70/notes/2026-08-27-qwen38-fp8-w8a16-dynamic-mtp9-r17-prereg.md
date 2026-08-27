# Preregistration: Qwen3.8 FP8 dynamic MTP9-at-one/MTP1-at-load R17

## Question

Can singleton MTP depth nine improve the newly promoted MTP8 service by at
least 2% while retaining at least 98% of its replicated c64 aggregate median
and passing the same exact-output gates?

The frozen promoted MTP8 medians are 146.81441784235233 tok/s for one user and
1094.314767229035 aggregate tok/s at c64. R17 is one bounded treatment,
preregistered before its server starts.

## Frozen runtime and treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- unchanged block-W8A16, active-width GDN, and active-Mamba-allocation patches;
- 2x B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, and direct oneCCL transport;
- only service change: schedule exactly `[[1,1,9],[2,128,1]]`;
- new container `qwen38-fp8-w8a16-mtp9-dynamic-mtp1-r17`, port 18140, and a
  previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify every model weight and exact image/patch label, then confirm
   the live MTP9-to-MTP1 schedule.
2. Require c2 output isolation, engine health, 7/7 sequential exact cases,
   8/8 repeat stability, and exact frozen-baseline agreement.
3. After one excluded conditioner, require the first eligible single-user row
   to return 128 cache-zero tokens at **at least 149.750706 tok/s** (2% above
   the promoted MTP8 median).
4. After one excluded transition, require the declared c64 batch to return all
   8192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **at least 1072.428472 aggregate tok/s** (98% of the promoted
   c64 median).
5. Require **512/512 synchronized exact-answer requests**, all cache-zero,
   followed by a healthy endpoint and zero-exit stop.
6. Preserve raw logs, inspection, checksums, and excluded receipts.

A pass authorizes only a separately preregistered R18 replication. Failure
closes this exact MTP9 treatment and retains MTP8. No missing concurrency,
context, or MTP depth is inferred, interpolated, or extrapolated.
