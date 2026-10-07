# Pinned split-half RoPE arithmetic compatibility

This process-local candidate restores the accepted comfy-kitchen 0.2.33 eager
`apply_rope_split_half1` arithmetic within the otherwise unchanged 0.2.37 package.
It changes one existing function object's code, preserving its eager-module alias,
registry ownership and callers. The other split-half helpers resolve that same
function; their code and registration stay unchanged. Installed packages, frozen
packets and model weights are never edited. GPU/full-clip parity is pending.

The updated helper changed two separately rounded products plus addition into
a diagonal product followed by `addcmul_`. Gemma4 directly uses this helper for
Q/K rotary embeddings. Packet 99 recorded matching text hashes, real-token counts
and window 64 but different conditioning fingerprints before the sampler. This
makes RoPE a concrete arithmetic compatibility hypothesis, not yet a proven sole
cause of the failed clips.

`install_rope_compat.py:install()` returns a JSON-compatible receipt. Call it only
after normal CLI, model-management and `comfy.quant_ops` initialization, and before
model construction or graph capture. It checks the exact isolated dependency path,
old/new full-source SHA256, loaded code for all four split-half helpers, module and
registry ownership, aliases, eager-only backend routing and absence of a thread
backend override. It refuses repeat installation and unknown source/code/routing.
It neither changes backend settings nor catches tensor exceptions. A caller must
stop startup if installation fails, and bind its receipt in the final server
identity before requests. The runtime 99b wrapper owns this ordering.

The old/new source files are preserved verbatim under `source-evidence/` with
upstream SPDX headers, LICENSE, NOTICE, source paths and exact function bytes.
Expected code is compiled from the full pinned module without executing that
module: Python's knowledge of module imports can affect generated call opcodes,
so compiling an isolated function AST would give a false identity mismatch.

CPU controls:

```
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/recovery/20261007-rope-compat/test_rope_compat.py
```

Ten tests cover repeat/source/bytecode/alias/global-binding/backend refusals,
exception propagation and unchanged unsupported-FP64 dispatch rejection. Numerical
cases include BF16 inputs with FP32 matrices (contiguous and noncontiguous),
FP32/FP32, BF16/BF16, and another BF16/FP32 window. Every restored result matches
the old operation bytewise, including repeated calls and pair/in-place helpers;
inputs remain unchanged. Old/new mixed BF16/FP32 outputs differ by 9 bytes in the
window 64 fixture and 16 bytes in window 128. This is a real CPU arithmetic
counterexample, not a model quality result.

The tests block GPU availability/initialization and simulate only quant_ops'
eager routing state. They exercise the real installed kitchen torch.ops dispatch
on CPU; they do not initialize Comfy or load a model. Gemma4 source computes its
rotary matrices in the residual stream dtype; saved text-layer capture output is
FP32, so the mixed BF16-projection/FP32-matrix case is included explicitly. No
saved per-Q/K tensor census was added to the failed 99 run.

Two development-control issues are recorded in `cpu-validation.json`: the first
isolated-AST identity control mismatched valid imported code, and a test requested
FP64 through a registry that correctly rejects it. Both were test-design issues;
no application launch, package mutation or GPU operation occurred.
