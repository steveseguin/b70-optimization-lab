# Qwen3.8 Q8 root-fused collective result

Date: 2026-08-16

Status: **safe and exact at the benchmark gate, but rejected as a 3.388%
decode regression**.

## Result

After a clean reboot, the host showed only its audited one-time KMS
`dma_buf_vmap` warning. Both B70s were normal, full-size device allocations
were visible, and no Xe/GuC compute fault existed. The old Qwen3.6 autostart
service was stopped so every run owned both GPUs.

The mode-4 `p0/n1/r1` safety smoke completed at `34.730080 tok/s`, printed the
root-fused activation marker, and reported `VERIFY_MISMATCH=0`. The same binary
in accepted mode 2 completed at `36.581733 tok/s`. Both cards remained normal
with no new fault, timeout, reset, or hang.

A position-balanced `A-B-B-A` bracket then used p64/n256/r3, equal TP2, F16
KV, FlashAttention, b1024/ub256, and the accepted Qwen3.8 environment:

| Arm | Mode | Decode tok/s | Stdev |
| --- | ---: | ---: | ---: |
| A1 | accepted mode 2 | `35.999246` | `0.044694` |
| B1 | root-fused mode 4 | `34.927634` | `0.042171` |
| B2 | root-fused mode 4 | `34.938762` | `0.019549` |
| A2 | accepted mode 2 | `36.317383` | `0.250897` |

- mean control: `36.1583145 tok/s`;
- mean candidate: `34.9331980 tok/s`;
- candidate delta: **`-3.388201%`**;
- every arm: expected fusion counters and `VERIFY_MISMATCH=0`;
- every post-arm health gate: passed;
- current-boot compute fault/reset/hang signatures: zero.

The removed submission did not compensate for serializing device 1 behind the
longer root kernel. This confirms the earlier scheduling diagnosis: extending
the root critical path is worse than retaining the accepted short reduction
followed by independently owned device handoffs.

## Evidence and decision

Raw logs are under:

`/mnt/fast-ai/bench-results/qwen38-q8-asrock-b70-20260816-root-fused-mode4/`

SHA-256:

- mode-4 safety smoke: `72cb905099f86d985cb5271aeadd53af143db75dc29de5b2bc1d0e521625fba4`;
- same-binary mode-2 smoke: `052d7eb9de500a8b4a1fe4386548eed9d1b3f50ab5d2177cacc5b8f1b4f47dfa`;
- A1 mode 2: `12f1b6fa957932b4346654173d570a95dd23c55bac87b4fa059f3c444dc1bc15`;
- B1 mode 4: `27f35d25730ddf448d37134aa9d93fb2c179caacfb473d02b4d968946c1969f7`;
- B2 mode 4: `45b605ca0c156af34553a4f47d5787cf8ac0e8aa5bb457165ab71d7e91c38243`;
- A2 mode 2: `07057f885377493dacf72abe138b1f368019e1eac48e45d5839e463b2ba71693`.

Do not enable or retest mode 4 unchanged. It passed the safety/exactness
screen but failed the performance gate by a wide margin, so no endpoint suite
or semantic gate was warranted. Keep accepted mode 2 and move to a candidate
that does not lengthen the cross-device critical path.
