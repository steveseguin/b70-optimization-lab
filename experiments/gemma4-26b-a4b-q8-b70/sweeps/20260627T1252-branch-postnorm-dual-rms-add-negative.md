# 2026-06-27T12:52Z - Branch post-norm dual-RMS-add fusion

## Idea

Gemma 4 MoE layers compute two residual branches before the FFN/MoE combine:

- `attn_output = rms_norm(attn_output) * post_attention_norm`
- `ffn_moe = rms_norm(ffn_moe) * post_ffw_norm`
- `ffn_moe_combined = attn_output + ffn_moe`

The experiment added an env-gated fused op:

- `GGML_OP_RMS_NORM_DUAL_SCALE_ADD`
- API: `ggml_rms_norm_dual_scale_add(ctx, a, scale_a, b, scale_b, eps)`
- model flag: `LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD=1`

The fused op computes both RMS norms, applies both scales, and writes the add
result in one output tensor. The goal was to remove one graph node and one
intermediate write per layer.

Source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/branch-postnorm-dual-rms-add-source-snapshot-20260627.patch`

Note: this snapshot is against the dirty Gemma optimization source tree at
`/home/steve/src/llama.cpp-gemma-record-repro-c926`; it includes the broader
existing Gemma stack in the touched files and is not a minimal upstream patch.

## Build

Built successfully:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31 --target llama-server -j 12
```

The local benchmark binary was:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31/bin/llama-server
```

## Paired Screen

All runs used the current Q8 Gemma 4 26B MTP stack:

- Q8 target/verifier model;
- Q4_0 MTP draft;
- f16 KV;
- `BENCH_PROMPT_MODE=filled-long`, actual prompt 588 tokens;
- `MAX_TOKENS=512`;
- `BATCH_SIZE=1024`;
- `MTP_N_MAX=7`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`;
- backend sampling disabled;
- graph enabled;
- route cache, RMS reuse, selected softmax fused, MTP fused output argmax.

Screen validation only: `CANARY_REPEATS=8`, `BENCH_REPEATS=1`.
This is enough to reject a regression, not enough to promote a record.

| label | gpu | ubatch | branch fusion | canary | fresh row0 tok/s after TTFT | wall tok/s | output hash |
| --- | ---: | ---: | --- | --- | ---: | ---: | --- |
| `gemma4-q8-gpu0-branchpost-control-ub768-20260627T125207Z` | 0 | 768 | off | 32/32 pass | `105.34818158752705` | `91.36349779305849` | `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31` |
| `gemma4-q8-gpu1-branchpost-fused-ub768-20260627T125207Z` | 1 | 768 | on | 32/32 pass | `104.07895046457548` | `90.2840615648743` | `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31` |
| `gemma4-q8-gpu2-branchpost-control-ub832-20260627T125207Z` | 2 | 832 | off | 32/32 pass | `103.8638921375127` | `90.18789944760371` | `d4cf5f90168bd7a276a1bc3072aa2641d8b33eb7a9a269271650586091600f31` |
| `gemma4-q8-gpu3-branchpost-fused-ub832-20260627T125207Z` | 3 | 832 | on | 32/32 pass | `102.71096714815394` | `89.1892067236382` | `d3236ebed08dda8f19a0fec78622967b3622704da06819c98a7e0e63f90d982b` |

The GPU3 fused UB832 output still passed canaries, but the long benchmark text
changed style (comma-free list and more line count). Because the fused run was
slower anyway, no follow-up quality investigation was warranted.

## Decision

Negative. The fused branch post-norm op is slower than paired controls at both
UB768 and UB832, despite passing the short canary screen. Do not enable
`LLAMA_GEMMA4_MOE_FUSED_BRANCH_POST_NORM_ADD` for headline runs.

Likely reason: the custom dual-RMS kernel does two reductions in one bespoke
node, but the existing graph has well-optimized RMS kernels and scheduling. The
saved intermediate/write is not enough to offset the custom kernel overhead.

No LocalMaxxing submission. No full confirmation run.

Follow-up if revisited: profile the node-level timing with this flag enabled
before changing the kernel again. A successful branch fusion would likely need
a better vectorized/tiled RMS implementation or a scheduler-level fusion that
keeps the existing RMS fast path.
