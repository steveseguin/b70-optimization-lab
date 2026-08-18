# Qwen3.8 Q8 output-head-only crossed-DP4A experiment

Date: 2026-08-18

Status: closed endpoint-neutral; exact and verifier-clean, not promoted

This arm isolated the exact crossed two-chain DP4A schedule to the standalone
Q8 output head (`K=5120`, local `N=124160`) after FFN, recurrent, and attention
isolation failed to reproduce a prior global-cross deep-direct signal. The
default-off same-binary door was
`GGML_SYCL_MMVQ_Q8_OUTPUT_HEAD_CROSS_DP4A=1`. All other kernel families,
weights, equal TP2 split, F16 KV, FlashAttention, and hardware/runtime policy
were unchanged. No speculation, MTP, or DFlash was used.

Unlike the fused-family experiments, strict verifier mode retained this
standalone shape: a TP2 `p0/n1` run announced treatment on both GPUs and ended
at `verified=990`, `VERIFY_MISMATCH=0`. Every packed weight/activation pairing
and exact integer sum is preserved before the unchanged FP32 scale/reduction.

## Direct gate

Complementary same-binary `p64/n512/r3` brackets both favored treatment:

- A-B-B-A: `36.8025765` treatment vs `36.6186630 tok/s` control, `+0.502240%`;
- B-A-A-B: `36.7406915` treatment vs `36.6060650 tok/s` control, `+0.367771%`;
- pooled: `36.7716340` vs `36.6123640 tok/s`, `+0.435017%`.

## Cache-zero endpoint gate

An initial four-suite endpoint capture printed valid primary metrics but used
colliding filenames due to a shell `local`-initialization bug; only its last
JSON survived. Those numbers are not promotion evidence. The corrected replay
retained four distinct JSONs, server logs, and benchmark logs.

| Pair | Arm | first-100 tok/s | full-decode tok/s | wall tok/s | TTFT ms |
| --- | --- | ---: | ---: | ---: | ---: |
| A-B | control | `37.076328826` | `36.589156600` | `36.128015059` | `174.363354` |
| A-B | treatment | `37.096171678` | `36.641938623` | `36.183276844` | `174.321708` |
| B-A | treatment | `37.066676648` | `36.623545610` | `36.170951469` | `174.391286` |
| B-A | control | `37.150139654` | `36.605170020` | `36.159929971` | `174.066126` |

First-100 pair deltas crossed: `+0.053519%`, then `-0.224664%`; pooled was
`-0.085711%` (`37.081424163` treatment vs `37.113234240 tok/s` control).
Pooled full decode was only `+0.097217%`, and wall throughput `+0.091693%`.
These are resolution-class and do not justify promotion.

All 48 requests were cache-zero, passed the fresh-response gate, and shared
the same 12-output hash set (`72dc31a52cf68f706da818720a493e085d2d622e2a64a71ebc204b62165d4e70`
for the canonicalized hash array). Candidate identities:

- SYCL library: `c2d9a43910927aabb295f798e5ea0ebc62d0e2dd32be827f3e1439ab3febaba4`;
- MMVQ object: `e1fa32c26fb1fb6bc569b83592c7a3a144780f21a44b019173461403236fd28e`;
- llama-bench: `74e7d48905196285f6e7cd8c8d0b20a8e25cf3f4731b1e2f0f5f6c49ad8d8865`;
- llama-server: `f7bc299a830cbbbbfc3e06ac46ef4f063b9d85e43995c04e07ffa9de0aa390bb`.

The exact patch is
[`q8-output-head-cross-dp4a-endpoint-neutral-20260818.diff`](../patches/q8-output-head-cross-dp4a-endpoint-neutral-20260818.diff),
and structured evidence is
[`2026-08-18-q8-output-head-cross-dp4a-endpoint-neutral.json`](../data/2026-08-18-q8-output-head-cross-dp4a-endpoint-neutral.json).
Raw evidence remains under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260818-output-head-cross-dp4a/`.
Both GPUs passed the post-run health gate.
