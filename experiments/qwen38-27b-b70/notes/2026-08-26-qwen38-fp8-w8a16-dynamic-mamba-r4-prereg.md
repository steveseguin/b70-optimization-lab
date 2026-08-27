# Preregistration: Qwen3.8 FP8 dynamic Mamba allocation R4

## Question

Can the single-service MTP2-at-one/MTP1-at-two-plus policy retain at least
82.810053 single-user tok/s and exceed **875 aggregate tok/s at c64** when
non-align Mamba state rows are allocated from the active dynamic lookahead
rather than the configured maximum?

R2 measured 817.007910 tok/s and 49.20× request capacity. Static MTP1 measured
1091.642460 tok/s and 70.14× capacity. R3 proved that reducing max model length
does not change the 49.20× state-row limit.

## Frozen treatment

- official `Qwen/Qwen3.8-27B-FP8` revision
  `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`;
- 2× B70/TP2, max length 256, 128 sequence slots, MBT512, block size 64,
  FP16 activations/KV, prefix cache off, direct oneCCL transport;
- dynamic schedule exactly `[[1,1,2],[2,128,1]]`;
- R2 active-width kernel repair unchanged;
- image
  `neural-download/vllm-openai-xpu:f01e-kernel-1e90-w8a16-dynamic-mamba-r1`,
  ID `sha256:2b79af686423379e4418aafa92d72e2248e8d09fabe609284dc7e29190cb8cd6`;
- only new treatment: patch SHA-256
  `3334c37f33677e4a499aa5959f79fb78d2fa47a39a350ab4bd1a120169512190`.

For FCFS, each request reserves the largest K that can still apply to the
eventual batch. This is conservative for arbitrary dynamic schedules. Priority
scheduling retains the old maximum allocation. Non-align Mamba converts the
passed lookahead to state blocks; full-sequence admission remains maximum-width.
The focused unit oracle is `[3,2,2,2]` blocks for four requests under the exact
K2→K1 schedule. All 19 dynamic-spec tests and the existing align-mode
variable-draft regression pass.

## Ordered gates

1. Direct-verify all model weight files and start the frozen image with a new
   compile cache. Record image labels, installed source hashes, server cache
   report, and container identity.
2. Run the former c2 crash canary: 2 requests, 256/256 returned tokens, complete
   token-ID capture, zero cross-base collisions, then require engine health.
3. Run the frozen 7/7 plus repeat 8/8 semantic suite and require exact equality
   to the static-MTP2 baseline.
4. Run one excluded single conditioner, then five rows. The first eligible row
   must return 128 tokens with zero cached tokens and measure at least
   **82.810053 tok/s after TTFT**.
5. Run one excluded c64 transition and one declared c64 batch. Each must return
   8,192 tokens with complete IDs, zero cached tokens, and zero cross-base
   collisions. The declared result passes at **≥875 tok/s**; >1,000 is
   preferred.
6. Stop after pass or failure. A passing result does not authorize publication
   until a separate fresh-server replication and 512-token concurrency quality
   canary are preregistered.

No c128, context, schedule, threshold, or graph sweep is authorized here. No
result will be interpolated or extrapolated.
