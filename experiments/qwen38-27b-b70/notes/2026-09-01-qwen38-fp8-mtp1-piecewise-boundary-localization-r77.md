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

R88 implemented that request-isolated qkvz projection and preserved the c1
oracle, but c2 still passed only 1/2. The layer-0 cache-prompt qkvz and BA
digests are now bitwise exact across c1/c2 on both TP ranks; layer 1 is not.
The same zero-based token-96 difference (`348` versus `2972`) remains. This
moves the boundary past both layer-0 input projections and into the packed
layer-0 GDN prefill/cache transaction or its immediately following output
projection. The next candidate must retain R88 and isolate the pure
multi-request GDN prefill transaction per request.

One preregistered R88 trace label was corrected: R86's selected 28 index rows
came from a packed 59-row projection, not a natural 28-row call. R88's isolated
28-row digest therefore should not equal it; the full index output still
matches the sequential oracle. R88's result is
[`2026-09-01-qwen38-fp8-mtp1-qkvz-request-isolation-r88-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-qkvz-request-isolation-r88-result.json).

R89 added a narrow per-request native GDN prefill/cache path on top of R88, but
the strict result was unchanged: c1 1/1, c2 1/2, with the same cache-prompt
token difference. Its input trace again has exact layer-0 qkvz and BA on both
ranks and differing layer-1 projections. R89 did not include a dispatch record,
so this negative cannot distinguish a guard fallback from a successful
per-request core followed by a batch-dependent norm/output projection. The next
experiment must record dispatch and hash `core_attn_out`, `z`, and the final
GDN-layer output before changing arithmetic again. R89's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-prefill-request-isolation-r89-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-prefill-request-isolation-r89-result.json).

R90 proved R89's dispatch and narrowed the boundary again. All 96 c2 rank-layer
records used `request-isolated`; none silently fell back. At layer 0, the
31-token cache request's raw `core_attn_out` and `z` are bitwise exact between
c1 and c2 on both ranks. Layer 1 is the first differing layer. Together with
R88, this means layer-0 qkvz, BA, native GDN core output, and z all match; the
difference is introduced afterward by `RMSNormGated` and/or the FP8 output
projection. The next candidate must isolate that final stage per request rather
than modify GDN state arithmetic. R90's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-prefill-output-trace-r90-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-prefill-output-trace-r90-result.json).

R91 split `RMSNormGated` and the FP8 `out_proj` together at natural request
boundaries. It is rejected: c1 regressed from 1/1 to 0/1 and c2 remained 1/2.
The cache prompt's c1 and c2 token sequences became identical to R90's known-bad
c2 sequence, with the same token-97 difference (`348` versus `2972`); the index
prompt stayed exact. Thus output-stage request isolation removes the shape
difference but selects the wrong numerical path even for a single request. The
next experiment must separate normalization from projection rather than carry
this combined change forward. R91's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-output-request-isolation-r91-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-output-request-isolation-r91-result.json).

R92 separated those stages. Norm-only isolation reproduced all three R91 token
sequences: c1 regressed to 0/1 and c2 remained 1/2. Projection-only isolation
reproduced all three R90 sequences: c1 stayed exact and c2 remained 1/2. Both
arms used fresh compile caches, zero cached prompt tokens, complete 128-token
outputs, and stopped cleanly with no kernel journal entry. The boundary is
therefore the compiled/fused `RMSNormGated` row-shape path, not request packing
inside FP8 `out_proj`. A repair must preserve the accepted c1 norm arithmetic
while making it batch-invariant; moving the norm outside the compiled graph is
known to select the wrong path. R92's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-output-factorial-r92-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-output-factorial-r92-result.json).

R93 disabled only the compiler's `norm_quant` fusion on the unchanged R90
lineage. The server log proved that only `act_quant` remained enabled, but all
three token sequences were byte-for-byte the R90 sequences: c1 1/1 and c2 1/2.
The fusion is therefore not causal. The remaining boundary is the compiled
`RMSNormGated` reduction arithmetic itself across different total row shapes.
R93's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-norm-quant-fusion-r93-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-norm-quant-fusion-r93-result.json).

R94 replaced every Qwen GDN gated normalization with a fixed one-program-per-row
128-wide Triton kernel. Its bounded operator gate was bitwise row-invariant and
matched the native reference exactly. End to end, the candidate repaired the
failing packed shape from 1/2 to 2/2 exact, while layer-0 `core_attn_out` and
`z` remained bitwise equal across c1/c2 on both ranks. It nevertheless regressed
c1 from 1/1 to 0/1: that output became exactly the prior known-bad R90-c2/R91
sequence, including token 97 changing from `348` to `2972`. R94 is therefore
rejected, but it is a causal positive for the c2 norm boundary. The next
diagnostic must preserve compiled RMSNorm for c1 and decode and use the
row-stable kernel only for packed multi-request prefill; a row-count threshold
may prove that split but cannot become the production discriminator. R94's
result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-row-stable-rmsnorm-r94-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-row-stable-rmsnorm-r94-result.json).

R95 attempted that phase split with a preregistered `num_tokens >= 32`
diagnostic predicate: the fixture has 31-token c1 prefill, 59-token c2 packed
prefill, and 2/4-token decode. The predicate did not survive compiled dynamic
execution as a runtime choice. Because the large profile shape selected the
true branch, the row-stable custom op later executed at all observed shapes,
including 744 rows for c1 prefill and 48 rows for c1 decode. Consequently R95
exactly reproduced R94: c1 0/1, c2 2/2. This rejects Python/SymInt shape
branching as the phase discriminator. The next implementation must carry
runtime request metadata inside one custom op, or reproduce the accepted
compiled c1 arithmetic as the custom op's non-multi-prefill path. R95's result
is
[`2026-09-01-qwen38-fp8-mtp1-gdn-phase-selective-rmsnorm-r95-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-phase-selective-rmsnorm-r95-result.json).

