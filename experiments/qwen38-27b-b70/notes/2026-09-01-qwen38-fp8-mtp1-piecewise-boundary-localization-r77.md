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

R100 moved the branch to live `GDNAttentionMetadata` inside the opaque custom
op and independently preserved the R99 single-request and R97 multi-request
arms. Its operator gate passed, but the server rejected during vLLM's
pre-serving `profile_run`: that intentional initialization phase has
`attn_metadata=None`, so R100's preregistered missing-metadata fail-closed rule
was overly broad. No output request ran. The narrow correction is to recognize
only that explicit profile state and run the R99 arm there; malformed live
metadata must still fail closed, and inference must still select from live
request counts. R100's startup rejection is
[`2026-09-01-qwen38-fp8-mtp1-gdn-runtime-metadata-selector-r100-result.json`](../data/2026-09-01-qwen38-fp8-mtp1-gdn-runtime-metadata-selector-r100-result.json).

R101 recognized only vLLM's explicit metadata-free profile phase and used R99
there, while retaining live metadata selection for inference. It is the first
end-to-end pass in this localization series: c1 was 1/1 exact and c2 was 2/2
exact against complete pinned token streams, with zero cached prompt tokens.
Distinct server markers proved the profile fallback, live single-request R99
arm, and live multi-request R97 arm all executed. Compiled metadata also
confirmed the intended 8-row/1024/libdevice single arm and
1-row/256/Triton-math multi arm. Layer-0 raw GDN core output and `z` remained
exact across c1/c2 on both ranks, and the kernel journal was clean. This is a
causal correctness repair, not yet a public performance result: first-use
Triton and EAGLE JIT occurred during the measured requests, only two prompt
rows were used, and this boot contains an earlier GPU reset. The next gate is a
non-tracing, fully warmed, varied-prompt determinism qualification on a clean
boot. R101's result is
[`2026-09-02-qwen38-fp8-mtp1-gdn-profile-aware-selector-r101-result.json`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-profile-aware-selector-r101-result.json).

R102 rejected that apparent repair under repetition. After distinct cache-zero
warmups exercised both selector arms, c1 remained exact in 2/2 attempts, but
c2 matched only 3/4 complete outputs. A bounded ten-repeat c2 probe then passed
only 7/10 batches. Every miss was the 31-token `cache-c000` request and every
miss produced the same known alternate stream (`348` to `2972` at zero-based
token 96); `index-c001` stayed exact 10/10. The server logged the intended
live-multi R97 arm and the kernel journal was clean, so this is not selector
misclassification or prompt caching. R97's earlier single 2/2 observation was
underpowered and R101 is not a robust causal repair. Per the preregistered stop
rule, the public-shape strict speed phase was not run. The next diagnostic must
correlate each output with the live 31/28-token prefill ordering before another
arithmetic change. See the
[`R102 result`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-profile-aware-selector-r102-result.json).

R103 attempted to correlate that binary branch with the live 31/28-token
prefill order. The intermittent alternate stream reproduced in 4/10 c2
batches, but the inherited R90 tracer intentionally de-duplicates by
`(layer_name, num_prefills)` and emitted only one of the ten required layer-0
rank-0 c2 records. That first order was `[31,28]` and its batch failed; the
remaining nine orders are unknowable, so the correlation is inconclusive.
The first startup was also stopped before requests after the inherited 9 GiB
cgroup began heavy reclaim; the established 12/16 GiB MTP bounds started
normally without a reset. The next observation-only overlay must log every
pure-prefill invocation with a counter. See the
[`R103 result`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-prefill-order-correlation-r103-result.json).

R104 replaced only the trace seen-set with an invocation counter. The overlay
passed its source gate and emitted 960 records for ten batches, but one batch
entered as a staggered/mixed scheduler shape rather than a pure c2 prefill, so
only nine layer-0 c2 records per rank were eligible. R105 froze that checkpoint
and repeated on the warmed server. Its first batch again began as a one-request
31-token prefill and is excluded from the order partition. Repeats 2-10 aligned
one-to-one on both ranks and give a perfect split: all seven `[31,28]`
cache-first batches produced the same known bad stream, while both `[28,31]`
cache-second batches matched the sequential oracle. The index request stayed
exact 10/10 and every request was complete and cache-zero. This establishes
live packed-prefill order as the discriminator; prompt length is only how the
frozen diagnostic identifies each request and must not become production
policy. The next candidate should use live request boundaries to isolate the
post-core output projection per request atop R101, leaving the R99/R97 selector
unchanged. See the [`R104 trace result`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-prefill-order-trace-all-r104-result.json)
and [`R105 aligned result`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-prefill-order-aligned-r105-result.json).

