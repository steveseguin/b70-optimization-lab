Follow-up: this now reproduces in the actual native speculative operators on
an Intel Arc Pro B70, beyond the earlier CPU shape-stub check.

On kernels `efc85bc8a0eb3076c861b2e6cb1e1731a93905d5`, torch `2.11.0+xpu`,
oneAPI 2025.3, both FP16 and BF16 pass the stock full-width3 numerical/state
control, then reject active width2 with a width3 state-index cache at the
reported host assertion. No guard was bypassed to launch the unsafe stock path.

The three-file candidate from the original packet passes a 3→2→3 sequence
in both dtypes, including previous accepted counts [3,2] on the shrinking
step and shuffled global token indices. Convolution state, z, and untouched
SSM slots match exactly. Worst output relative-L2 error versus the adapted
Torch reference: 0.000024 FP16 / 0.002170 BF16; written SSM also passes.

These are isolated builds of the exact two speculative entrypoints and kernel
headers, with an explicit queue/registration adapter; unrelated prefill/TLA
code is omitted. No installed-vLLM, scheduler, model, graph, mixed-batch, or
native ragged qualification is claimed. The harness rejects ragged offsets,
which is not a native implementation fix. The candidate remains a starting
point for a complete contract fix, not a production promotion.

All four cards passed bounded pre/post health checks with a clean journal.
The packet retains an initial loader failure (2026 compiler/libsycl9 mismatch),
the matching 2025 rebuild commands/library hashes, exact source/test hashes,
reference adaptations, raw logs and structured results:

https://github.com/steveseguin/b70-optimization-lab/tree/main/experiments/qwen38-27b-b70/upstream-review-20260912/width-validation-20260912

AI assistance was used for the isolated build, test harness, review and report.
