# Qwen3.8 Flash-Next FP8 A25 fresh inner-trace result

Date: 2026-08-30
Status: diagnostic trace positive; lifecycle negative; no promotion

## Outcome

A25 answered the frozen diagnostic question. Its rank-0 trace and A24 each
contain exactly 64 ordered records and 171 tensor tuples. The first 23 tuples
match exactly. The first difference is record 13,
`layer_1_attn_output.attn_out`, a BF16 `[64, 2560]` tensor:

- A24: `1c3cd27e11c3927cf6663eb01345f06a03938423a1def150c0777307a34e0352`;
- A25: `9aa9a30aaad4647bdc956761b54973a6cb35acbe64dedb4f4f6d46e4afa0ef9a`.

Everything before that boundary is exact across the fresh starts: layer input,
PLE row lookup, dequantization, projections, gate, convolution input/output,
PLE output, PLE addition, and the layer-1 hyperconnection mix. Zero-based
layer 1 uses GatedDeltaNet linear attention. PLE is therefore not the first
cross-start divergence; the next reliability trace belongs inside GDN, from
its projections and cache-state inputs through recurrent output, norm, and
output projection.

## Battery

The inherited quality boundary passed: six of seven exact semantic cases, the
known code-case exception, the repeat suite, and the exact-4K needle. Three
short rows retained one output hash at `5.419691 / 5.408572 / 5.551166 tok/s`
(median `5.419691`). The two 4K rows completed at `5.312945 / 5.273093 tok/s`
but produced two distinct non-authority hashes, so the final assertion failed
closed. No speed or reliability result is promoted. The protected
`5.515783 tok/s` target-only median and `20.727 tok/s` MTP4 result remain
unchanged.

## Lifecycle defect and evidence scope

The frozen supervisor did not own this server. During read-only wrapper
inspection, the launch wrapper's advertised source-only mode unexpectedly
executed the derived A25 launcher. The resulting server still matched the
frozen model, source, placement, cache, graph, MTP, prompt, and trace identity
and was the boot's sole full-model load. The frozen client correctly refused
an absent supervisor. A diagnostic client was then run with only the
supervisor PID/deadline admission block removed; its derived SHA-256 was
`c0ffb1110564180173a13d3ec711be336eb47309cb3bf6847005b8bb4a2ddcb5`.
All server identity checks, requests, hashes, trace operations, quality gates,
and assertions remained intact.

That makes the trace scientifically useful but the run procedurally ineligible
for qualification. The server was terminated by its validated process group,
the endpoint disappeared, all four cards remained discoverable, and host RAM
and swap recovered. The kernel window contained corrected Samsung NVMe PCIe
receive events but no reset, OOM, hung task, or device loss.

Raw evidence is under
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1-attempt25`.
The trace SHA-256 is
`e595f32348c86972a586bf989a72e0a7301513370d40be4a8bf328207ee330c5`;
the ordered comparison SHA-256 is
`a746430610a30d92f787a80f9175db9a1476b2433cdca28a027203058569bae4`.

## Next action

Add a default-off, report-only layer-1 GDN trace that records projected QKVZ/BA,
selected convolution and recurrent-state inputs, post-convolution Q/K/V/gate,
recurrent output/final state, gated norm output, and row-parallel projection
output. First use fixed-input component gates. Only a later fresh-start pair
may attribute or repair the reliability defect. Async UVA PLE and the already
exact MoE/collective component candidates remain valid speed work because this
trace exonerates their arithmetic as the first divergence.
