# Preregistration: Qwen3.8 FP8 dynamic MTP9 p64 recovery R18

## Question

Can limiting the exact MTP9 service to the measured 64 scheduler slots recover
its failed c64 aggregate rate while retaining a useful singleton gain and the
same output-quality boundary?

R17 measured 158.602109747958 tok/s for one user but only 889.6075857304468
tok/s at c64. Its startup reported only 4,062 KV tokens and 15.87x nominal
256-token concurrency. R18 changes only `max_num_seqs` from 128 to 64 and
narrows the schedule coverage to `[[1,1,9],[2,64,1]]`. This is a bounded
recovery treatment preregistered before its server starts.

## Frozen runtime and treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- unchanged block-W8A16, active-width GDN, and active-Mamba-allocation patches;
- 2x B70/TP2, max length 256, **64 sequence slots**, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, and direct oneCCL transport;
- MTP9 only at one active request and MTP1 at two through 64;
- new container `qwen38-fp8-w8a16-mtp9-p64-dynamic-mtp1-r18`, port 18141, and
  a previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify every model weight and exact image/patch label, then confirm
   the live MTP9-to-MTP1 schedule and 64-slot cap.
2. Require c2 output isolation, engine health, 7/7 sequential exact cases,
   8/8 repeat stability, and exact frozen-baseline agreement.
3. After one excluded conditioner, require the first eligible single-user row
   to return 128 cache-zero tokens at **at least 149.750706 tok/s**.
4. After one excluded transition, require the declared c64 batch to return all
   8192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **at least 1072.428472 aggregate tok/s**.
5. Require **512/512 synchronized exact-answer requests**, all cache-zero,
   followed by a healthy endpoint and zero-exit stop.
6. Preserve raw logs, inspection, checksums, and excluded receipts.

A pass authorizes only a separately preregistered R19 replication. Failure
closes this exact p64 recovery and retains MTP8. No missing concurrency,
context, or MTP depth is inferred, interpolated, or extrapolated.
