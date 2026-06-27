# Gemma4 26B Q8 Route Profile: Decode Slices Already Use MMVQ (2026-06-27 10:01 UTC)

## Question

After the guarded prequant route-row experiment measured below record, verify
whether the current Gemma4 Q8 verifier `MUL_MAT_ID` expert slices are already
using the small-batch MMVQ path. If they are, more route/gather/scatter
plumbing is unlikely to produce a material win.

Current valid one-B70 fresh-response record for comparison:

- run:
  `data/gemma4-q8-gpu0-rmsreuse-ub768-nmin3-pmin010-fullrepeat-20260627T070421Z/`
- fresh row0 after TTFT: `104.30919255569083 tok/s`
- wall row0: `90.85119259916031 tok/s`
- canary: `6144/6144`
- LocalMaxxing: `cmqw1tgzx0366qr01g4lkv7f1`

This run is diagnostic only: `MAX_TOKENS=128`, `BENCH_REPEATS=1`, route
profiling enabled, and only `8/8` canary rows.

## Run

- data:
  `data/gemma4-q8-gpu0-routeprofile-rmsreuse-ub768-20260627Tmanual/`
- server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-routeprofile-rmsreuse-ub768-20260627Tmanual.server.log`
- target/verifier: `gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- draft: `MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf`
- common identity: current record stack, `UBATCH_SIZE=768`,
  `MTP_N_MAX=7`, `MTP_N_MIN=3`, `MTP_P_MIN=0.10`, graph enabled, VMM off,
  route cache on, RMS reuse on, fused assistant output argmax on, verifier
  backend argmax IDs on
- profiling flags: `LLAMA_SYCL_MUL_MAT_ID_ROUTE_PROFILE=1`,
  `LLAMA_SYCL_MUL_MAT_ID_ROUTE_PROFILE_EVERY=10`
- canary: `8/8`
- diagnostic row: `99.64146044247981 tok/s` after TTFT on a 128-token bench
  row, not headline-comparable

## Final Route Profile

Final cumulative route-profile counters from the server log:

| Bucket | Calls | Avg tokens | Avg routed rows | Avg global unique experts | Avg repeated rows | Avg max expert rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 2710 | 25.776 | 206.211 | 30.966 | 175.245 | 19.031 |
| tok1 | 18 | 1.000 | 8.000 | 8.000 | 0.000 | 1.000 |
| tok2_8 | 2152 | 7.665 | 61.323 | 23.819 | 37.505 | 6.593 |
| tok33p | 540 | 98.778 | 790.222 | 60.215 | 730.007 | 69.200 |

The decode-like bucket is `tok2_8`: average max expert slice is only `6.593`
rows, so most per-expert slices are at or below the `MMVQ_MAX_BATCH_SIZE == 8`
threshold.

Source selection confirms this is already the active path:

- `ggml/src/ggml-sycl/common.hpp`: `MMVQ_MAX_BATCH_SIZE 8`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: `can_use_mul_mat_vec_q()` returns true
  for quantized `src0`, F32 `src1` / `dst`, and `src1->ne[1] <= 8`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`: `ggml_sycl_mul_mat()` routes that case
  to `ggml_sycl_op_mul_mat_vec_q()`
- `ggml/src/ggml-sycl/mmvq.cpp`: Q8 calls reach
  `mul_mat_vec_q8_0_q8_1_sycl_switch_ncols()` for `src1_ncols <= 8`

## Interpretation

The current route-row layer is not missing an obvious "use MMVQ for small
slices" switch; that switch is already in the generic matmul path. This explains
why the guarded prequant route-row attempt was correct but slower: it added a
standalone prequantization/direct-MMVQ detour around a path that was already
choosing MMVQ for the hot decode-sized slices.

The large `tok33p` entries are prefill or larger batched work, not the
fresh-response decode bottleneck that MTP optimization is trying to improve.

## Decision

Do not repeat these unchanged:

- prequant route-row direct MMVQ;
- route/gather/scatter plumbing around `MUL_MAT_ID`;
- broad `MUL_MAT_ID` rewrites that do not change the actual Q8 MMVQ body;
- more counters proving small slices are small.

If continuing source work in this lane, target one of:

1. the actual `q8_0 x q8_1` MMVQ kernel body for `ncols=2..8`;
2. a verifier LM-head design that preserves exact greedy correctness without
   materializing full logits;
3. a fresh-valid speculation source that increases accepted tokens per target
   verifier call without repeated-output history.
