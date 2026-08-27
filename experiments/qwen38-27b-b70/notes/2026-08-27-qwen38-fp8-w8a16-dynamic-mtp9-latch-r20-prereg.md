# Preregistration: Qwen3.8 FP8 dynamic MTP9 reset-after-free latch R20

## Question

Does the corrected default-off busy-period latch preserve MTP9 for a genuine
singleton while keeping a concurrent batch on MTP1 through its slow tail?

R19 did not answer that performance question: it proved that checking for idle
inside `_free_request()` was too early. The corrected patch resets the peak
only after `_free_blocks()` deletes the final request from the scheduler's
authoritative request map. An isolated lifecycle test in the exact image
passed: peak 64 remained with one request outstanding and reset to zero only
after the final request free.

## Frozen runtime and treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-sd-latch-r2`,
  ID `sha256:7bd30381b4c57b2a853cf821ef118d1d60b8a27f398f6a263b630c7a04b6b012`;
- reset-after-free latch patch SHA-256
  `fe42ed628041032f51cf456ffcc03136f57be9415f34f32354965a655a2b13bf`,
  enabled only by `VLLM_DYNAMIC_SD_LATCH_PEAK_BATCH=1`;
- unchanged block-W8A16, active-width GDN, and active-Mamba-allocation patches;
- 2x B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, and direct oneCCL transport;
- schedule exactly `[[1,1,9],[2,128,1]]`;
- new container `qwen38-fp8-w8a16-mtp9-latch2-dynamic-mtp1-r20`, port 18143,
  and a previously nonexistent compile-cache directory.

## Ordered gates

1. Direct-verify every model weight and exact image/patch labels, then confirm
   the live schedule, latch environment, and 128-slot cap.
2. Require c2 complete token-ID identity, cache zero, zero cross-base
   collisions, engine health, 7/7 sequential exact cases, 8/8 repeat
   stability, and exact frozen-baseline agreement. Record c2 sequential-oracle
   agreement separately and do not hide a mismatch.
3. After one excluded conditioner, require the first eligible single-user row
   to return 128 cache-zero tokens at **at least 149.750706 tok/s**.
4. After one excluded transition, require the declared c64 batch to return all
   8192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions at **at least 1072.428472 aggregate tok/s**.
5. Require **512/512 synchronized exact-answer requests**, all cache-zero,
   followed by a healthy endpoint and zero-exit stop.
6. Preserve raw logs, inspection, checksums, and excluded receipts.

A pass authorizes only a separately preregistered R21 replication. Failure
closes this exact corrected treatment and retains MTP8. No missing concurrency,
context, or MTP depth is inferred, interpolated, or extrapolated.
