# Current-source dynamic GDN width device-validation packet

Parent execution completed: [device-results.json](device-results.json) and
[follow-up summary](../VALIDATION.md). Both dtypes pass stock full-width control,
reproduce stock reduced-width rejection, and pass candidate 3→2→3 transitions.
The preparation-only statements below describe the packet author's work before
the parent device run. Full-model and graph qualification are still absent.

Prepared September 12, 2026. No GPU execution by the packet's author. Parent
agent owns preflight and device runs. This packet builds isolated spec kernels
without installing packages or changing any production image.

## Build scope

`build_isolated.py` copies the pinned source archive's GDN directory into a new
output directory, optionally applies the width candidate, then extracts the
exact `causal_conv1d_spec` and `gated_delta_rule_spec` C++ entrypoints. It compiles
those with unchanged `causal_conv1d.hpp`, `gated_delta_rule.hpp`,
`gdn_attn_utils.h`, and `dispatch_utils.h` into `width_review.so`. Registration
uses separate `torch.ops.width_review.conv/delta`, never `_xpu_C`.

The only adapter is the exact `vllmGetQueue` definition extracted from upstream
`utils.h`; unused architecture helpers are omitted. `VLLM_XPU_ENABLE_XE2` is
undefined, avoiding non-spec TLA chunk kernels. The spec kernels themselves do
not depend on that macro. No oneDNN, TLA, vLLM package, or Python pybind module
is needed. Compiler/link jobs limited to two. Dependencies: existing torch
2.11.0+xpu venv and Intel oneAPI 2025.3 icpx (matches torch libsycl.so.8). Both stock and candidate compiled
successfully with direct SYCL linking against torch/c10 XPU libraries.

Source: `efc85bc8a0eb3076c861b2e6cb1e1731a93905d5`, archive located by parent at
`/home/steve/q27-validation-20260912/vllm-project-vllm-xpu-kernels-efc85bc`.
Archive URL:
`https://api.github.com/repos/vllm-project/vllm-xpu-kernels/tarball/efc85bc8a0eb3076c861b2e6cb1e1731a93905d5`;
downloaded archive SHA256:
`2aff4bbaa77b202619a27c7dbf9005d71d3214cb2f992caa771215ead0725172`.
Run `build_isolated.py --source EXTRACTED_SOURCE --output NEW_DIRECTORY`
under the documented torch Python; for candidate add
`--patch ../width/active-width-candidate.patch`. Exact commands and generated
translation units used are retained in `build-stock-2025/` and
`build-candidate-2025/`. Binaries remain outside Git with recorded hashes.
Build outputs:

- `/home/steve/q27-validation-20260912/width-stock-2025-build/width_review.so`
- `/home/steve/q27-validation-20260912/width-candidate-2025-build/width_review.so`

Each build directory contains extracted TU, command JSON, library hash receipt,
and isolated source. The candidate uses sibling
`../width/active-width-candidate.patch`.

## Explicit GPU probe after preflight

Run one arm per process (the library namespace cannot be registered twice):

```bash
/home/steve/.venvs/vllm-xpu/bin/python probe_width.py \
  --library /home/steve/q27-validation-20260912/width-stock-2025-build/width_review.so \
  --arm stock --dtype float16
/home/steve/.venvs/vllm-xpu/bin/python probe_width.py \
  --library /home/steve/q27-validation-20260912/width-candidate-2025-build/width_review.so \
  --arm candidate --dtype float16
```

Repeat with `--dtype bfloat16` if fp16 passes. Bind a single device using the
parent's preflight-approved affinity environment; the script targets xpu:0.
No model load, server, networking, or multi-GPU collective occurs.

The case uses 16 K heads, 32 V heads, head dimensions128, two requests, configured
cache width3, active widths3→2→3. Accepted-token counts are [0,1]→[3,2]→[2,1],
so the shrinking step reads history at old column2, beyond the new active width.
Global token indices are permuted. Entire physical cache remains width3.

At each successful step compare output,z,all conv and SSM tensors to adapted
upstream PyTorch reference. z and convolution state must be bit-exact; untouched
SSM slots must be bit-exact, including inactive columns2/5 on the reduced step.
Output and written SSM state have explicit allclose screening plus relative
L2 error <=0.005 fp16 or <=0.02 bf16, calculated on written slots only for SSM.
Nonzero reference norms and max errors are reported. Zero outputs cannot pass.

Stock should pass step0 then reject step1 in the native convolution interface.
Do not bypass that guard to launch stock reduced-width delta: its current loop
bounds can access beyond compact buffers. Candidate must pass all three steps.

## Reference and limits

`reference.py` derives two functions from current upstream
`tests/gdn_attn/test_gdn_attn.py`; origin hash and precise changes are in
`reference-origin.json`. It uses query-offset width instead of cache capacity,
computes effective convolution prefix length as `conv_width-2+active_width`,
and preserves unused physical tail. This matches the proposed native
uniform-active-width convention, but is not independent proof that vLLM's
scheduler uses the same cache convention in every mode.

`probe_width.py --cpu-contract-only` passed without device initialization.
It rejects ragged [1,3], [3,1], [0,4] offsets even though aggregate divisibility
can hold. That is a harness restriction, not a fix for native ragged dispatch.
Do not claim native ragged support. Fresh GPU results must be attached by the
parent; this packet itself claims only successful CPU-side compilation.

Missing coverage includes mixed batches, graph capture, strided/interleaved
cache, varied seeds/shapes, other compiler/runtime combinations, long service
soak, and full-model scheduler integration. It is a correctness microprobe,
not a throughput benchmark or recipe-promotion gate.

## Loader correction (attempt1)

The first libraries compiled with oneAPI2026.0 but required libsycl.so.9, while
the torch2.11 environment provides libsycl.so.8. Parent's first attempt stopped
at library loading, before GPU kernels. Preserve original width-stock-build
and width-candidate-build as failed build artifacts. Rebuilt both with
oneAPI2025.3 into separate *-2025-build directories. Do not fix this by loading
both SYCL runtimes. CPU load checks must map only the venv libsycl.so.8 and
leave torch.xpu.is_initialized() false. No added compiler rpath is required:
importing torch already resolves venv libsycl/libsvml/libimf/libirng.
