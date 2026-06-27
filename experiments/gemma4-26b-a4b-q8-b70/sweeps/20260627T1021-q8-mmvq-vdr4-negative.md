# 2026-06-27 - Q8 MMVQ VDR=4 Screen Negative

## Question

After the route-profile audit confirmed Gemma 4 26B Q8 decode-sized routed
expert calls already use the Q8 multi-column MMVQ path, test whether widening
the Q8_0 x Q8_1 MMVQ vecdot ratio helps:

- source file: `/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/vecdotq.hpp`
- default: `VDR_Q8_0_Q8_1_MMVQ=2`
- experiment binary: build with `-DVDR_Q8_0_Q8_1_MMVQ=4`
- binary:
  `/home/steve/src/llama.cpp-gemma-record-stack/build-sycl-b70-aot-bmg-g31-vdr4/bin/llama-server`

Patch artifact:
`patches/gemma4-26b-a4b-q8-b70/20260627T1021-q8-mmvq-vdr-override.patch`

## Result

Clear loss. Do not pursue VDR=4 for this lane.

Correct record-identity screen:

- run:
  `data/gemma4-q8-gpu1-vdr4-rmsreuse-ub768-nmin3-pmin010-recordid-screen-20260627T102132Z/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu1-vdr4-rmsreuse-ub768-nmin3-pmin010-recordid-screen-20260627T102132Z.server.log`
- canary: `16/16` repeats, `64/64` rows, pass
- fresh row0 after TTFT: **44.21455725216031 tok/s**
- wall row0: `43.12433575109506 tok/s`
- support mean after TTFT: `44.00347536660475 tok/s`
- all benchmark rows reported `cached_tokens=0`

Current valid record for comparison:

- run:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- fresh row0 after TTFT: **104.30919255569083 tok/s**

The loss is too large to be noise. The likely explanation is worse occupancy /
register pressure from the wider vecdot body. This also supports the route-audit
recommendation: the next source work should not change VDR globally; it should
specialize or restructure the Q8 multi-column MMVQ body to reduce repeated
weight-block loads while preserving the tuned `VDR=2` inner dot shape.

## Misconfigured Control

An earlier VDR4 screen accidentally omitted the record-lane MTP controls
(`--no-spec-draft-backend-sampling`, draft threads `32/32`, and
`--ctx-checkpoints 0`) and measured `39.08442285684637 tok/s` row0:

- `data/gemma4-q8-gpu1-vdr4-rmsreuse-ub768-screen-20260627T101931Z/`

Do not compare that number to the record lane except as a reminder to diff
benchmark identity before interpreting performance.

## Next

Implement the bounded Q8_0 ncols hoist candidate:

- active path:
  `ggml_sycl_mul_mat_id()` -> sorted/gathered multi-token path ->
  per-expert `ggml_sycl_mul_mat()` -> `can_use_mul_mat_vec_q()` for
  `src1->ne[1] <= 8` -> `ggml_sycl_op_mul_mat_vec_q()` ->
  `mul_mat_vec_q8_0_q8_1_sycl_switch_ncols()`;
- target files:
  `/home/steve/src/llama.cpp-gemma-record-stack/ggml/src/ggml-sycl/mmvq.cpp`
  and possibly `mmvq.hpp`;
- keep the patch env-gated for first test;
- preserve stride semantics: non-reorder `stride_col_y` is in `block_q8_1`
  units and is currently used as `&y[j * stride_col_y + iby]`.

