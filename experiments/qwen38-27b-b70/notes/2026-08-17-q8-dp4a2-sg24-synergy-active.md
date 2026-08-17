# Qwen3.8 27B Q8 TP2 DP4A2 × SG24 synergy

Date: 2026-08-17

Status: **accepted and promoted** on the reference ASRock host

## Decision

Promote the retained two-independent-accumulator DP4A row body (`DP4A2`) on
top of the already accepted Qwen3.8 recurrent-quad SG16 and SG24 geometry.
Keep the previous one-chain SG24 build as the compile-time fallback.

This does not invalidate the earlier Qwen3.8 DP4A2 result. Under the old SG8
recurrent-quad geometry, DP4A2 was quality-exact but did not produce a
repeatable endpoint gain. SG24 changes that hot quad from 128 to 384 work
items, altering occupancy and register-pressure balance. The combined
DP4A2×SG24 result is therefore a materially different experiment, and both
opposite-order endpoint pairs favored it.

## Fixed identity

- model: `ggml-org/Qwen3.8-27B-GGUF`, revision
  `0669b98607d47046c7c2b3f801011d54a08cfccf`
- file: `Qwen3.8-27B-Q8_0.gguf`, 28,595,763,552 bytes
- SHA-256:
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- base source: mndodd `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`
- control: one-chain DP4A + SG16 + SG24
- candidate: DP4A2 + SG16 + SG24
- selector/devices: `level_zero:1,0`, `SYCL0/SYCL1`, equal `1/1` TP2
- Q8 target, F16 KV, FlashAttention, `b1024/ub256`, reasoning off
- target-only: no MTP, DFlash, draft model, speculation, or response reuse

The DP4A2 body uses two independent integer DP4A chains within each reordered
Q8 block and combines the integer partial sums before the same per-block FP32
scale/accumulation boundary. It changes scheduling/ILP, not the represented Q8
weights or floating-point reduction boundary.

## Direct fresh-process gate

The first balanced sequence was `A-B-B-A,B-A-A-B`; a second run put every arm
in the complementary process positions. Each process ran `p64/n256/r3`.

| Aggregate | One-chain SG24 | DP4A2 SG24 | Delta |
| --- | ---: | ---: | ---: |
| First 8, mean | 37.314317 | 37.544037 | +0.616% |
| Complementary 8, mean | 37.258893 | 37.727908 | +1.259% |
| All 16, mean | 37.286605 | 37.635972 | **+0.937%** |
| All 16, median | 37.364352 | 37.729693 | **+0.978%** |

Every run ended at `VERIFY_MISMATCH=0`.

## Cold realistic endpoint gate

Four fresh servers formed two opposite process-order pairs. Each suite used 12
unique prompts, at most 512 generated tokens, `cache_prompt=false`, one 8K
slot, and `cached_tokens=0` for every request.

| Order | One-chain SG24 | DP4A2 SG24 | Primary delta | Full-decode delta |
| --- | ---: | ---: | ---: | ---: |
| control → candidate | 36.794593 | 37.120351 | +0.885% | +1.181% |
| candidate → control | 36.878483 | 37.142719 | +0.717% | +0.724% |
| pooled pair medians | 36.836538 | 37.131535 | **+0.801%** | **+0.952%** |

The pooled candidate first-100 helper converts to `36.760220 tok/s` under the
99-interval conventional accounting. That is slightly below the older
reasoning-enabled absolute headline (`36.772932 tok/s`), so the headline is
not changed. Promotion rests on the matched opposite-order deltas. The pooled
full-output after-TTFT median was `36.900803 tok/s` for DP4A2 SG24 versus
`36.552765 tok/s` for one-chain SG24.

All four endpoint suites passed the fresh-response policy. Their 12 complete
output SHA-256 values matched exactly across both binaries and both process
orders.

## Independent quality gate

The promoted candidate then passed:

- 7/7 exact semantic canaries;
- 8/8 deterministic repeat runs with one unique output hash;
- the actual 3,829-token long-context needle;
- exact comparison with the retained Qwen3.8 Q8 semantic baseline;
- `VERIFY_MISMATCH=0` on clean server shutdown.

There was no current-boot Xe fault, reset, timeout, or hang, and both B70s
remained in normal state.

## Reproduction and provenance

Restore the public mndodd base, apply the checksum-gated full DP4A2 artifact,
then apply the Qwen3.8 SG16 and SG24 increments. A clean reconstruction matched
all 20 modified files in the tested source byte-for-byte. Exact instructions,
hashes, build flags, and runtime doors are in the
[standalone reproduction](../../../repro/qwen38-27b-q8-tp2-asrock-b70/README.md)
and [patch packet](../../../patches/qwen38-27b-q8-tp2-asrock-b70/README.md).

Structured metrics are in
[`2026-08-17-q8-dp4a2-sg24-accepted.json`](../data/2026-08-17-q8-dp4a2-sg24-accepted.json).
Large raw evidence remains at
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260817-dp4a2-sg24/`.
