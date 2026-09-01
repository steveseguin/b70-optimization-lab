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
counts are zero, `index-c001` is exact, and `cache-c000` first differs at
zero-based token index 96 (human token 97; `348` expected, `2972` observed).

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

R82 confirmed the first-call mapping on both TP ranks. The c2 speculative
batch is request-major: token rows `[0,1]` and `[2,3]`, query starts
`[0,2,4]`, state rows `[[7,6],[8,9]]`, and accepted counts `[1,1]`. The c1
control was exact, while c2 remained 1/2 exact and retained the known first
difference at zero-based output index 96. R80's row slicing and accepted-count-minus-one
selection are therefore consistent with the scheduler metadata at the start
of decoding; R83 must observe later decode steps where the failure develops
rather than make another ungrounded mapping change.

R83 extended that trace through all 72 c2 verifier steps: 3,456 calls per TP
rank (48 GDN layers per step), with zero rank payload mismatches. Every call
kept query starts `[0,2,4]`, token rows `[0,1,2,3]`, and four distinct state
slots; each layer's state-slot pattern remained fixed across the decode. The
known zero-based output-index-96 divergence coincides with step 54, where the failing
request has accepted count 1 and the exact request has accepted count 2, but
there is no malformed or evolving scheduler mapping. The next discriminator is
therefore direct multi-request-versus-isolated operator/state equivalence.

R84 supplied that operator discriminator at the real TP2 GDN dimensions. For
identical inputs and cache contents, native packed c2 was bitwise identical to
two isolated c1 transactions in all 48 cases: `z`, core output, convolution
cache, and SSM cache. The R80 ordinary one-token replay kept convolution exact
but differed slightly in the production float16 SSM cases (core max absolute
error 0.0001221; state 0.00390625). This rules out intrinsic native packed-c2
operator arithmetic and explains why R80 was not a true exact repair. The
remaining boundary is the layer-1 cache content arriving from prefill/state
publication before the first verifier step.

R85 moved that boundary one stage earlier. At layer 0, the target request's
projected speculative qkvz and ba rows are bitwise identical between c1 and c2
on both TP ranks, while both its selected convolution and FP32 SSM source-cache
rows already differ. From layer 1 onward that state difference has propagated
into the projected inputs. The next split is therefore layer-0 prefill
projection versus the XPU GDN prefill kernel, not speculative arithmetic.

This is diagnostic evidence, not a speed or quality promotion. The current boot
contains an earlier GPU reset, so any eventual repair still requires a clean-
boot strict replay. Structured evidence is in
[`2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-localization-r77-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-piecewise-boundary-localization-r77-result.json).
R82's structured result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-metadata-trace-r82-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-metadata-trace-r82-result.json).
R83's full step-level trace summary is
[`2026-09-01-qwen38-fp8-mtp1-gdn-evolving-metadata-r83-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-evolving-metadata-r83-result.json).
R84's operator-equivalence result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-c2-isolation-r84-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-c2-isolation-r84-result.json).
R85's exact state-input result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-state-input-r85-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-state-input-r85-result.json).

R86 resolved the prefill side of that boundary. The c2 prefill scheduler orders
the 28-token `index-c001` request before the 31-token `cache-c000` request, so
the correct prefill comparison is c1 request 0 against c2 request 1. At layer
0, the existing fixed-256 BA projection is bitwise exact for `cache-c000` on
both TP ranks, while its FP8 qkvz projection differs. The difference therefore
precedes both GDN prefill kernels. A fixed-row-shape qkvz projection is the next
repair candidate. R86's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-prefill-input-r86-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-prefill-input-r86-result.json).

R87 rejected the first repair candidate. Padding every qkvz prefill projection
to 256 rows made layer-0 `cache-c000` qkvz and BA bytes exact between c1 and c2
on both TP ranks. It did not restore the oracle: c1 fell from 1/1 to 0/1, c2
remained 1/2, and the cache prompt produced the same complete 128-token sequence
in both shapes but retained the known wrong token at zero-based index 96
(`2972` instead of `348`). The fixed shape therefore forced both executions
onto the previously wrong c2 numerical path. The layer-0 rank-0 qkvz digest
confirms this directly: R86 natural c1 begins `8624f67d...`, while both R86
natural c2 and R87 fixed-256 begin `c171b53e...`. Batch invariance alone is not
a quality result.

R87 also showed that prefill scheduler order is not stable enough to identify a
request by position: unlike R86, it placed the 31-token cache request first.
Future trace comparisons must match a prompt by its token count or an explicit
request identity. The next candidate is request-isolated qkvz projection at
each request's natural row count (31 and 28 in this fixture), not another padded
shape. R87's rejected result is
[`2026-09-01-qwen38-fp8-mtp1-qkvz-fixed-shape-r87-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-qkvz-fixed-shape-r87-result.json).
