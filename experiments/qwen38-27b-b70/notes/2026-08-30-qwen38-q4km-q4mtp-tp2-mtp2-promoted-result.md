# Qwen3.8 Q4_K_M + Q4_0 MTP2 TP2 result

Date: 2026-08-30
Status: replicated; promotion-attestation preparation authorized

## Result

The two-card Q4_K_M target and one-card Q4_0 MTP draft compose correctly at
MTP depth 2 on this host. The fixed class-balanced, 99-interval varied-prompt
metric measured:

| arm | fresh server | tok/s | complete arrays vs MTP0 |
| --- | ---: | ---: | ---: |
| TP2 target-only, MTP0 | R1 | 49.787366 | oracle |
| TP2 target + MTP2 | R1 | 64.180644 | 12/12 exact |
| TP2 target + MTP2 | R2 | 64.293959 | 12/12 exact |

The promoted MTP2 headline is the median of the two fresh candidate servers:
**64.237301 tok/s**. That is **29.02%** above the matched fresh MTP0 oracle.
Candidate run-to-run drift was 0.18%. Across both MTP2 servers, all **24/24**
complete arrays matched the unchanged target-only oracle. Both suites used all
12 prompts across six classes once each, returned zero cached tokens on every
request, retained complete token IDs, and passed repeat, arithmetic, copy, and
JSON canaries.

## Exact profile

- target: `Qwen3.8-27B-Q4_K_M.gguf`, SHA-256
  `31629f53165ab6a7dad8c9847dcfd1fdf55829dac1e6e748f4a68581b0033d34`;
- draft: `mtp-Qwen3.8-27B-Q4_0.gguf`, SHA-256
  `50d9ce5a6da381bbcfb31061cf73df94a90e6faf8efeddee379a9cb8f1501c6e`;
- target devices: `SYCL0,SYCL1`, equal tensor split;
- draft device: `SYCL0`;
- F16 target/draft KV, FlashAttention on, 8K configured context, one slot;
- batch 1024, ubatch 256, eight CPU threads;
- prompt cache, context checkpoints, slot similarity, and reasoning disabled;
- runtime binary SHA-256
  `35f2d2327f05f42feb40f1a015ff46791e7277771ed97653f085be05a6f2c545`;
- SYCL backend SHA-256
  `0e7789313ac5776b197da813d482f78e2f396620cc745af0f9c1bb2ec39bd154`.

The exact compressed receipts and their uncompressed hashes are in
[`../data/qwen38-q4km-q4mtp-tp2-mtp2-20260830/`](../data/qwen38-q4km-q4mtp-tp2-mtp2-20260830/).
The [R1 comparison](../data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-screen-r1-result.json)
and [R2 comparison](../data/2026-08-30-qwen38-q4km-q4mtp-tp2-mtp2-replication-r2-result.json)
remain compact review artifacts.

## Boundary

This result qualifies only the measured short-context, one-user TP2/MTP2
profile. It does not inherit target-only 32K or concurrency results, does not
authorize deeper MTP, and is not a clean-host Intel installation test. The
model remained loaded between prompts, which is allowed steady state; no
prompt, KV, response, learned-draft, or repeated-fixture cache was used.
