# Ornith 1.5 35B-A3B Q4_K_M one-B70 patch

This packet contains the lab-maintained SYCL decode optimization used by the
Ornith 1.5 35B-A3B recipe. It is a source patch against upstream llama.cpp;
the recipe and validation evidence in this repository are the source of truth.

## Identity

- Base: llama.cpp `9fee29e9435f865ec0b811a783a6471a136d9317`.
- Current complete patch: `llama-cpp-ornith15-moe-add-conv-silu-residual-rms-concat-state-direct-alpha-moe-gate-up-shared-residual-rms-gdn-rms-gate-20260823.patch`.
- Patch SHA-256:
  `762becc20a4ce1d82017bdb7d73485ff892eb26b9cf141dd9b74a9707fe1cf9a`.
- Runtime doors: `GGML_SYCL_FUSED_MOE_ADD_REDUCE=1` and
  `GGML_SYCL_FUSED_ORNITH_CONV_SILU=1` and
  `GGML_SYCL_FUSED_RESIDUAL_RMS_NORM=1` and
  `GGML_SYCL_FUSED_ORNITH_CONCAT_STATE=1` and
  `GGML_SYCL_FUSED_ORNITH_CONCAT_STATE_DIRECT=1` and
  `GGML_SYCL_FUSED_ORNITH_ALPHA_GATE=1` and
  `GGML_SYCL_FUSED_ORNITH_MOE_GATE_UP=1` and
  `GGML_SYCL_FUSED_ORNITH_MOE_SHARED_RESIDUAL_RMS=1` and
  `GGML_SYCL_FUSED_ORNITH_GDN_RMS_GATE=1` (all default off).
- Validated `libggml-sycl.so` SHA-256:
  `d75d5f1d07b6ac64421bbc9ae3cda7b916584f0422d512f57843a50427478e8c`.

Apply only to the pinned clean base:

