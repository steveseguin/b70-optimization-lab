# Qwen3.8 27B Q8 TP2 recurrent-quad SG24 workgroup

Date: 2026-08-17

Status: active; claimed on the reference ASRock host

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

Other hosts should not duplicate this exact SG24 arm while the note is active.

## Checkpoint

The SG24 smoke announced on both B70s and ended with
`VERIFY_MISMATCH=0`. A fully complementary 16-process `p64/n256/r3` screen
measured SG24 `37.259894` versus accepted SG16 `36.940721 tok/s` (`+0.864%`).
Both eight-process orders favored SG24 (`+1.326%`, `+0.400%`).

The first realistic endpoint pair (fresh SG16, then fresh SG24) also favored
SG24: `+0.321%` primary median, `+0.435%` full-decode median and `+0.283%`
full-decode mean. All 12 complete output hashes matched and both arms had
`cached_tokens=0`. The reverse process-order pair is required before a
promotion decision.
