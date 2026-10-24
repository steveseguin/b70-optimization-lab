# Upstream precision options after the shared-prefix replay

This is source appraisal, not implementation or evidence of the active replay's
result. The existing numerical mismatch remains a fidelity failure. A successful
reproduction of native220 at the shared157-ID prefix would make the captured
BF16 head ranking relevant to that failure; it would not resolve it.

First inspect both conflicting tokens in the full BF16 ranking. A tie or coarse
margin makes the already-proposed FP32-before-BF16 dual-store diagnostic useful.
That diagnostic preserves the old BF16 selector and can distinguish final store
rounding from its input/accumulation. If the pre-store ordering still favors220,
changing only the final destination cannot explain CPU264. Conversely a recovered
264 ordering isolates a sufficient last-store cause for this one decision, not
all earlier arithmetic or broader output fidelity.

The smallest upstream island is the final HC mixer. Actual5926 Builder::hc uses
`streams → final.norm → final.low → final.act → final.gate → final.mix`, then
`output.weight → logits`. The mixer reads streams and uses distinct final buffers;
it does not overwrite recurrent state or streams. The reference qwen4exp final
mixer explicitly has no separate output norm: grouped RMSNorm and gamma, down
linear, scale by1/4 and SiLU, up linear, sigmoid-gated normalized streams, ordered
four-stream sum and scale by1/4 all produce F32 tensors. Native ordinary buffers
and Args::put round those intermediate results to BF16. Its mix computes sigmoid
and products in float, then writes the mean through the BF16 accessor.

An additive F32 final-mixer diagnostic could widen these few destinations and
their consumers, preserving explicit arithmetic order and selected weight bytes.
It must supply real typed GEMV input/output facades and non-GEMV accessors; changing
only buffer dtype would make existing uint16 pointers interpret F32 incorrectly.
Explicit intermediate Args::bf casts must be reviewed separately. Its source input
would still be BF16 final streams. It is therefore a bounded attribution island,
not a claim to restore the reference's full F32 residual path. Its allocation and
transfer deltas must be derived from the actual plan before any build; no memory
fit is inferred here. Target-only avoids silently changing MTP hidden-state
contracts while diagnosing the target.

If the final mixer does not explain the decision, use aligned, same-prefix
checkpoints to locate the first differing semantic boundary before broad rewrites:
embedding/PLE lookup, HC residual and norm, attention/GDN outputs, router scores
and selected expert IDs, and expert outputs. Ordinary BF16 stores here are extra
rounding relative to the reference F32 graph, unlike the explicitly admitted BF16
KV cache. F32 recurrence fixes one boundary, not these others. A full correction
would require typed activation bindings, transfer and rollback lengths, both
rank boundaries, and fresh device/capture accounting; it is not an enum switch.

Finally, F32 storage alone is not an exact CPU arithmetic oracle. The pinned CPU
quantized GEMV can pack F32 inputs into its vec-dot format (for example Q6_K uses
Q8_K), and its reduction/math implementations differ from the custom SG32 tree
and detmath functions. A useful diagnostic must distinguish storage rounding,
input quantization and reduction/math order rather than attribute every mismatch
to the word BF16. No tolerance, new speed work, GPU/compiler/model invocation,
or quality promotion follows from this appraisal.
