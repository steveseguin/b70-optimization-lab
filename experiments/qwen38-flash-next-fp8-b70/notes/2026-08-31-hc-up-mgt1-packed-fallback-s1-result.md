# Qwen3.8 Flash-Next HC-up M>1 packed-fallback S1 result

Date: 2026-08-31

Status: two-repeat exact component pass; no source or endpoint promotion

S1 attempt 2 completed twice. All 16 isolated arms were finite, repeatable,
non-mutating, and byte-exact to their contiguous-weight authority. This
includes packed-view linear, packed matmul, and grouped E=1 at both M2 and the
production chunked-prefill shape M64 on the real layer-0 attention HC-up
weight.

Grouped was directionally fastest in both fixed-order screens:

- M2: `13.976 / 14.998 us` versus authority `35.511 / 38.284 us`, reductions
  of `60.64 / 60.82%`;
- M64: `21.305 / 21.534 us` versus authority `40.074 / 37.468 us`, reductions
  of `46.84 / 42.53%`.

Those timings are descriptive, not an attributed speed claim. Provider order
was fixed and the scope contains one real weight. The earlier synthetic M2
packed-view mismatch remains a valid bounded negative for that synthetic
input, but it does not reproduce on this real-weight S1 scope.

Raw summaries:

- r1 SHA-256 `dde7b9aaeda8bb564d64f2259aeb3e825ad01416afea506098ef49e25d3f6a37`;
- r2 SHA-256 `38cf8bb5af172aacbf632f943136d6a14ea83182f7d70a2f6ba642249527e969`.

The structured result is
`data/20260831-hc-up-mgt1-packed-fallback-s1-result.json`. S1 authorizes only
the frozen S2 five-sentinel/wide-M correctness screen. The source integration
continues to reject non-M1 inputs until broader exactness and dispatch policy
are accepted. Protected endpoint results are unchanged.
