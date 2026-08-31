# Qwen3.8 INT4 M=1→2 view repair D33r preregistration

Date: 2026-08-31

Status: **preregistered before the D33r build or model requests**

D33 failed because a separate XPU `copy_()` consumed the asynchronous padded
oneDNN destination. D33r changes only the handoff: the result tensor is rebound
to a row-0 view of the M=2 destination, with no post-matmul copy. The candidate
patch and built image must be hash-bound after this preregistration is written.

The immediate gate is the same four-fresh-process layer-0 decode-call-2 stage
trace. The normalized input and final `out_proj` must each have one hash. The
candidate output should also match D32's direct loaded-projection M=2 row-0
hash `650e70d1ff44ee4b513f31fc746c535c2ece8440a8ee6c61ed55fef9f49a2db7`.
Only after this passes may the strict varied-prompt determinism, independent
quality attestation, and cold performance gates run.
