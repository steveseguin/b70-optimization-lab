# Gemma 4 26B Strided-ID Selected-Down Matmul-Epilogue Snapshot

Date: 2026-06-26

Patch:
`patches/gemma4-26b-a4b-q8-b70/20260626T1818-strided-id-selected-down-matmul-epilogue-cumulative.patch`

Source worktree:
`/home/steve/src/llama.cpp-gemma-record-stack`

This is a cumulative source snapshot of the Gemma 4 MoE selected-softmax /
selected-down experimental stack in:

- `src/llama-graph.cpp`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`

The latest changes captured here are default-off support/enabling changes for
strided selected-expert ID tensors:

- allow non-transposed strided I32 IDs for
  `GGML_OP_MOE_SELECTED_SOFTMAX_WEIGHTED_SUM`;
- allow non-transposed strided I32 IDs for
  `GGML_OP_MOE_SELECTED_DOWN_WEIGHTED_SUM`;
- densify strided IDs on host for selected-down route sorting/profile
  accounting, while leaving the device epilogue on the original device ID
  tensor and strides;
- add the default-off
  `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NAME_SUBSTR` diagnostic filter.

Validation screens:

- `data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-stridedids-screen-20260626T180548Z/summary.json`
  - `128/128` canary rows, fresh row0 `102.36018628889175 tok/s`;
- `data/gemma4-q8-gpu0-selecteddown-matmul-epilogue-stridedids-screen-20260626T181834Z/summary.json`
  - `128/128` canary rows, fresh row0 `102.82922518638489 tok/s`;
- `data/gemma4-q8-gpu0-selecteddown-matmul-epilogue-skipweights-stridedids-screen-20260626T182028Z/summary.json`
  - `128/128` canary rows, fresh row0 `100.69151522542195 tok/s`;
- `data/gemma4-q8-gpu0-selecteddown-matmul-epilogue-stridedids-clean-screen-20260626T182204Z/summary.json`
  - `128/128` canary rows, fresh row0 `100.98858879531659 tok/s`.

Decision: keep as an experiment artifact, but do not promote as the Gemma Q8
fresh-response record. The current valid headline remains
`103.2992004295621 tok/s` from
`data/gemma4-q8-gpu0-selectedsoftmax-weightedsum-pmin0136-full-20260625T031510Z/summary.json`
with LocalMaxxing id `cmqsylo2l011nqr011yydjvne`.

Lesson: strided-ID guard relaxation is useful plumbing, but wrappers around the
existing per-expert matmul still pay too much route sorting / packing overhead.
The next meaningful Gemma path should reduce target/verifier MoE cost with a
larger shape-specific kernel or a verifier shortcut, not another scalar flag
sweep.
