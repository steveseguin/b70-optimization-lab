# Qwen3.8 27B Q8 TP2 DP4A4 × SG24 synergy

Date: 2026-08-17

Status: **closed as endpoint-neutral; do not promote or repeat unchanged**

## Decision

Retain the accepted two-independent-accumulator DP4A2×SG24 source. The
four-independent-accumulator DP4A4×SG24 candidate was exact and positive in a
fully position-complemented direct screen, but that gain did not transfer to
two opposite-order cold endpoint pairs.

This was a materially different retry of the older DP4A4-under-SG8 result.
The candidate used the same accepted Qwen3.8 SG16/SG24 geometry as control;
only the Q8 row body's compile-time integer scheduling differed. Four signed
DP4A results were combined in integer space before the unchanged per-block
FP32 scale/accumulation boundary.

## Identity

- model: `Qwen3.8-27B-Q8_0.gguf`, SHA-256
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- base: mndodd `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- control: promoted DP4A2 + SG16 + SG24
- candidate: DP4A4 + SG16 + SG24
- compiler: Intel oneAPI DPC++ 2026.1.1 (`2026.1.1.20260724`)
- runtime: equal TP2, `level_zero:1,0`, F16 KV, FlashAttention,
  `b1024/ub256`, reasoning off, no speculation

Every non-`vecdotq.hpp` modified source file matched the promoted DP4A2 tree
byte-for-byte before the clean candidate build.

## Direct gate

The first sequence was `A-B-B-A,B-A-A-B`; the second swapped every arm in
every position. Each fresh process ran `p64/n256/r3`.

| Block | DP4A2 SG24 | DP4A4 SG24 | Delta |
| --- | ---: | ---: | ---: |
| First 8 | 37.100782 | 37.258297 | +0.425% |
| Position complement | 37.201425 | 37.474236 | +0.733% |
| All 16 mean | 37.151104 | 37.366266 | **+0.579%** |

All 16 processes ended at `VERIFY_MISMATCH=0`.

## Cold endpoint gate

Two opposite process-order pairs used fresh servers, 12 unique prompts, at
most 512 generated tokens, one 8K slot, and `cached_tokens=0` throughout.

| Order | Primary delta | Full-decode delta | Wall delta |
| --- | ---: | ---: | ---: |
| control → candidate | +0.130% | -0.045% | +0.046% |
| candidate → control | -0.081% | +0.049% | -0.161% |
| pooled pair medians | **+0.0245%** | **+0.0021%** | **-0.0576%** |

Pooled primary medians were `37.064684` control and `37.073780 tok/s`
candidate. Pooled full-decode medians were `36.689234` and `36.690013 tok/s`.
Candidate TTFT was 0.882% worse. The directions cross and all throughput
deltas are noise-level, so DP4A4 is not promoted.

All four endpoint suites passed the fresh-response gate, were cache-zero, and
produced the same 12 complete output SHA-256 values. Both B70s remained normal
with no current-boot Xe fault, reset, timeout, or hang.

The focused source increment is
[`q8-dp4a4-sg24-neutral-20260817.diff.gz.b64`](../patches/q8-dp4a4-sg24-neutral-20260817.diff.gz.b64).
Structured data is in
[`2026-08-17-q8-dp4a4-sg24-neutral.json`](../data/2026-08-17-q8-dp4a4-sg24-neutral.json).
Raw local evidence remains at
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-dp4a4-sg24/`.
