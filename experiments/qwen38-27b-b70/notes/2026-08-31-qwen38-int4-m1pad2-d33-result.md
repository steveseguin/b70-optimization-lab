# Qwen3.8 INT4 M=1→2 repair D33 result

**Post-run audit correction:** D32's `1` label was the complete M=71 prefill
tensor, not M=1. D33 was therefore based on a mislabeled diagnostic and could
not affect the traced failing operation. This patch is withdrawn.

D33 did not repair the production boundary. Across four fresh processes the
normalized `out_proj` input was bit-identical, but the candidate output still
had four different hashes.

The first patch recursively ran the deterministic M=2 primitive into a padded
destination and then used `result.copy_()` to populate the original M=1
destination. That separate XPU copy could race the asynchronous oneDNN write;
it reintroduced the same class of ordering defect after the deterministic
calculation.

D33r removes the copy and rebinds the caller's tensor to a row-0 view of the
padded destination. This preserves the padded allocation's lifetime and lets
normal stream consumption order the result.
