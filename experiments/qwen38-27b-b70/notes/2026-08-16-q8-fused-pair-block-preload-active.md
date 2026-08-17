# Qwen3.8 Q8 fused-pair block preload

Date: 2026-08-16  
Status: closed, endpoint-neutral; do not promote

## Hypothesis

The accepted SG16 reordered-Q8 MMVQ gives each lane one aligned 16-byte weight load per subgroup iteration. Two adjacent iterations are independent until their FP32 contributions are added. The candidate loads the operands for iterations `i` and `i + blocks_per_subgroup` before executing either DP4A chain, then adds their contributions in the original order.

The treatment is limited to the launch-fused Q8 pair kernel. It does not change the model, quantization, tensor split, subgroup reduction, DP4A order within a block, FP32 block accumulation order, KV type, or sampling. A same-binary environment door, `GGML_SYCL_MMVQ_Q8_PAIR_BLOCKS`, selects the paired walk. The off arm retains the existing loop body.

## Same-boot control

After the 2026-08-16 reboot, the corrected accepted binary completed the fixed 12-prompt, 512-token suite at `36.417180562989 tok/s` conventional. All 12 complete output hashes matched the promoted oracle and every request reported zero cached tokens. Raw evidence is `/mnt/fast-ai/bench-results/qwen38-q8-accepted-postreboot-control-20260816.json`, SHA-256 `1d008e7bce2640ad9eeddf45495c5029ef392959c395d81f548c73d9328ebb01`.

Both cards held 2800 MHz during the control, used about 13.7 GiB VRAM each, and reported no reset, driver, cache, or ECC errors.

## Safety and build boundary

The candidate is building in an isolated source and CMake tree under `/mnt/fast-ai/src/llama.cpp-q38-q8-paired-blocks`. The build uses IntelLLVM 2026.1.1, BMG-G31 AOT, `-j2`, and a 6/8 GiB host-memory scope. No model workload overlaps compilation.

## Result

The same-binary `p64/n256` bracket ran A1/B1/B2/A2, with three repetitions in the first pair and five in the second:

| Arm | Decode |
| --- | ---: |
| A1, door off | `36.863472 tok/s` |
| B1, door on | `36.813444 tok/s` |
| B2, door on | `36.597669 tok/s` |
| A2, door off | `36.514540 tok/s` |

The pooled control was `36.689006 tok/s`; the pooled treatment was `36.705557 tok/s`, only `+0.045%`. The paired comparisons crossed direction (`-0.136%`, then `+0.228%`). The treatment announced on both devices, the r5 run executed 163,968 fused pair kernels, and `VERIFY_MISMATCH=0`.

This is below endpoint resolution and does not justify a full 12-prompt candidate suite. No candidate output-hash claim is made. The source intentionally retained DP4A and FP32 block-add order, but that structural argument is not a substitute for the unrun full oracle.

## Decision

Reject for performance. Do not extend this unchanged two-iteration preload to the triple and quad kernels: its intended memory-level-parallelism benefit was already absent in the high-byte fused-pair path. Exact data and the incremental source are retained in the [structured result](../data/2026-08-16-q8-fused-pair-block-preload-neutral.json) and [patch](../patches/q8-fused-pair-block-preload-neutral-20260816.diff).