R96 restored the accepted R90 reduction kernel's two-warp launch geometry
inside R94's one-program-per-row kernel. The operator remained bitwise
row-invariant and matched its bounded reference, but the server result was
c1 0/1 and c2 1/2. C1 stayed exactly on R94's known-bad sequence, while c2
returned exactly to R90's sequences. Thus reduction warp geometry controls the
c2 branch, but cannot reproduce accepted c1 alone. The next candidate must
mirror the generated two-kernel structure: two-warp sum reduction followed by
the four-warp flattened gated pointwise stage. R96's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-two-warp-row-stable-r96-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-two-warp-row-stable-r96-result.json).

R97 split the custom norm into the generated implementation's two structural
stages: a two-warp FP32 sum reduction followed by a separate four-warp gated
pointwise kernel. The bounded operator gate passed, but the server result was
again c1 0/1 and c2 2/2, bit-for-bit equal to R94 at both concurrencies. The
temporary store/load boundary and four-warp pointwise stage therefore do not
repair c1. Inspection of R90's retained compiled TTIR found the remaining
concrete difference: Inductor specialized its persistent reduction to
`tensor<8x128>`, processing eight rows per program, while R94-R97 processed one
row per reduction program. The next candidate will reproduce that fixed
eight-row program shape ahead of R97's c2-exact pointwise stage. R97's result
is
[`2026-09-01-qwen38-fp8-mtp1-gdn-two-stage-row-stable-r97-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-two-stage-row-stable-r97-result.json).

R98 reproduced the retained reduction's eight-row-by-128 tensor shape. Its
stricter operator gate proved all eight row slots invariant, proved tail masks
inert, and stayed within `1.53e-5` of the reference. End to end it nevertheless
produced c1 0/1 and c2 1/2: c1 was exactly R94/R96/R97, while c2 was exactly
R90/R96. The compiled artifact comparison revealed three still-unmatched
lowering details. R90 uses one pipeline stage in both kernels, a 1024-element
pointwise block, and explicit libdevice `rsqrt`/`exp`; R98 used two stages, a
256-element pointwise block, and Triton math operations. The next candidate
will match those retained compiled values rather than infer them. R98's result
is
[`2026-09-01-qwen38-fp8-mtp1-gdn-xblock8-row-stable-r98-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-xblock8-row-stable-r98-result.json).

R99 matched every remaining retained R90 lowering detail: one pipeline stage
for both kernels, an eight-row-by-128 two-warp reduction, a 1024-element
four-warp pointwise launch, and libdevice `rsqrt`/`exp`. The operator gate was
bitwise row-slot invariant and matched the bounded reference exactly. End to
end, all three complete token streams became byte-for-byte R90 again: c1
recovered to 1/1, while c2 remained 1/2 with the cache request's same token-97
`348` to `2972` divergence and the index request exact. Layer-0 raw GDN core
output and `z` remained exact across c1/c2 on both ranks. This closes the
source-level lowering search: R99 is the c1-exact arm and R97 is the c2-exact
arm. The next diagnostic must select between them using live request metadata
inside the opaque custom-op implementation; R95 already proved that a Python
shape branch outside that boundary freezes during compilation. R99's result is
[`2026-09-01-qwen38-fp8-mtp1-gdn-retained-lowering-r99-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-retained-lowering-r99-result.json).
