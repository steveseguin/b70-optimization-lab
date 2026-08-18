# Qwen3.8 Q8 paired sum/amax subgroup reduction

Date: 2026-08-17

Status: closed negative; do not repeat unchanged

## Hypothesis

Each hot Q8_1 activation quantizer reduces both an FP32 sum and absolute
maximum over the same SG16 butterfly. The candidate packed their FP32 bit
patterns into one `uint64_t`, exchanged both values with a single
`sycl::select_from_group` per XOR stage, then performed the original FP32 add
and `fmax`. It changed neither the reduction tree nor the downstream Q8_1
format.

The treatment covered all eight live Q8_1 quantization sites in `quantize.hpp`,
`element_wise.cpp`, and `ggml-sycl.cpp`. The exact source increment is retained
as [`q8-paired-sum-amax-reduction-negative-20260817.diff`](../patches/q8-paired-sum-amax-reduction-negative-20260817.diff).

## Correctness and mechanism gates

- An independent BMG-G31 SYCL device probe compared the original two subgroup
  reductions with the packed XOR butterfly over 10,000 randomized SG16 blocks:
  `mismatches=0`, `exact=1`.
- A strict TP2 p0/n1 model smoke exercised 1,980 Q8 memo comparisons:
  `verified=1980 VERIFY_MISMATCH=0`.
- Every measured process below also reported `VERIFY_MISMATCH=0`.
- Candidate `llama-bench` SHA-256:
  `ae0dc3b22a07f68abc9a94c4a674cec0828e7a2c2e811e93c03f906db89ef9fa`.
- Candidate `libggml-sycl.so.0.19.0` SHA-256:
  `f2ebc360d8a29b18cc1a3081013168a9b72f3d1688b107f63fba0fe49f157146`.
- Accepted library SHA-256:
  `e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`.

The candidate was built from an isolated copy of the accepted DP4A2 x SG24
source with oneAPI 2026.1.1, Release AOT for `bmg_g31`, and the accepted build
features. A control-library override kept the candidate host executable and
all non-SYCL libraries identical between arms.

## Performance result

Both screens used Qwen3.8-27B Q8_0, equal TP2, `level_zero:1,0`,
`SYCL0/SYCL1`, F16 KV, FlashAttention, b1024/ub256, and all promoted
target-only runtime doors. Each process ran in a bounded 10 GiB RAM / 8 GiB
swap service.

The short p64/n128/r3 A-B-B-A screen was inconclusive:

| Position | Arm | Decode tok/s |
| ---: | --- | ---: |
| 1 | accepted | 36.627452 |
| 2 | packed reduction | 36.956011 |
| 3 | packed reduction | 36.374308 |
| 4 | accepted | 36.433352 |

- control mean: `36.530402000 tok/s`;
- candidate mean: `36.665159500 tok/s`;
- candidate delta: `+0.368894263%`.

The longer p64/n512/r3 A-B-B-A confirmation rejected the candidate:

| Position | Arm | Decode tok/s |
| ---: | --- | ---: |
| 1 | accepted | 36.912021 |
| 2 | packed reduction | 36.885847 |
| 3 | packed reduction | 37.174417 |
| 4 | accepted | 37.607084 |

- control mean: `37.259552500 tok/s`;
- candidate mean: `37.030132000 tok/s`;
- candidate delta: **`-0.615736059%`**.

The apparent short-screen gain did not survive a longer balanced bracket, and
the closing control was the fastest position. One packed 64-bit subgroup
shuffle does not outperform the compiler/runtime implementation of the two
native reductions on BMG-G31. No endpoint gate is warranted. Retain the
accepted separate sum and maximum reductions.

No Xe fault, reset, hang, timeout, device-lost event, or kernel panic appeared
in the experiment window. No hardware, PCI, power-management, driver, or
kernel policy was changed.
