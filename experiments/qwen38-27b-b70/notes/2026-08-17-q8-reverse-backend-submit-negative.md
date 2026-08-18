# Qwen3.8 Q8 TP2 reverse backend submission order

Date: 2026-08-17

Status: closed negative; do not repeat unchanged

## Hypothesis

The meta backend submits each independent tensor-parallel subgraph to rank 0
and then rank 1 before queuing the ordered collective. A host-only experiment
reversed those two asynchronous submission calls so rank 1's partial might be
ready when the rank-0 collective root was queued. It did not change a graph,
kernel, tensor, cross-device access, model operation, or arithmetic order.

The candidate was a default-off `GGML_META_REVERSE_BACKEND_SUBMIT=1` door in
`ggml-backend-meta.cpp`. It reused the accepted DP4A2 x SG24 SYCL library
byte-for-byte (`e75b960307fccee661073e67d8288b3893f421617ea83a100cf9b8f9de38b4b5`);
only `libggml-base` differed. The exact source increment is retained as
[`q8-reverse-backend-submit-negative-20260817.diff`](../patches/q8-reverse-backend-submit-negative-20260817.diff).

## Result

A same-binary `A-B-B-A` screen used Qwen3.8-27B Q8_0, equal TP2,
`level_zero:1,0`, `SYCL0/SYCL1`, F16 KV, FlashAttention, p64/n128/r3,
b1024/ub256, and every promoted target-only runtime door. Each fresh process
ran inside a 10 GiB RAM / 8 GiB swap cap.

| Position | Arm | Decode tok/s |
| ---: | --- | ---: |
| 1 | accepted rank-0-first | 36.025559 |
| 2 | rank-1-first | 36.707261 |
| 3 | rank-1-first | 35.836582 |
| 4 | accepted rank-0-first | 36.765676 |

- control mean: `36.395617500 tok/s`;
- candidate mean: `36.271921500 tok/s`;
- candidate delta: **`-0.339865095%`**;
- all four runs: `VERIFY_MISMATCH=0` and the accepted fusion census;
- no Xe fault, reset, hang, timeout, device-lost, or kernel panic appeared in
  the test window.

The candidate's two positions disagreed by much more than its plausible
effect and the pooled result was negative. Sequential host submission is not
the remaining bottleneck at this resolution. Retain rank-0-first order and do
not promote or endpoint-test this door.

The accepted source was restored after the screen. The legacy
`qwen36-q8-b70.service`, which had automatically restarted after the reboot
and initially occupied both GPUs, was disabled and stopped before testing.
