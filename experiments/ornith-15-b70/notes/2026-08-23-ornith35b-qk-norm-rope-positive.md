# Ornith 1.5 35B-A3B: full-attention Q/K RMSNorm, IMRoPE, and K-cache fusion

Date: 2026-08-23 EDT

Status: **accepted as the eleventh target-only optimization**

## Why this Qwen transfer was tested

Ornith 1.5 is a retrained, Qwen-derived architecture (`qwen35moe` in the
runtime). After the Qwen-derived GDN state-I/O transfer succeeded, the next
accepted Qwen TP1 lever was the one-token full-attention Q/K normalization and
rotary-position chain. Ornith has 10 full-attention layers with the same useful
shape: 16 Q heads and 2 KV heads, 256 dimensions per head, RMS normalization,
and interleaved multi-dimensional RoPE.

The default-off `GGML_SYCL_FUSED_ORNITH_QK_NORM_ROPE=1` path combines each
layer's Q/K RMS reductions, scale, IMRoPE, and K conversion/write into one
kernel. Q remains FP32 for flash attention and K is written directly to its
F16 cache. The matcher fails closed on tensor shapes, op parameters, named
normalization weights, layer identity, sole-consumer chains, cache type, and
storage non-overlap. A separate poison door verifies matcher activation.

This replaces five operations with one in each of 10 full-attention layers,
removing 40 launches per decoded token. The complete eleven-feature stack
removes 700 launches per decoded token.

## Matched performance

All promoted runs used one B70, graph off, F16 KV, the same maintained final
binary, and the preceding ten-feature stack in both arms.

| Protocol | Controls | Candidates | Mean change |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7`, A/B/B/A | `130.338305`, `130.456676` | `133.521063`, `133.326313` | **+2.32%** |
| fresh 12-prompt server suite, A/B/B/A | `126.095292`, `126.845325` | `129.754844`, `127.909546` | **+1.87%** |

Both candidates exceeded both controls in both protocols. Every server
process used 12 unique prompts once, reported `cached_tokens=0`, and passed
the tokens 1-100 and final-response gates. The promoted serving number is the
directly measured candidate mean, **128.832195 tok/s**; it is not extrapolated
from the preceding package number.

Candidate engine runs recorded 8,970 hits each and server runs recorded
61,320 hits each, confirming that the timed path executed throughout.

## Correctness and build identity

- Same-maintained-binary forced 128-token control and candidate transcripts
  were byte-identical at
  `d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`.
- The candidate recorded exactly 1,270 hits: 10 full-attention layers across
  127 decoded graph evaluations.
- The short repeat-8x, arithmetic (`4183`), exact-copy, and JSON-schema
  canaries all passed.
- An isolated scratch build produced a different transcript hash because its
  AOT/build configuration differed. Its positive timing established only that
  the mechanism was worth transferring. It is excluded from promoted
  performance and exactness evidence; all values above come from the
  maintained oracle-matching build.
- The complete patch applies cleanly to pinned llama.cpp base
  `9fee29e9435f865ec0b811a783a6471a136d9317` and passes `git diff --check`.

## Artifacts

The incremental patch is
`../patches/llamacpp-ornith15-qk-norm-rope-positive-20260823.patch`. The
package's complete eleven-feature patch is
`../../../patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-eleven-feature-stack-qk-norm-rope-20260823.patch`.
Structured summary, exactness, raw engine/server rows, canaries, and logs are
under `../data/2026-08-23-ornith35b-qk-norm-rope-*`.
