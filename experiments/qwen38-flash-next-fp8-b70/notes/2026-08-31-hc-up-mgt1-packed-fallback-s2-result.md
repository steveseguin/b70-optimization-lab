# Qwen3.8 Flash-Next HC-up M>1 packed-fallback S2 result

Date: 2026-08-31

Status: grouped provider positive; simple packed alternatives rejected at low M;
original S3 not authorized

S2 completed all 120 isolated arms. Every arm was finite and internally
repeatable, and the full receipt, stream, model, runtime, weight, loader, and
process closure passed independent review.

The provider result is mixed:

- contiguous authority: 30/30 exact cells;
- grouped E=1: 30/30 byte-exact cells across five real weights and
  M2/M8/M64/M256/M1024/M4096;
- packed-view linear: 22/30 exact cells;
- packed matmul: 22/30 exact cells.

Packed-view and packed matmul had the same eight cross-provider mismatches:
`00-mlp`, `47-mlp`, and `final` at M2, plus all five sentinels at M8. They are
therefore rejected as universal low-M fallbacks. Their M64 cells were exact,
but that does not erase the low-M negatives.

Grouped was descriptively 57.27%, 59.87%, and 19.82% below the authority
median at M2, M8, and M64. It was 18.25% and 15.02% above authority at M256
and M1024, and essentially neutral at M4096. These fixed-order timings are
directional component evidence, not endpoint throughput or attribution.

The original S2 preregistration stated that unqualified exactness across S2
would authorize its 388-arm S3. Since `all_providers_byte_exact=false`, that
antecedent did not pass and the original S3 must not launch. The prospective
successor is S3g: only authority versus the sole universal packed provider,
grouped E=1, across all 97 real M64 weights. That narrower run requires its own
frozen plan and hashes before execution.

Raw summary SHA-256:
`15994048d275f8252e02ff65702f7b64271dc7dba7c12ce28319a3dd94f67fde`.
The structured result is
`data/20260831-hc-up-mgt1-packed-fallback-s2-result.json`. No source,
endpoint, or protected speed claim changes.
