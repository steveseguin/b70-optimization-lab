# SYCL RoPE plus KV-cache write fusion: rejected

Date: 2026-08-13

## Experiment

The existing default-off `GGML_SYCL_ROPE_SET_ROWS_FUSION=1` path computes K
RoPE and writes the F16 KV cache in one kernel. The Muse graph exposes the
eligible `ROPE -> VIEW -> SET_ROWS` chain on 39 of 52 layers. This removes one
kernel submission and the intermediate RoPE output read on those layers while
retaining the existing RoPE arithmetic and final F16 cast.

An exact 64-token control/candidate/control packet on the retained TP4 stack
measured:

| arm | prose | code | JSON | arithmetic mean |
|---|---:|---:|---:|---:|
| control before | 68.766 | 114.673 | 222.121 | 135.187 |
| fusion | 68.561 | 114.698 | 221.169 | 134.809 |
| control after | 69.395 | 114.524 | 221.375 | 135.098 |

All hashes, proposal counts, and accepted counts were identical. Candidate
round-time deltas versus the interpolated controls were `+0.438 / -0.044 /
+0.126 ms` for prose/code/JSON. The candidate lost about `0.25%` against the
pooled control mean and did not justify a full run.

Evidence:

- config:
  `experiments/muse-glimmer-30b-b70/sweeps/20260813-dflash-rope-setrows-fusion-cac64.json`;
- JSONL:
  `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dflash-rope-setrows-fusion-cac64-20260813.jsonl`,
  SHA-256 `6da0298a26f8b86485c595811f2e4f32d4fa7d173f4dc91734329f8be2992bb2`.

## Decision

Leave the fusion default-off. This is another exact example where removing a
few lightweight launches does not improve the current verifier critical path.
