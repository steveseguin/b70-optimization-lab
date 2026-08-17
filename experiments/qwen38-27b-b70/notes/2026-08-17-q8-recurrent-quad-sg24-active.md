# Qwen3.8 27B Q8 TP2 recurrent-quad SG24 workgroup

Date: 2026-08-17

Status: accepted and promoted on the reference ASRock host

Accepted SG16 (256 work items) improved two opposite-order endpoint pairs;
SG32 (512 work items) regressed `0.233%` in a fully complementary 16-process
screen. This midpoint trial packs 24 independent SG16 rows (384 work items)
per exact-shape recurrent GDN-quad workgroup.

The per-row Q8 DP4A walk, FP32 accumulation and subgroup reduction remain
unchanged. The experiment is target-only equal TP2 with F16 KV,
FlashAttention and `b1024/ub256`. It must announce SG24 on both devices and
end with `VERIFY_MISMATCH=0`. Screening will use complementary orders so SG16
and SG24 occupy the same process positions across the combined result. Any
quality mismatch or non-positive position-balanced result rejects the arm.

Other hosts should use the promoted reproduction rather than duplicate this
exact SG24-vs-SG16 arm.

## Checkpoint

The SG24 smoke announced on both B70s and ended with
`VERIFY_MISMATCH=0`. A fully complementary 16-process `p64/n256/r3` screen
measured SG24 `37.259894` versus accepted SG16 `36.940721 tok/s` (`+0.864%`).
Both eight-process orders favored SG24 (`+1.326%`, `+0.400%`).

The first realistic endpoint pair (fresh SG16, then fresh SG24) also favored
SG24: `+0.321%` primary median, `+0.435%` full-decode median and `+0.283%`
full-decode mean. The reverse pair (fresh SG24, then fresh SG16) independently
favored SG24 by `+0.391%` on the primary median.

Pooling the two opposite process orders measured SG16 `36.757534` versus SG24
`36.888416 tok/s` on the primary tokens-1-100 median (`+0.356%`). The pooled
primary mean improved `+0.349%`, full-decode median `+0.415%`, full-decode mean
`+0.311%`, and wall median `+0.400%`. All four 12-prompt suites had
`cached_tokens=0`, passed the final-gate policy, and produced the same 12
complete output hashes.

The independent quality suite passed 7/7 exact semantic canaries, 8/8
deterministic repeats, and the actual 3,829-token long-context needle. It
reported both `pass_all=true` and `baseline_match_all=true`. The accepted-source
rebuild then announced `24xSG16` on both B70s in a TP2 smoke and ended at
`VERIFY_MISMATCH=0`.

## Decision

Promote `GGML_SYCL_MMVQ_Q8_QUAD_SG24=1` after the accepted SG16 patch. SG24
takes priority when both doors are enabled, so setting SG24 to zero restores
the accepted SG16 control without rebuilding. This is a small, repeatable
target-only gain; it does not replace the higher historical `36.772932 tok/s`
conventional headline because these matched A/B sessions used a distinct
reasoning-off identity and lower absolute process state.

Artifacts:

- structured result:
  [`../data/2026-08-17-q8-recurrent-quad-sg24-accepted.json`](../data/2026-08-17-q8-recurrent-quad-sg24-accepted.json)
- incremental patch:
  [`../../../patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg24-20260817.diff`](../../../patches/qwen38-27b-q8-tp2-asrock-b70/recurrent-quad-sg24-20260817.diff)
