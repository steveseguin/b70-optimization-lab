# 2026-06-29: Q8 reordered multi-column compact argmax AOT negative

Status: **negative / not tested at runtime**.

Model lane: Gemma 4 26B A4B `UD-Q8_K_XL` target/verifier with Q4_0 MTP draft
on one Intel Arc Pro B70. Current valid record remains
`115.72789384447941 tok/s` from the VDR2 selected-down fused weighted-sum
recipe.

## Idea

The existing `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` verifier path is exact
but slower than the current backend-sampled full-LM-head path. Prior profiling
showed the reason: the current `GGML_OP_MUL_MAT_ARGMAX` implementation uses a
separate scratch/tile argmax path and, for multiple verifier rows, computes
each row independently. The promoted record path benefits from the regular Q8
reordered MMVQ small-ncols kernel, which handles `2..8` columns together.

Attempted source shape:

- add gated env `LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_NCOLS=1`;
- add a reordered-Q8 multi-column argmax tile for `GGML_OP_MUL_MAT_ARGMAX`;
- target only the record verifier shape `nvec=4` (`n_max=3` draft rows plus
  bonus row);
- reuse the existing scratch/reduce output format so sampler semantics stay
  exact.

## Result

Build failed by practicality, not syntax:

- `mmvq.cpp` compiled successfully;
- B70 AOT link entered `ocloc -device bmg-g31` and did not finish in a
  reasonable iteration window;
- the wider first version that instantiated `nvec=2..8` was even worse;
- the experiment was interrupted and the source was reverted to the previous
  record-stack shape.

No benchmark was run, no LocalMaxxing submission was made, and no result should
be promoted from this attempt.

## Lesson

The compact exact LM-head direction is still plausible, but not as a naïve new
templated SYCL kernel layered onto `MUL_MAT_ARGMAX`. For B70 AOT, the next
attempt should avoid broad template instantiation and should preferably reuse
the already-compiled regular reordered-Q8 MMVQ kernel/epilogue shape, or be
developed first in a smaller/JIT build before touching the record AOT target.

Do not retry this exact env/symbol plan:

- `LLAMA_SYCL_MUL_MAT_ARGMAX_MULTI_NCOLS`;
- `mul_mat_vec_q_reorder_argmax_multi_ncols_tile`;
- `reorder_mul_mat_vec_q_argmax_multi_ncols_sycl`;
- `reorder_mul_mat_vec_q_argmax_multi_ncols_switch_sycl`.
