# Qwen3.8 Python-ordered INT4 M=1→2 repair D34 preregistration

Date: 2026-08-31

Status: **preregistered before D34 model requests**

D32 proved the loaded production projection is deterministic at M=2 and not
at M=1. D33 and D33r attempted to create that extra row inside the custom C++
operator; both failed because the padded input was still populated immediately
before an asynchronous oneDNN dispatch without a dispatcher-visible dependency.

D34 returns to the original deterministic mechanism: for every
`INCXPULinearMethod` call whose flattened row count is one, vLLM constructs a
two-row input, copies the real row into row zero, calls the unchanged production
operator, then returns its row-zero view. These operations are issued through
PyTorch before crossing the custom-op boundary. All other row counts and
quantization paths remain unchanged.

The immediate gate is four fresh-process layer-0 decode-call-2 traces using the
sealed current image `sha256:895e82ec34982f2ca957a00d14b055e41bad6b63f2ac123141c24fd398727136`
plus the hash-bound diagnostic hook. The normalized input and final `out_proj`
must each have exactly one hash. The candidate output must equal D32's direct
M=2 row-zero hash
`650e70d1ff44ee4b513f31fc746c535c2ece8440a8ee6c61ed55fef9f49a2db7`.

Passing this localization gate authorizes packaging the Python repair. It does
not authorize a performance or quality claim. A packaged-image replay, strict
varied-prompt cross-process determinism suite, independent output/quality
attestation, and cold performance comparison remain mandatory.