R106 intended to isolate only the final FP8 GDN `out_proj` at live
pure-prefill request boundaries, but its treatment was inert. The checked-in
zero-context patch had an incorrect first-hunk line count: GNU `patch` applied
the helper-registration hunk, treated the call-site hunk as trailing garbage,
and still returned success. The image and installed-file hashes consequently
matched the flawed expected source while live `forward_xpu` retained its direct
`self.out_proj` call. R107 exposed this when its mandatory trace file remained
absent despite the trace environment being present; installed-source
inspection confirmed that no custom-op call site existed.

R106's c1/c2 and request-order observations remain a valid reproduction of the
inherited R101/R104 behavior, but they provide **no evidence** for or against
projection isolation. The earlier rejection of packed `out_proj` shape is
withdrawn. A repeat must prove both that the call occurs inside `forward_xpu`
and that a runtime execution marker is emitted before any output result is
interpreted. See the corrected
[`R106 result`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-projection-isolation-r106-result.json)
and the
[`R107 invalidation`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-postnorm-projection-trace-r107-result.json).

R108 repeated the intended treatment from the frozen R104 image with two
independent execution proofs. Its AST validator requires the custom-op call
inside `QwenGatedDeltaNetAttention.forward_xpu` (and rejects the inert R106
source), while the runtime gate recorded 2,496 exact trace rows spanning both
TP ranks, all 48 GDN layers, and both `single-request-control` and
`split-per-request` execution. The valid result rejects projection isolation:
c1 remained exact 3/3, but c2 passed only 1/20 batches (21/40 streams). The
cache request produced the known alternate stream 19/20 times; the index
request stayed exact 20/20. Every request was complete and cache-zero.

The new boundary trace is decisive. On both ranks, the normalized and isolated
projected rows for both prompts are invariant across the two packed orders at
GDN layer 0. Starting at GDN layer 1, both digests vary by order for all 47
remaining GDN layers and both prompts (94/96 layer-prompt pairs). The branch is
therefore introduced after layer-0 `out_proj` and before the layer-1 post-core
normalization boundary, not by request packing inside `out_proj`. The next
single-variable diagnostic should exercise the already-available packed serial
outer RMSNorm/residual path; it must pass repeated c2 output identity before
any performance measurement. See the
[`R108 result`](../data/2026-09-02-qwen38-fp8-mtp1-gdn-projection-isolation-trace-r108-result.json).

R109 tested the existing packed-serial Qwen/Gemma outer RMSNorm path as the
only new variable, using a fresh compile cache and retaining R108's execution
trace. It is a clean negative: c1 remained exact 3/3, while all twenty c2
batches matched only the index request. The cache request produced the same
known alternate stream 20/20 times. The trace boundary was unchanged on both
ranks: layer 0 remained invariant across packed order and 94/96 later
layer-prompt pairs varied. This rules out that existing outer RMSNorm gate as a
sufficient repair. The next diagnostic must observe the decoder-layer contract
directly—layer-0 returned hidden/residual and layer-1 received hidden—before
another arithmetic change. See the
[`R109 result`](../data/2026-09-02-qwen38-fp8-mtp1-outer-rmsnorm-serial-r109-result.json).

R110 attempted to hash the decoder-layer contract at eight layer-0/layer-1
boundaries, but the synchronous observer failed its mandatory non-perturbation
gate. The patch and live call sites were proven this time, both ranks emitted
all expected stages, and the server logged the intended R99 single-request
selector arm. Nevertheless, the first complete cache-zero c1 output was the
known alternate token stream instead of the frozen c1 oracle (0/1 exact).
Because each trace call copied device data to the CPU and wrote a file before
continuing, the observer changed execution scheduling. C2 was not run and none
of R110's tensor digests may be interpreted. The replacement must defer all
device synchronization until a later request and must first reproduce the c1
oracle exactly. See the
[`R110 result`](../data/2026-09-02-qwen38-fp8-mtp1-decoder-boundary-trace-r110-result.json).
