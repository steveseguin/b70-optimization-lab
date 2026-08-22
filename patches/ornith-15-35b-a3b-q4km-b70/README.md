# Ornith 1.5 35B-A3B Q4_K_M one-B70 patch

This packet contains the lab-maintained SYCL decode optimization used by the
Ornith 1.5 35B-A3B recipe. It is a source patch against upstream llama.cpp;
the recipe and validation evidence in this repository are the source of truth.

## Identity

- Base: llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`.
- Current complete patch: `llama-cpp-ornith15-moe-add-conv-silu-20260822.patch`.
- Patch SHA-256:
  `8e780b0f4c43a69bd18d0d8d66087d65813cb83353437c3443898231b94c0f9c`.
- Runtime doors: `GGML_SYCL_FUSED_MOE_ADD_REDUCE=1` and
  `GGML_SYCL_FUSED_ORNITH_CONV_SILU=1` (both default off).
- Validated `libggml-sycl.so` SHA-256:
  `d478e4ca7c84faef34e6acf8b1bcf3bdfd8b6e37abe884ea9e0b2826f0dfe883`.

Apply only to the pinned clean base:

```bash
git checkout 9fee29e9435f865ec0b811a783a6471a136d9317
sha256sum /path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-moe-add-conv-silu-20260822.patch
git apply --check /path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-moe-add-conv-silu-20260822.patch
git apply /path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-moe-add-conv-silu-20260822.patch
git diff --check
```

## What it changes

Each decode layer materializes eight weighted routed-expert rows and then
reduces them through seven serial FP32 `ADD` launches. The patch recognizes
only that exact eight-expert, contiguous, ordered chain and performs the same
seven additions in one kernel. The preceding weighted multiplication remains
separate, preventing fused-multiply-add contraction and preserving its rounded
graph-visible outputs. Any shape, order, use-count, type, or layout mismatch
falls back to stock execution.

The full-model trace observed 40 ordered-reduction matches and 30 recurrent
convolution/SiLU matches per token. Together they remove 270 launches/token.

The second fusion accepts only the exact one-token `[4,8192]` FP32 convolution
whose sole consumer is a full-width SiLU. It preserves stock state handling,
convolution accumulation order, and SiLU expression. Any shape, stride, name,
type, or ownership mismatch uses the stock path.

## Validation

- Raw engine A/B/B/A-style means: `103.047744` control versus
  `108.097861 tok/s` candidate (**+4.90%**).
- Two fresh-server means: `99.664082` control versus
  `104.499487 tok/s` candidate (**+4.85%**).
- All four server runs passed unique-prompt and zero-cached-token gates.
- Same-binary door-off/on forced 400-token greedy output: byte-identical,
  SHA-256 `08f2d1834e42656c85768beef340dda43f35a81924d24a4483613466e99056bb`.
- Candidate canaries: 8x repeat stability, arithmetic, exact copy, and JSON
  schema all passed.
- The added convolution/SiLU fusion improved matched raw-engine decode by
  **+1.18%** and two-fresh-server decode by **+2.10%** over the ordered-MoE
  stack. Its forced 400-token response was byte-identical door-off/on.

Fresh stock servers matched `0/12` complete response hashes with each other on
the long realistic suite. That pre-existing cross-process instability is
recorded but is not attributed to this patch; within-process stability and the
same-binary door-off/on exact comparison passed.

Full evidence and limitations are in the
[matched experiment note](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-moe-add-reduce-positive.md).
The incremental convolution result is in
[`2026-08-22-ornith35b-conv-silu-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-conv-silu-positive.md).
