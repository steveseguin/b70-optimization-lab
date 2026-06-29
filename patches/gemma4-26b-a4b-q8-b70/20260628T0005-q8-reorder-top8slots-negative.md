# Q8 Reorder Top-8 Slots Negative Patch Note

Date: 2026-06-28

Source tree:
`/home/steve/src/llama.cpp-gemma-record-repro-c926`

This default-off patch added a reordered-Q8 multi-token `MUL_MAT_ID` path for
the active Gemma verifier MoE shape where `ids ne=[8,2]` and
`src1 ne=[2816,1,2,1]`.

## Files / Symbols

- `ggml/src/ggml-sycl/mmvq.cpp`
  - `mul_mat_vec_q8_0_moe_multi_token_top8_slots_reorder()`
  - `launch_mul_mat_vec_q8_0_moe_multi_token_top8_slots_reorder()`
  - `ggml_sycl_mul_mat_vec_q_id_multi_token_top8_slots_q8_0_reorder()`
- `ggml/src/ggml-sycl/mmvq.hpp`
  - declaration for
    `ggml_sycl_mul_mat_vec_q_id_multi_token_top8_slots_q8_0_reorder()`
- `ggml/src/ggml-sycl/ggml-sycl.cpp`
  - env gate:
    `LLAMA_SYCL_MUL_MAT_ID_Q8_0_REORDER_TOP8_SLOTS`
  - dispatch inside the fused small multi-token MoE verifier path.

Harness logging updates:

- `scripts/run-gemma4-26b-llamacpp-replica.sh`
- `scripts/run-gemma4-26b-first-baseline.sh`

## Intended Optimization

Compute all eight selected expert slots for one token/row in a single workgroup
so the quantized activation row is loaded once and reused across top-8 experts.

## Result

Quality and fresh-response validity passed on all four B70 lanes, but
throughput did not beat the current strict record:

- best row: `91.45707162294053 tok/s` on GPU0;
- four-lane center: below the current promoted
  `90.98312252660529 tok/s` record;
- decision: negative, no LocalMaxxing submission.

Full experiment ledger:
`experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0005-q8-reorder-top8slots-negative.md`

## Lesson

The active top-8 shape is real, but slot-blocking all experts together likely
raises register/private-memory pressure enough to erase the activation-row
reuse benefit. Do not retry this exact approach without kernel-profile evidence.
