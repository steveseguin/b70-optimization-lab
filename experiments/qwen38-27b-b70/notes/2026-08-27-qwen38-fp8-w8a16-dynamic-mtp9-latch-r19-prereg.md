# Preregistration: Qwen3.8 FP8 dynamic MTP9 busy-period latch R19

## Question

Can a default-off busy-period peak latch retain MTP9 for a genuine singleton
while preventing a concurrent batch's final request from switching from MTP1
back to MTP9 and dominating aggregate wall time?

R17 measured 158.602109747958 tok/s for one user but only 889.6075857304468
tok/s at c64. Source inspection showed that dynamic speculative depth is
selected from the number of requests scheduled in each step. The new patch
latches the highest outstanding batch size until the service becomes idle.
An isolated scheduler test passed: a genuine singleton selected K9, while a
step scheduling only 7 of 64 outstanding requests selected and latched K1.

## Frozen runtime and treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-sd-latch-r1`,
  ID `sha256:312c501233ab61bca2642a4412a338baf054951b14feb39a1ad18fa5c104af86`;
- latch patch SHA-256
  `e15287dc97b448bc067ef7d2aa71cf2855a754ff621573470e4d643c54c7ca64`,
  enabled only by `VLLM_DYNAMIC_SD_LATCH_PEAK_BATCH=1`;
- unchanged block-W8A16, active-width GDN, and active-Mamba-allocation patches;
- 2x B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, and direct oneCCL transport;
- schedule exactly `[[1,1,9],[2,128,1]]`;
- new container `qwen38-fp8-w8a16-mtp9-latch-dynamic-mtp1-r19`, port 18142,
  and a previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify every model weight and exact image/patch labels, then confirm
   the live schedule, latch environment, and 128-slot cap.
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

A pass authorizes only a separately preregistered R20 replication. Failure
closes this exact latch treatment and retains MTP8. No missing concurrency,
context, or MTP depth is inferred, interpolated, or extrapolated.
