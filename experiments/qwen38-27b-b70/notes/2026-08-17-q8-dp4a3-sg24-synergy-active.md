# Qwen3.8 27B Q8 TP2 DP4A3 × SG24 synergy

Date: 2026-08-17

Status: **closed as endpoint-neutral; do not promote or repeat unchanged**

## Decision

Retain the accepted two-independent-accumulator DP4A2×SG24 source. The
three-independent-accumulator DP4A3×SG24 candidate was exact and positive in
both halves of a fully position-complemented direct screen, but that gain did
not transfer to two opposite-order cold endpoint pairs.

The candidate assigned one reordered-Q8 DP4A operation to each of three
independent integer accumulators and folded the fourth operation into the
first chain. The three integer partial sums were combined before the unchanged
per-block FP32 scale/accumulation boundary. Every other promoted optimization
and runtime setting remained fixed.

## Identity

- model: `Qwen3.8-27B-Q8_0.gguf`, SHA-256
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- base: mndodd `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- control: promoted DP4A2 + SG16 + SG24
- candidate: DP4A3 + SG16 + SG24
- compiler: Intel oneAPI DPC++ 2026.1.1 (`2026.1.1.20260724`)
- runtime: equal TP2, `level_zero:1,0`, F16 KV, FlashAttention,
  `b1024/ub256`, reasoning off, no speculation

Every non-`vecdotq.hpp` modified source file matched the promoted DP4A2 tree
byte-for-byte before the clean candidate build.

## Direct gate

The first sequence was `A-B-B-A,B-A-A-B`; the second swapped every arm in
every position. Each fresh process ran `p64/n256/r3`.

| Block | DP4A2 SG24 | DP4A3 SG24 | Delta |
| --- | ---: | ---: | ---: |
| First 8 | 36.896162 | 37.022298 | +0.342% |
| Position complement | 37.130981 | 37.520516 | +1.049% |
| All 16 mean | 37.013571 | 37.271407 | **+0.697%** |

All 16 processes ended at `VERIFY_MISMATCH=0`, and every candidate process
announced the accepted 24×SG16 recurrent-quad workgroup on both devices.

## Cold endpoint gate

Two opposite process-order pairs used fresh servers, 12 unique prompts, at
most 512 generated tokens, one 8K slot, and `cached_tokens=0` throughout.

| Order | Primary delta | Full-decode delta | Wall delta |
| --- | ---: | ---: | ---: |
| control → candidate | -0.059% | +0.008% | -0.100% |
| candidate → control | +0.161% | -0.076% | -0.113% |
| pooled pair medians | **+0.051%** | **-0.034%** | **-0.106%** |

Pooled primary medians were `37.070336` control and `37.089346 tok/s`
candidate. Pooled full-decode medians were `36.681376` and `36.669000 tok/s`.
Pooled TTFT was effectively identical (`-0.006%` candidate delta). The two
pairs cross direction on the primary metric, both full and wall throughput do
not improve, and every delta is noise-level, so DP4A3 is not promoted.

All four endpoint suites passed the fresh-response gate, were cache-zero, and
produced the same 12 complete output SHA-256 values. All four server shutdown
summaries reported `VERIFY_MISMATCH=0`. Both B70s remained normal with no
current-boot Xe fault, reset, timeout, or hang.

The focused source increment is
[`q8-dp4a3-sg24-neutral-20260817.diff.gz.b64`](../patches/q8-dp4a3-sg24-neutral-20260817.diff.gz.b64).
Structured data is in
[`2026-08-17-q8-dp4a3-sg24-neutral.json`](../data/2026-08-17-q8-dp4a3-sg24-neutral.json).
Raw local evidence remains at
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-dp4a3-sg24/`.
