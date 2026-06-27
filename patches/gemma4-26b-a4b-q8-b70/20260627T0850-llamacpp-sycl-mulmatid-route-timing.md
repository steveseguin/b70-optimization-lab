# llama.cpp SYCL MUL_MAT_ID Route Timing Diagnostic

Date: 2026-06-27T08:50Z

## Status

Diagnostic-only patch. Keep as a reusable experiment artifact, but do not
promote as a production performance change.

## Source Tree

- repo: `/home/steve/src/llama.cpp-gemma-record-stack`
- relevant file: `ggml/src/ggml-sycl/ggml-sycl.cpp`
- build target verified: `build-sycl-b70-aot-bmg-g31/bin/llama-server`

## What Changed

Added default-off timing instrumentation around the routed
`ggml_sycl_mul_mat_id()` multi-token path.

New env flags:

- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING=1`
- `LLAMA_SYCL_MUL_MAT_ID_ROUTE_TIMING_EVERY=<N>` (default `25`)

When enabled, the code measures:

- route copy/sort;
- route map upload;
- gathered input creation;
- routed expert matmul;
- scattered output restore;
- total profiled time.

It prints lines like:

```text
llama.cpp: SYCL_MUL_MAT_ID_ROUTE_TIMING call=... name=... hit=... n_ids=... n_tokens=... routed=... active_experts=... src0_type=... src1_type=... dst_type=... copy_sort_us=... map_upload_us=... gather_us=... matmul_us=... scatter_us=... total_profiled_us=...
```

The timing path intentionally inserts stream waits, so any throughput measured
with the flag enabled is perturbed and must not be used as a record claim.

The results harness was updated to preserve the timing flags in run identity:

- `scripts/run-gemma4-26b-first-baseline.sh`
- `scripts/run-gemma4-26b-llamacpp-replica.sh`

## Validation

- `git diff --check -- ggml/src/ggml-sycl/ggml-sycl.cpp`: pass
- build with oneAPI environment:
  `cmake --build build-sycl-b70-aot-bmg-g31 --target llama-server -j 8`: pass
- diagnostic run:
  `data/gemma4-q8-gpu0-mmid-route-timing-rmsreuse-ub768-nmin3-pmin010-20260627T085044Z/`
- canary: `8/8`
- parsed timing records: `337`

## Result

The diagnostic rejected routed-MoE plumbing as a lead optimization lane:

- decode-like `n_tokens=8 src0=q8_0`: route overhead mean `20.66 us`
  (`3.30%`), matmul mean `630.77 us` (`96.70%`);
- decode-like `n_tokens=2 src0=q8_0`: route overhead mean `18.43 us`
  (`6.92%`), matmul mean `254.43 us` (`93.08%`);
- larger groups are also mostly matmul-dominated.

Decision: do not spend more primary effort on route/gather/scatter plumbing for
this record stack. Move to verifier/output economics, especially the target
LM-head cost that remains after backend argmax IDs removed host logits copies.

Primary note:

- `experiments/gemma4-26b-a4b-q8-b70/sweeps/20260627T0850-mulmatid-route-timing.md`
