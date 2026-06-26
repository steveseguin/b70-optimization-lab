# 20260626T1844 Gemma4 `MUL_MAT_ID` Route Cache Micro-Record

## Status

Valid but tiny win. Preserve as a default-off experiment patch and result
reference, but do not treat it as material progress.

- model: Gemma 4 26B A4B IT, `UD-Q8_K_XL` target/verifier;
- draft: local Gemma MTP `Q4_0` draft only;
- hardware: one Intel Arc Pro B70 32 GB, GPU0;
- runtime: llama.cpp SYCL AOT BMG, current Gemma record stack;
- env gate: `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1`;
- LocalMaxxing: approved as `cmqvalync02lhqr01h76rnti3`.

## Patch Shape

Source worktree:
`/home/steve/src/llama.cpp-gemma-record-stack`.

Touched source files:

- `ggml/src/ggml-sycl/common.hpp`
  - add `#include <vector>`;
  - add `struct mmid_route_cache`;
  - add `mmid_route_cache mmid_route_cache_host;` to
    `ggml_backend_sycl_context`.
- `ggml/src/ggml-sycl/ggml-sycl.cpp`
  - add `ggml_sycl_mul_mat_id_route_cache_enabled()` reading
    `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE`;
  - in the multi-token `GGML_OP_MUL_MAT_ID` host route-packing path, cache the
    immediately previous selected-expert IDs host copy, expert row counts,
    offsets, and routed row mapping;
  - reuse the cache only when tensor pointer, data pointer, shape, strides,
    byte span, and routed-row count all match;
  - clear on hit so reuse is one-shot only. This prevents stale pointer-based
    reuse across decode steps where the selected-experts tensor object/data can
    remain stable while contents change.

The raw llama.cpp source worktree contains a broader Gemma patch stack, so do
not treat a full `git diff` from that tree as this patch alone. Use the source
symbols above to isolate this experiment if extracting it later.

## Hypothesis

The selected-expert IDs for adjacent Gemma MoE `MUL_MAT_ID` ops can be reused
inside the same decode step. Reusing the route materialization for the
immediately following matching op should avoid one host wait / route sort /
row-map build without changing model math.

## Validation

Screen:

- `data/gemma4-q8-gpu0-mulmatid-routecache-screen-20260626T184446Z/summary.json`
- canary: `128/128`, pass;
- fresh row0 after TTFT: `103.42820086552045 tok/s`;
- row0 wall: `90.18501516643299 tok/s`;
- cached tokens: `[0, 0]`.

Full gate:

- `data/gemma4-q8-gpu0-mulmatid-routecache-full-20260626T184617Z/summary.json`
- canary: `1536/1536`, pass;
- fresh row0 after TTFT: `103.30108468098005 tok/s`;
- supporting mean after TTFT: `103.06255061691155 tok/s`;
- row0 wall: `89.97733776184405 tok/s`;
- cached tokens: `[0, 0, 0, 0, 0, 0, 0, 0]`;
- previous record: `103.2992004295621 tok/s`;
- delta: `+0.00188425141795 tok/s`.

LocalMaxxing evidence:

- queue:
  `data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626.queue.json`
- response:
  `data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-mtp-n7-q8target-q40draft-routecache-pmin0136-fresh-20260626.submit.log`

## Interpretation

The cache is correctness-safe under the current full gate and slightly positive,
but the margin is noise-sized. It is useful as a preserved micro-optimization
and as proof that route materialization can be reused safely only with strict
one-shot invalidation. It does not change the main Gemma bottleneck.

Do not spend more time on scalar host route-cache variants unless a profile
shows route packing has become dominant again. The remaining high-ROI Gemma work
is target/verifier MoE work: graph-level multi-token assistant unroll,
shape-specific MoE kernels, or a verifier shortcut that avoids doing full target
work for every speculative candidate.
