# Qwen3.8 Q8 fused-pair row-chunk interleave

Date: 2026-08-16
Status: closed, rejected; apparent screen gain was a process-position artifact

## Hypothesis

The accepted launch-fused gate/up Q8 kernel streams all rows of matrix 0 and
then all rows of matrix 1. This candidate alternated equal, whole-workgroup row
chunks between the two matrices. The intent was to expose independent HBM
streams without changing the arithmetic of any output row.

The experimental `mul_mat_vec_q8_0_reorder_pair_chunked` kernel retains the
incumbent SG16 DP4A body, per-block order, subgroup reduction, and output
mapping. A same-binary runtime door,
`GGML_SYCL_MMVQ_FUSED_PAIR_CHUNK_ROWS`, selects `0`, `32`, `64`, `128`, `256`,
or `512` rows. Zero takes the incumbent kernel. The treatment applies only
when the two matrices have equal row counts and the chunk is aligned to whole
workgroups.

## Reproduction boundary

- model: `ggml-org/Qwen3.8-27B-GGUF`, revision
  `0669b98607d47046c7c2b3f801011d54a08cfccf`
- file: `Qwen3.8-27B-Q8_0.gguf`, SHA-256
  `f5c702d8820d36fb55985bb238fc83ee3a313e920f4b752a437c3a6a9e14e4c8`
- source base: mndodd `intel-sycl-optimization` commit
  `4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`, plus the accepted Qwen3.8 Q8
  full stack and then the retained incremental patch
- source/build: `/mnt/fast-ai/src/llama.cpp-q38-q8-pair-chunk-interleave`
  and `build-sycl-aot-bmg-g31-make`
- compiler: IntelLLVM 2026.1.1, Release, BMG-G31 AOT, Level Zero enabled,
  DNN/graph/host fallback disabled; build limited to `-j2` in a 6/8 GiB
  memory scope
- benchmark: two B70s, `level_zero:1,0`, `SYCL0/SYCL1`, tensor split `1/1`,
  target-only, F16 KV, flash attention, batch/ubatch `1024/256`
- candidate hashes: `llama-bench`
  `31ef1d1ae9240bd69be164225f3a01d0f68bae1b4d386fd57abbb9bd018856ce`,
  `llama-server`
  `fb2de854ef7c0660516afb944198d9ab91b1b115110fce9e65ed37047953a098`,
  `libggml-sycl.so`
  `b9c67579e586a3c2e49698380648fdf56107b44b86ec85173c76f908078af058`

The incremental patch is
[`q8-fused-pair-chunk-interleave-position-artifact-20260816.diff`](../patches/q8-fused-pair-chunk-interleave-position-artifact-20260816.diff),
SHA-256 `88d352c602f3562fb3887c06dcc586fb09363994573acef0bd3eb60d5fe9729c`.
It passes `git apply --check` against a reconstruction of the accepted source
stack.

## Mechanism gate and short screen

A `p64/n1/r1` chunk-64 smoke ran the treatment on both devices, reported
`VERIFY_MISMATCH=0`, and completed normally. The ordered `p64/n256/r3` screen
then produced:

| Position | Chunk rows | Decode |
| ---: | ---: | ---: |
| 1 | 0, control | `36.805878 tok/s` |
| 2 | 32 | `37.440147 tok/s` |
| 3 | 64 | `37.285603 tok/s` |
| 4 | 128 | `37.144215 tok/s` |
| 5 | 256 | `37.271375 tok/s` |
| 6 | 512 | `37.375656 tok/s` |
| 7 | 0, control | `37.090699 tok/s` |

The pooled edge controls were `36.9482885 tok/s`. Chunk 32 appeared best at
`+1.331%`, but every treatment occupied a middle process position while the
controls occupied the two edges. This was a screening signal, not promotion
evidence.

## Position-balanced confirmation

The best screen arm was rerun as a fresh-process B-A-A-B bracket at
`p64/n512/r3`:

| Position | Arm | Decode |
| ---: | --- | ---: |
| 1 | B1, chunk 32 | `36.375253 tok/s` |
| 2 | A1, control | `37.424021 tok/s` |
| 3 | A2, control | `37.367360 tok/s` |
| 4 | B2, chunk 32 | `37.167925 tok/s` |

The pooled control was `37.3956905 tok/s`; the pooled candidate was
`36.771589 tok/s`, a `-1.669%` delta. Moving the treatment from the middle to
the edges reversed the result. The screen was therefore measuring
fresh-process/run-position state, not a row-scheduling improvement.

## Decision and health

Reject all tested chunk sizes. Do not run an endpoint quality suite and do not
promote this scheduler. A future retry must first introduce a position-randomized
or fully interleaved process protocol and a materially different scheduling
mechanism; repeating this implementation is not useful.

Both GPUs remained normal and unloaded after the run. There was no current
Xe compute fault, reset, hang, device-lost, timeout, or CAT error. The older
boot-log OOM was an unrelated, earlier Docker/vLLM compilation inside its own
8 GiB cgroup and did not overlap this experiment.

Raw logs are retained under
`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-pair-chunk-interleave/`.
Their exact hashes and the structured result are in
[`2026-08-16-q8-fused-pair-chunk-interleave-position-artifact.json`](../data/2026-08-16-q8-fused-pair-chunk-interleave-position-artifact.json).
