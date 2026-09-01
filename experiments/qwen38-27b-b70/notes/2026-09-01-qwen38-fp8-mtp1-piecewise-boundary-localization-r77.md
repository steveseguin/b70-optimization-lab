# Qwen3.8 FP8 TP2 MTP1 R74-R77: layer-1 GDN boundary

The first meaningful c1-versus-c2 difference is the output of
`gdn_attention_core_xpu` in decoder layer 1. The embedding and layer-0 FP8/BA
projections match, the layer-0 GDN result matches, and the layer-1 `z` input
matches. The layer-1 `core_attn_out` does not.

R77 fixed the earlier scalar-hash diagnostic and logged the packed token vector
`[3833, 14542, 271, 9923]`. That proves rows 0-1 belong to the failing
`cache-c000` request and rows 2-3 to the exact `index-c001` request. It also
corrects the scheduler-based row assumptions in R75/R76. Comparing R74 c1
backbone call 5 row 0 with R77 c2 call 5 row 0 gives the boundary above.

One apparent earlier difference is intentionally excluded: piece 0 output slot
1 is an uninitialized `torch.empty_like` scratch tensor before the custom GDN
op. Its changing bytes are not model arithmetic. The initialized projection
outputs are byte-identical.

The original R74 preregistration cited an older August oracle. Final analysis
uses the explicit R72-derived oracle in
[`2026-09-01-qwen38-fp8-mtp1-c2-r72-oracle.json`](../data/2026-09-01-qwen38-fp8-mtp1-c2-r72-oracle.json).
The observed c2 failure is unchanged: both outputs are complete, cached-token
counts are zero, `index-c001` is exact, and `cache-c000` first differs at token
96 (`348` expected, `2972` observed).

R78 attempted to split convolution from delta-rule arithmetic using the old R50
serial controls. The conv arm failed closed before producing output because
that diagnostic supports one speculative request only. A narrow multi-request
extension is required before the factorial can answer the question.

R79 reached its new two-request path, then failed closed when the scheduler
narrowed to a follow-up one-request shape. R80 separated those dispatch modes
and completed the preregistered factorial. Conv-only and delta-only both
returned two complete 128-token outputs with zero cached tokens and no new GPU
fault, but each matched only 1/2 oracle outputs. Both arms produced the same
token sequences. Neither isolated stage is therefore sufficient; R81 tests the
complete conv-plus-delta transaction without changing production defaults.

R81 also matched only 1/2 oracle outputs. Both serial stages executed on both
TP ranks, yet its two token sequences were identical to both isolated R80 arms.
The combined transaction as implemented is therefore not a repair. R82 traces
the actual speculative request boundaries, packed-token indices, state-cache
columns, and accepted counts before any further mapping change.

This is diagnostic evidence, not a speed or quality promotion. The current boot
contains an earlier GPU reset, so any eventual repair still requires a clean-
boot strict replay. Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-localization-r77-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-localization-r77-result.json).
