# Plan: one cache read for all draft rows in the verifier's attention (one card, long prompts)

## Why

After a long prompt the one-card writing speed falls from 66 tok/s (16K) to about 40 (24K+), and the profile
([findings](2026-09-16-fp8-review-findings.md#where-the-writing-speed-goes-after-long-prompts-september-17-2320-utc-the-verifiers-per-row-attention))
puts the context-dependent part in the verifier's attention: the
[verifier-rows overlay](../../../packages/qwen38-27b-fp8-tp1-b70/overlays/b70_fa_verify_rows.py) issues one
single-query decode call per draft row above 1,536 keys (six per layer, 106 per step), and each call rereads the
layer's cache. At 32K that is 12 GB per step, 27.6 ms of an 89 ms step, and it grows 6.4 ms per 8K.

## What the kernel does today

- `flash_api.cpp::mha_varlen_fwd`: any call with `max_seqlen_q > 1` (and no mixed batch) goes to the
  chunk-prefill kernel; the split-K decode kernel (`paged_decode`) only ever sees `max_seqlen_q == 1` and is called
  with `is_causal=false` (the comment there explains why: with several rows its causal formula adds `q_sg_tile`
  extra KV positions).
- The census (`qwen38-fa-verify-row-census.py`) found that row r of a 6-row chunk-prefill call equals the same
  query alone up to 1,984 keys and differs by FP16 ULPs beyond: the decode kernel's split-K combine (splits begin
  at 16 KV tiles of 64, `get_num_splits`) versus the prefill kernel's single pass. Hence the per-row overlay.
- The image's `_spec_decode_varlen_fwd` fast path already flattens rows into pseudo-sequences for the decode kernel
  (one launch), but every pseudo-sequence still reads the cache, and its split plan is built for the whole batch, so
  its rows differ from lone rows once splits start. Forcing the lone-row split count per pseudo-sequence would make
  it bit-identical to the overlay's calls, but it saves only launches: the six calls are already at the bandwidth
  floor (6 x 128 MB per layer at 32K, ~1.5 ms).

## The lever

A decode-kernel variant that holds the six draft positions in its Q tile alongside the six GQA heads it already
packs there (`paged_decode_kernel.hpp`: "Decode packs the GQA head-group into the Q/row dimension"), applies each
position's causal limit (`seqused_k - (5 - j)`), and keeps the lone-row split plan and per-split accumulation order.
Then every KV tile is read once for all 36 rows of a KV head. If each row's result equals the lone-row call bit for
bit, the verifier's attention cost at 32K drops from 27.6 ms to about 5 ms per step (+25% writing speed at 32K,
+16% at 16K, nothing under 1,536 keys), with the outputs unchanged.

## Steps

1. **Census first, no serving:** a research build (r312) that exposes `paged_decode` with `max_seqlen_q = 6`
   (batch 1, per-position causal limits) as a separate op; compare its rows with six lone-row calls at 2K to 40K
   keys, contiguous and scattered pages, as the 2026-09-15 census did. If the rows are not bit-identical, find
   which part of the row arithmetic changes with the row count (MMA tile shape, split boundaries, epilogue order)
   and fix that before anything else.
2. **Overlay routing:** replace the per-row loop in `b70_fa_verify_rows.py` with one call to the new op for the
   one-request verify case; prefill chunks and batches unchanged.
3. **Gates:** strict twice, ladder, 2K/8K/16K and the long-corpus 24K/30K/36K probes vs the no-MTP references,
   logprob replay; then the package (R312 image) if exact.

Kernel build notes: build with the service stopped (`chunk_gated_delta_rule_xe2.cpp` needs the 14 GB cap); the
attention kernels are under `csrc/xpu/attn/xe_2` (cutlass/sycl-tla), bound through `csrc/flash_attn/flash_api.cpp`.
