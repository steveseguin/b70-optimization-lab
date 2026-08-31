# Qwen3.8 Python-ordered INT4 M=1→2 repair D34 result

D34 did not change the failing production boundary. All four processes had the
same normalized `out_proj` input, shape `[71, 6144]`, and four different
`[71, 5120]` output hashes. The first token difference remained at index 60.

This result exposed the diagnostic error in D32: its `rows == 1` branch passed
the complete normalized tensor and therefore ran at M=71. D33, D33r, and D34
all targeted M=1 on that mistaken premise. Their negative outcomes are now
fully explained and their candidate patches are withdrawn.

D35 pads the actual loaded prefill band in Python before the custom operator.
It leaves M=1 decode unchanged.
