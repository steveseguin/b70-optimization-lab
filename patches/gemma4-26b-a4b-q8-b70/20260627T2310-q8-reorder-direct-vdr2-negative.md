# Q8 Reorder Direct VDR2 Patch - Negative

Date: 2026-06-27

## Scope

Default-off llama.cpp/SYCL experiment in
`/home/steve/src/llama.cpp-gemma-record-repro-c926`.

Files touched:

- `ggml/src/ggml-sycl/mmvq.cpp`
- `ggml/src/ggml-sycl/mmvq.hpp`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`

Env gate:

```bash
LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_DIRECT_VDR2=1
```

## Implementation Idea

Specialize the active Gemma 4 26B verifier `MUL_MAT_ID` small multi-token
reordered-Q8 path for VDR2:

- Q8_0 reordered target weights only;
- `src1=[ncols,1,n_tokens]`;
- `ids=[n_experts_used,n_tokens]`, with `n_experts_used<=8`;
- direct Q8_0/VDR2 addressing in the inner loop instead of the generic
  `reorder_vec_dot_q_sycl<GGML_TYPE_Q8_0>` trait path.

The dispatch is narrow and default-off. The env helper returns false on
non-VDR2 builds so a default VDR4 binary cannot mark graph nodes eligible for
a missing specialization.

## Build Result

The first build failed on a hard-coded `blocks_per_subgroup == 8` assertion.
The B70 build uses `GGML_SYCL_WARP_SIZE=16`, so VDR2 gives
`blocks_per_subgroup == 4`. The assertion was corrected to match the generic
reordered kernels' positive-invariant style.

The AOT BMG VDR2 `llama-server` build then succeeded.

## Validation Result

Strict fresh-response realistic suite, all `cached_tokens=0`, no history/cache
reuse:

- screen:
  `data/gemma4-q8-gpu0-directvdr2-screen-n3-nmin2-p00475-ub1024-20260627T230753Z/summary.json`
  at `90.71249998925582 tok/s`;
- four-GPU confirmation:
  - GPU0 `89.78446476095618`;
  - GPU1 `88.2181491417087`;
  - GPU2 `86.62953234681859`;
  - GPU3 `86.36862208450489`.

Current promoted record remains `90.98312252660529 tok/s`.

## Decision

Negative. Keep as default-off source artifact only. Do not submit to
LocalMaxxing and do not include in promoted reproduction commands.

Detailed run note:
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T2310-q8-reorder-direct-vdr2-negative.md`.
