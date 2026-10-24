# Same-prefix logits differ despite matching tokens

The fixed retained comparison completed successfully after reading exactly
496,652 bytes: all 248,320 native BF16 logits and three context scalars. Both
engines used the same 118-token conditional prefix (87 original inputs plus
31 matching outputs). Stored position118, input token220 and chosen token16
confirm alignment. No model ran for this analysis.

Both choose token16; top-five membership matches. Overlap is9/10 and30/32
for the larger retained candidate sets. The chosen token's log probability
differs by-0.00152375 (native minus reference). Across the reference's retained
32 candidates, mean absolute difference is0.220871 and maximum0.590961.
These are descriptive log-probability differences, not an invented quality
threshold or a measured task-quality penalty. The reference retains only32
probabilities, so no full-reference KL or distribution equality is claimed.

The native model still rounds ordinary activations and head outputs to BF16.
The reference has F32 tensor outputs but also different reductions and possible
Q8 activation packing inside quantized matmul. The observed difference is not
attributed to one mechanism. Speed work remains held while longer comparisons
and shared-prefix localization establish the remaining fidelity gap.

[Actual comparison](evidence/actual.json), [independent source review](evidence/independent-review.json),
and [remaining dtype appraisal](../precision-appraisal/REMAINING-DTYPES.md).