```bash
git checkout 9fee29e9435f865ec0b811a783a6471a136d9317
sha256sum /path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-moe-add-conv-silu-residual-rms-concat-state-direct-alpha-moe-gate-up-shared-residual-rms-gdn-rms-gate-20260823.patch
git apply --check /path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-moe-add-conv-silu-residual-rms-concat-state-direct-alpha-moe-gate-up-shared-residual-rms-gdn-rms-gate-20260823.patch
git apply /path/to/b70-optimization-lab/patches/ornith-15-35b-a3b-q4km-b70/llama-cpp-ornith15-moe-add-conv-silu-residual-rms-concat-state-direct-alpha-moe-gate-up-shared-residual-rms-gdn-rms-gate-20260823.patch
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

The full-model trace observed 40 ordered-reduction matches, 30 recurrent
convolution/SiLU matches, 80 residual/RMSNorm matches, and 30 recurrent
concat/state matches per token. The direct state-materialization path replaces
the latter boundary and also removes 30 recurrent `GET_ROWS` launches. Together
the complete stack removes 630 launches/token.

The second fusion accepts only the exact one-token `[4,8192]` FP32 convolution
whose sole consumer is a full-width SiLU. It preserves stock state handling,
convolution accumulation order, and SiLU expression. Any shape, stride, name,
type, or ownership mismatch uses the stock path.

The third fusion recognizes the Qwen-derived 2048-wide `attn_residual-*` and
`l_out-*` chains. It writes and rereads the original residual tensor through a
volatile FP32 pointer, preserving later skip-connection consumers, then uses
the stock RMS reduction order and fused norm-weight expression.

The fourth fusion recognizes only the Qwen-derived one-token `[4,8192]` FP32
recurrent convolution input. It materializes the full concat output and mirrors
rows 1-3 into the original persistent-state destination in the same kernel.
The state copy must be the next real compute node, and exact shape, stride,
consumer, name, type, and non-overlap checks fail closed to stock execution.

The fifth fusion further specializes that verified boundary for the exact
one-row persistent-state case. One work-item owns each channel, loads all three
old state values before any write, then materializes the original `GET_ROWS`
output, complete concat output, and shifted persistent state. It leaves the
convolution separate. Exact source identity, sole-consumer, node-order, shape,
stride, and non-overlap gates fall back to the fourth fusion on any mismatch.

The sixth fusion recognizes only Ornith's recurrent 32-element FP32
`alpha + ssm_dt.bias -> softplus -> multiply by ssm_a` chain. It materializes
and rereads the original rounded ADD tensor before applying the existing SYCL
softplus expression and gate multiplication. Exact node adjacency, names,
shapes, source order, layout, output flags, and sole-consumer checks fail closed
to the prior stack.

The seventh fusion keeps Ornith's routed-expert gate/up work on the tuned
reordered-Q4_K `MUL_MAT_ID` path. Each subgroup computes both original dot
products in their prior reduction order and writes SWIGLU directly to the
graph's GLU destination. Exact model names, shapes, route ids, adjacency,
sole-use, strides, quantization, layout, and device checks fail closed. It
removes one duplicate input quantization, one routed GEMV, and one GLU launch
per MoE layer, or 120 launches/token.

The eighth fusion extends the Qwen-derived residual/RMSNorm path across the
preceding routed-plus-shared-expert ADD. It writes and reloads both original
FP32 ADD destinations before the unchanged RMS reduction, preserving their
graph-visible rounding and other consumers. Exact tensor names, node order,
shape, stride, type, and ownership checks fail closed. It removes one launch
per MoE layer, or another 40 launches/token.

The ninth fusion recognizes Ornith's exact Qwen3.5-derived 128x32 recurrent
gated-normalization subgraph. It delays the existing RMSNorm/weight operation
until the parallel `z` projection is ready, then performs the stock SIMD16 XOR
reduction, weight multiplication, SiLU, and final gate multiply in one kernel.
A volatile FP32 normalized value preserves the original graph materialization
boundary. Exact layer names, shapes, graph edges, opcodes, use counts, types,
and contiguous layouts fail closed. It removes one launch in each of 30
recurrent layers.

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
- The added residual/RMSNorm fusion improved matched raw-engine decode by
  **+2.00%** and two-fresh-server decode by **+1.37%** over the prior stack,
  reaching a `107.775961 tok/s` two-server mean. Its forced 128-token canonical
  output was byte-identical and all candidate canaries passed.
- The added recurrent concat/state fusion improved matched raw-engine decode by
  **+3.53%** and two-fresh-server decode by **+2.74%** over the prior stack,
  reaching a `108.661707 tok/s` two-server mean. Its forced 128-token output
  was byte-identical and all candidate canaries passed.
- The added direct gathered-state path improved matched raw-engine decode by
  **+1.97%** and two-fresh-server decode by **+1.12%** over the prior stack,
  reaching a `111.882513 tok/s` two-server mean. Its forced 128-token output
  was byte-identical before and after matcher hardening, and all candidate
  canaries passed.
- The added recurrent alpha-gate fusion improved pooled matched raw-engine
  decode by **+1.18%** and two-fresh-server decode by **+2.04%** over the prior
  stack, reaching a `114.314270 tok/s` two-server mean. Each candidate server
  exceeded each control; forced 128-token output was byte-identical and all
  candidate canaries passed.
- The added routed-expert gate/up fusion improved mirrored raw-engine decode by
  **+2.09%** and two-fresh-server decode by **+2.33%** over the prior stack,
  reaching a `115.680299 tok/s` two-server mean. Every candidate exceeded every
  control; forced 128-token output was byte-identical and all canaries passed.
- The added MoE shared-branch residual/RMSNorm fusion improved mirrored
  raw-engine decode by **+0.99%** and two-fresh-server decode by **+1.41%**
  over the prior stack, reaching a `118.048489 tok/s` two-server mean. Every
  candidate exceeded every control; forced 128-token output was byte-identical
  and all canaries passed.
- The added GDN RMSNorm/SiLU-gate fusion improved mirrored raw-engine decode by
  **+0.34%** and matched fresh-server decode by **+0.78%** over the prior
  stack, reaching a directly measured `117.446154 tok/s` two-server mean.
  Every candidate exceeded every control; forced 128-token output was
  byte-identical, exactly 3,810 recurrent hits were recorded, and all canaries
  passed.

Fresh stock servers matched `0/12` complete response hashes with each other on
the long realistic suite. That pre-existing cross-process instability is
recorded but is not attributed to this patch; within-process stability and the
same-binary door-off/on exact comparison passed.

Full evidence and limitations are in the
[matched experiment note](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-moe-add-reduce-positive.md).
The incremental convolution result is in
[`2026-08-22-ornith35b-conv-silu-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-conv-silu-positive.md).
The incremental residual result is in
[`2026-08-22-ornith35b-residual-rms-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-residual-rms-positive.md).
The incremental recurrent-state result is in
[`2026-08-22-ornith35b-concat-state-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-concat-state-positive.md).
The direct gathered-state increment is in
[`2026-08-22-ornith35b-concat-state-direct-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-concat-state-direct-positive.md).
The recurrent alpha-gate increment is in
[`2026-08-22-ornith35b-alpha-gate-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-22-ornith35b-alpha-gate-positive.md).
The routed-expert gate/up increment is in
[`2026-08-23-ornith35b-moe-gate-up-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-moe-gate-up-positive.md).
The MoE shared-branch residual/RMSNorm increment is in
[`2026-08-23-ornith35b-moe-shared-residual-rms-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-moe-shared-residual-rms-positive.md).
The GDN RMSNorm/SiLU-gate increment is in
[`2026-08-23-ornith35b-gdn-rms-silu-gate-positive.md`](../../experiments/ornith-15-b70/notes/2026-08-23-ornith35b-gdn-rms-silu-gate-positive.md).
