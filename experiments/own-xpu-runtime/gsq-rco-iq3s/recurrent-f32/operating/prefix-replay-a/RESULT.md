# Shared-prefix replay isolates an upstream numerical difference

The unchanged corrected5926 binary replayed exactly157 input IDs (87 original
prompt IDs plus70 matching generated IDs), then emitted one token. It reproduced
native220, while the independently retained CPU reference chooses264 at the
same conditional prefix. Saved counters confirm consumed position157, last
input303 and selected220. This was one fresh target-only request, with no MTP,
prompt-cache reuse, model rebuild, speed claim or broad quality qualification.

Independent closed readback passed. It streamed the final rank1 bundle exactly
once (125,598,668 bytes), checked its full seal and every range, and extracted
496,652 bytes for all248,320 BF16 logits plus three context scalars. Other
bundles were not requalified. Both device contacts, normal owner exit, physical
drain, protected vision and unchanged fault baseline passed. RESET, final DUMP
and FINISH acknowledged the complete640,127,112-byte two-group capture budget.

The two relevant native logits are **21.0 for220** and **20.625 for264**, a gap
of0.375. They are not tied. Finite round-to-nearest BF16 is monotone, so the final
store cannot reverse their strict pre-round ordering. A head-only pre-round
side channel would not explain this disagreement and is deferred. Differences
in earlier BF16 activation boundaries, CPU activation packing, reductions or
nonlinear arithmetic remain possible; this result does not identify which one
caused it or quantify task-quality loss.

The reference's top-two log-probability gap is0.0616703 in the opposite order.
Top-five and top-ten membership matches;31 of32 retained candidates overlap.
Across those32, mean absolute log-probability difference is0.157720 and maximum
0.602597. These are descriptive measurements, not an acceptance tolerance.
The reference's full distribution is unavailable, so no full-distribution KL
or numerical equality is claimed.

The owner requested wrap-up after the replay. Experiments and recurring coaching
are stopped; no additional model run, build or quality-qualified publication is
planned. If resumed, inspect avoidable earlier precision reductions under an
explicit reference contract, with fixed same-prefix/task checks. Exact
free-running CPU/GPU token identity alone is not a universal quality metric.
The final HC mixer is a bounded candidate for attribution; changing it alone
would still consume previously rounded BF16 streams.

[Closed logit review](evidence/closed-logit-review.json),
[source review](evidence/independent-audit-source-review.json),
[retained metadata copies](evidence/actual-copy-map.json),
[prior failed comparison](../longer-a/RESULT.md),
and [upstream source options](../../reference-longer-plan/UPSTREAM-PRECISION-OPTIONS.md).
